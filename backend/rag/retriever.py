"""
ReliefOps AI — Unified SOP Retriever Engine
Provides the primary clean retrieval interface for the Needs Assessment Agent.
Combines ChromaDB persistent vector search with genuine Okapi BM25 keyword fallback.
"""

import datetime
import os
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.database.db_manager import DatabaseManager, default_db_manager
from backend.rag.document_loader import SOPChunk, SOPDocumentLoader
from backend.rag.fallback_retriever import BM25Retriever
from backend.rag.vector_store import ChromaVectorStore


class SOPChunkResult(BaseModel):
    """Structured representation of a retrieved SOP chunk."""
    chunk_id: str
    sop_id: str
    title: str
    category: str
    hazard_type: str
    source_agency: str
    section_title: str
    content: str
    score: float
    retrieval_method: str


class RetrievalResult(BaseModel):
    """Complete retrieval payload returned to consuming agents."""
    query: str
    retrieved_chunks: List[SOPChunkResult] = Field(default_factory=list)
    sop_ids: List[str] = Field(default_factory=list)
    retrieval_method: str
    total_hits: int = 0
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SOPRetriever:
    """Unified Disaster SOP Retriever supporting ChromaDB Vector Search and BM25 Fallback."""

    def __init__(
        self,
        vector_store: Optional[ChromaVectorStore] = None,
        bm25_retriever: Optional[BM25Retriever] = None,
        db: Optional[DatabaseManager] = None
    ):
        self.vector_store = vector_store or ChromaVectorStore()
        self.bm25_retriever = bm25_retriever or BM25Retriever()
        self.db = db or default_db_manager
        self.loader = SOPDocumentLoader()
        self._is_indexed = False

    def ingest_and_index(self, sops_dir: Optional[str] = None) -> Dict[str, Any]:
        """Loads all SOP markdown files, indexes into ChromaDB & BM25, and records in SQLite."""
        if sops_dir:
            self.loader = SOPDocumentLoader(sops_dir)

        chunks = self.loader.load_all_chunks()
        if not chunks:
            return {"status": "EMPTY", "documents_indexed": 0, "chunks_indexed": 0}

        # 1. Index in ChromaDB
        chroma_count = self.vector_store.index_chunks(chunks)

        # 2. Index in BM25 Fallback Engine
        self.bm25_retriever.index(chunks)
        self._is_indexed = True

        # 3. Synchronize SOP Document metadata in SQLite
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        docs_by_sop: Dict[str, List[SOPChunk]] = {}
        for c in chunks:
            docs_by_sop.setdefault(c.sop_id, []).append(c)

        for sop_id, chunk_list in docs_by_sop.items():
            first = chunk_list[0]
            self.db.execute_non_query(
                """
                INSERT OR REPLACE INTO sop_documents
                (doc_id, title, disaster_type, source_agency, chunk_count, chromadb_collection, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sop_id,
                    first.title,
                    first.hazard_type,
                    first.source_agency,
                    len(chunk_list),
                    self.vector_store.collection_name,
                    now
                )
            )

        return {
            "status": "SUCCESS",
            "documents_indexed": len(docs_by_sop),
            "chunks_indexed": len(chunks),
            "chroma_chunks": chroma_count
        }

    def ensure_indexed(self) -> None:
        """Guarantees the in-memory BM25 index is populated if not already done."""
        if not self._is_indexed or self.bm25_retriever.num_docs == 0:
            chunks = self.loader.load_all_chunks()
            self.bm25_retriever.index(chunks)
            self._is_indexed = True

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        force_fallback: bool = False,
        hazard_filter: Optional[str] = None
    ) -> RetrievalResult:
        """Primary retrieval method. Uses ChromaDB vector search with automatic BM25 fallback."""
        start_time = time.perf_counter()

        # Handle empty/whitespace query
        if not query or not query.strip():
            return RetrievalResult(
                query=query or "",
                retrieved_chunks=[],
                sop_ids=[],
                retrieval_method="none",
                total_hits=0,
                execution_time_ms=0.0,
                metadata={"reason": "empty_query"}
            )

        self.ensure_indexed()

        # Route 1: Explicit offline fallback request
        if force_fallback:
            return self._retrieve_bm25(query, top_k, hazard_filter, start_time)

        # Route 2: ChromaDB Vector Retrieval
        try:
            where_filter = None
            if hazard_filter and hazard_filter.upper() != "ALL":
                where_filter = {"hazard_type": hazard_filter.upper()}

            raw_results = self.vector_store.query(
                query_text=query,
                top_k=top_k,
                where_filter=where_filter
            )

            if raw_results:
                chunk_models = [SOPChunkResult(**r) for r in raw_results]
                unique_sops = list(dict.fromkeys([c.sop_id for c in chunk_models]))
                elapsed = (time.perf_counter() - start_time) * 1000.0

                return RetrievalResult(
                    query=query,
                    retrieved_chunks=chunk_models,
                    sop_ids=unique_sops,
                    retrieval_method="vector_chromadb",
                    total_hits=len(chunk_models),
                    execution_time_ms=round(elapsed, 2),
                    metadata={"engine": "ChromaDB", "model": "all-MiniLM-L6-v2-onnx"}
                )
            else:
                # If vector search returned 0 results, fall back to BM25
                return self._retrieve_bm25(query, top_k, hazard_filter, start_time)

        except Exception as e:
            # On any vector store failure, gracefully trigger genuine BM25 fallback
            res = self._retrieve_bm25(query, top_k, hazard_filter, start_time)
            res.metadata["fallback_trigger_exception"] = str(e)
            return res

    def _retrieve_bm25(
        self,
        query: str,
        top_k: int,
        hazard_filter: Optional[str],
        start_time: float
    ) -> RetrievalResult:
        """Executes genuine BM25 keyword retrieval."""
        raw_results = self.bm25_retriever.query(
            query_text=query,
            top_k=top_k,
            category_filter=hazard_filter
        )

        chunk_models: List[SOPChunkResult] = []
        for chunk, score in raw_results:
            chunk_models.append(
                SOPChunkResult(
                    chunk_id=chunk.chunk_id,
                    sop_id=chunk.sop_id,
                    title=chunk.title,
                    category=chunk.category,
                    hazard_type=chunk.hazard_type,
                    source_agency=chunk.source_agency,
                    section_title=chunk.section_title,
                    content=chunk.content,
                    score=score,
                    retrieval_method="bm25_keyword_fallback"
                )
            )

        unique_sops = list(dict.fromkeys([c.sop_id for c in chunk_models]))
        elapsed = (time.perf_counter() - start_time) * 1000.0

        return RetrievalResult(
            query=query,
            retrieved_chunks=chunk_models,
            sop_ids=unique_sops,
            retrieval_method="bm25_keyword_fallback",
            total_hits=len(chunk_models),
            execution_time_ms=round(elapsed, 2),
            metadata={"engine": "Okapi BM25", "k1": self.bm25_retriever.k1, "b": self.bm25_retriever.b}
        )


# Module-level singleton instance for shared usage
default_sop_retriever = SOPRetriever()


"""
ReliefOps AI — ChromaDB Vector Store Engine
Persistent vector indexing and semantic retrieval for disaster management SOP chunks.
"""

import os
from typing import Any, Dict, List, Optional, Tuple
import chromadb
from chromadb.config import Settings
from backend.rag.document_loader import SOPChunk


class ChromaVectorStore:
    """Manages persistent ChromaDB vector storage and semantic similarity search."""

    def __init__(self, persist_dir: Optional[str] = None, collection_name: str = "disaster_sops"):
        if persist_dir is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            env_path = os.getenv("CHROMADB_PATH", "").strip()
            if env_path:
                persist_dir = env_path if os.path.isabs(env_path) else os.path.join(base_dir, env_path)
            else:
                persist_dir = os.path.join(base_dir, "data", "chromadb")

        self.persist_dir = os.path.abspath(persist_dir)
        os.makedirs(self.persist_dir, exist_ok=True)
        self.collection_name = collection_name

        # Initialize persistent ChromaDB client
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(anonymized_telemetry=False, is_persistent=True)
        )
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "ReliefOps AI Disaster Management SOP Embeddings", "hnsw:space": "cosine"}
        )

    def index_chunks(self, chunks: List[SOPChunk]) -> int:
        """Upserts a list of SOP chunks into the ChromaDB collection."""
        if not chunks:
            return 0

        ids = [c.chunk_id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [c.to_metadata() for c in chunks]

        # ChromaDB handles batch upserting
        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        return len(chunks)

    def query(
        self,
        query_text: str,
        top_k: int = 3,
        where_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Queries the vector store for nearest semantic neighbor chunks."""
        if not query_text or not query_text.strip():
            return []

        # Count available documents in collection
        total_docs = self.collection.count()
        if total_docs == 0:
            return []

        actual_k = min(top_k, total_docs)

        query_params = {
            "query_texts": [query_text],
            "n_results": actual_k,
            "include": ["metadatas", "documents", "distances"]
        }
        if where_filter:
            query_params["where"] = where_filter

        results = self.collection.query(**query_params)

        formatted_results: List[Dict[str, Any]] = []
        if not results or not results["ids"] or not results["ids"][0]:
            return formatted_results

        ids = results["ids"][0]
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0] if "distances" in results and results["distances"] else [0.0] * len(ids)

        for i in range(len(ids)):
            # In cosine space, similarity = 1.0 - distance
            dist = distances[i] if i < len(distances) else 0.5
            similarity_score = max(0.0, round(1.0 - float(dist), 4))

            meta = metas[i] if i < len(metas) else {}
            formatted_results.append({
                "chunk_id": ids[i],
                "sop_id": meta.get("sop_id", "UNKNOWN"),
                "title": meta.get("title", ""),
                "category": meta.get("category", ""),
                "hazard_type": meta.get("hazard_type", ""),
                "source_agency": meta.get("source_agency", ""),
                "section_title": meta.get("section_title", ""),
                "content": docs[i],
                "score": similarity_score,
                "retrieval_method": "vector_chromadb"
            })

        return formatted_results

    def count(self) -> int:
        """Returns the number of indexed chunks."""
        return self.collection.count()

    def reset(self) -> None:
        """Clears the collection."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "ReliefOps AI Disaster Management SOP Embeddings", "hnsw:space": "cosine"}
        )


"""
ReliefOps AI — RAG & Vector Retrieval Unit Tests
Tests document loading, section-aware chunking, ChromaDB vector indexing,
retrieval accuracy, citation verification, BM25 offline fallback, and edge cases.
"""

import os
import unittest
from backend.rag.document_loader import SOPDocumentLoader, SOPChunk
from backend.rag.fallback_retriever import BM25Retriever
from backend.rag.vector_store import ChromaVectorStore
from backend.rag.retriever import SOPRetriever, RetrievalResult, default_sop_retriever


class TestSOPKnowledgeBaseAndRAG(unittest.TestCase):
    """Test suite for SOP Knowledge Ingestion, ChromaDB Vector Store, and BM25 Retriever."""

    @classmethod
    def setUpClass(cls):
        """Initialize and ingest the SOP knowledge base once for all test cases."""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.sops_dir = os.path.join(base_dir, "data", "sops")
        cls.loader = SOPDocumentLoader(cls.sops_dir)
        cls.retriever = default_sop_retriever
        # Ingest documents
        cls.retriever.ingest_and_index(cls.sops_dir)

    def test_sop_document_loading(self):
        """Test that all 12 SOP markdown documents exist, load, and have valid metadata."""
        md_files = [f for f in os.listdir(self.sops_dir) if f.endswith(".md")]
        self.assertGreaterEqual(len(md_files), 10, "Course requires at least 10 SOP documents")
        self.assertEqual(len(md_files), 12, "Expected exactly 12 authored SOP documents")

        # Test single document parsing
        sample_path = os.path.join(self.sops_dir, "SOP_FL_001_flood_response.md")
        with open(sample_path, "r", encoding="utf-8") as f:
            content = f.read()

        meta, body = self.loader.parse_frontmatter(content)
        self.assertEqual(meta.get("sop_id"), "SOP-FL-001")
        self.assertEqual(meta.get("hazard_type"), "FLOOD")
        self.assertIn("SYNTHETIC DEMONSTRATION DOCUMENT", meta.get("academic_disclaimer", ""))
        self.assertTrue(len(body) > 100)

    def test_text_chunking(self):
        """Test that chunks are cleanly separated by sections with enriched context headers."""
        chunks = self.loader.load_all_chunks()
        self.assertGreater(len(chunks), 30, "Expected at least 30 semantic chunks across 12 documents")

        for chunk in chunks:
            self.assertIsInstance(chunk, SOPChunk)
            self.assertTrue(chunk.chunk_id.startswith("SOP-"))
            self.assertTrue(len(chunk.content) > 20)
            self.assertTrue(len(chunk.section_title) > 0)
            # Verify enriched header format
            self.assertTrue(
                chunk.content.startswith("SOP Document:"),
                f"Chunk {chunk.chunk_id} missing context header prefix"
            )

    def test_chromadb_vector_storage(self):
        """Test that ChromaDB stores and reports indexed documents."""
        count = self.retriever.vector_store.count()
        self.assertGreaterEqual(count, 50, "Expected at least 50 chunks indexed in ChromaDB")

        # Verify ChromaDB directory exists on disk
        chroma_dir = self.retriever.vector_store.persist_dir
        self.assertTrue(os.path.exists(chroma_dir))

    def test_retrieval_accuracy_synthetic_queries(self):
        """Test that semantic retrieval accurately maps domain queries to the correct SOP."""
        test_cases = [
            ("What is the Sphere minimum drinking water requirement per person per day?", "SOP-WAT-006"),
            ("What are the caloric food requirements and family ration pack standards?", "SOP-FOOD-007"),
            ("How are Level 1 through Level 5 riverine flood severity damages classified?", "SOP-FL-001"),
            ("What are the trauma medical kit allocation rules for high medical urgency?", "SOP-MED-005"),
            ("What is the maximum acceptable Gini coefficient and anti-starvation floor?", "SOP-FAIR-010"),
            ("What is the road transit impedance coefficient when a road is blocked?", "SOP-LOG-009")
        ]

        for query, expected_sop_id in test_cases:
            result = self.retriever.retrieve(query, top_k=3)
            self.assertIsInstance(result, RetrievalResult)
            self.assertGreater(result.total_hits, 0, f"No hits for query: {query}")
            self.assertEqual(result.retrieval_method, "vector_chromadb")
            self.assertIn(
                expected_sop_id,
                result.sop_ids,
                f"Query '{query}' did not retrieve expected SOP ID {expected_sop_id}. Retrieved: {result.sop_ids}"
            )

    def test_source_citation_correctness(self):
        """Test that every retrieved chunk has authentic metadata and zero hallucinated citations."""
        result = self.retriever.retrieve("cyclone storm surge emergency response", top_k=3)
        self.assertTrue(len(result.retrieved_chunks) > 0)

        # Catalog of authentic SOP IDs
        valid_sop_ids = {
            "SOP-FL-001", "SOP-EQ-002", "SOP-LS-003", "SOP-CY-004",
            "SOP-MED-005", "SOP-WAT-006", "SOP-FOOD-007", "SOP-VULN-008",
            "SOP-LOG-009", "SOP-FAIR-010", "SOP-SHL-011", "SOP-SAN-012"
        }

        for chunk in result.retrieved_chunks:
            # Check SOP ID conforms to known catalog - no hallucinated IDs
            self.assertIn(chunk.sop_id, valid_sop_ids, f"Retrieved invalid or hallucinated SOP ID: {chunk.sop_id}")
            self.assertTrue(len(chunk.title) > 0, "Chunk title must not be empty")
            self.assertTrue(len(chunk.source_agency) > 0, "Source agency must not be empty")
            self.assertTrue(len(chunk.content) > 30, "Chunk content must be substantive")
            # Ensure score is a normalized probability/similarity
            self.assertGreaterEqual(chunk.score, 0.0)
            self.assertLessEqual(chunk.score, 1.0)

    def test_offline_bm25_fallback(self):
        """Test that genuine BM25 keyword fallback operates deterministically when forced."""
        query = "potable drinking water 15 liters per person per day"
        result = self.retriever.retrieve(query, top_k=3, force_fallback=True)

        self.assertEqual(result.retrieval_method, "bm25_keyword_fallback")
        self.assertIn("SOP-WAT-006", result.sop_ids)
        self.assertGreater(result.total_hits, 0)
        self.assertGreater(result.retrieved_chunks[0].score, 0.0)
        self.assertEqual(result.metadata.get("engine"), "Okapi BM25")

    def test_empty_and_invalid_queries(self):
        """Test graceful handling of empty strings, whitespace, and non-matching queries."""
        # Empty string
        empty_res = self.retriever.retrieve("", top_k=3)
        self.assertEqual(empty_res.total_hits, 0)
        self.assertEqual(empty_res.retrieved_chunks, [])

        # Whitespace
        ws_res = self.retriever.retrieve("    \n\t  ", top_k=3)
        self.assertEqual(ws_res.total_hits, 0)

        # Nonsense gibberish query in fallback mode
        gibberish_res = self.retriever.retrieve("xyzzy999111zzzzqqqnotaword", top_k=3, force_fallback=True)
        self.assertEqual(gibberish_res.total_hits, 0)


if __name__ == "__main__":
    unittest.main()

"""
ReliefOps AI — Genuine Okapi BM25 Offline Fallback Retriever
Pure Python mathematical implementation of Okapi BM25 ranking.
Guarantees 100% deterministic, zero-dependency offline keyword retrieval.
"""

import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from backend.rag.document_loader import SOPChunk


# Common English stopwords to prevent noise in BM25 scoring
STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me",
    "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only",
    "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "would", "you", "your", "yours", "yourself", "yourselves"
}


class BM25Retriever:
    """Okapi BM25 Information Retrieval Engine for Disaster SOP chunks."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.chunks: List[SOPChunk] = []
        self.doc_len: List[int] = []
        self.avg_doc_len: float = 0.0
        self.doc_freqs: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.term_freqs: List[Dict[str, int]] = []
        self.num_docs: int = 0

    def tokenize(self, text: str) -> List[str]:
        """Converts text to lowercase tokens with punctuation stripped and stopwords filtered."""
        tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", text.lower())
        return [t for t in tokens if t not in STOPWORDS]

    def index(self, chunks: List[SOPChunk]) -> None:
        """Indexes a collection of SOP chunks and computes document statistics."""
        self.chunks = chunks
        self.num_docs = len(chunks)
        self.doc_len = []
        self.term_freqs = []
        self.doc_freqs = {}

        total_length = 0
        for chunk in chunks:
            # Combine content and title for indexing
            tokens = self.tokenize(f"{chunk.title} {chunk.section_title} {chunk.content}")
            length = len(tokens)
            self.doc_len.append(length)
            total_length += length

            # Calculate term frequencies for this document
            tf: Dict[str, int] = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            self.term_freqs.append(tf)

            # Update document frequency for unique tokens
            for token in set(tokens):
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1

        self.avg_doc_len = total_length / self.num_docs if self.num_docs > 0 else 0.0

        # Precompute Inverse Document Frequency (IDF) with smoothing
        self.idf = {}
        for token, df in self.doc_freqs.items():
            # Standard Lucene/BM25 IDF formula
            self.idf[token] = math.log(1.0 + (self.num_docs - df + 0.5) / (df + 0.5))

    def query(
        self,
        query_text: str,
        top_k: int = 3,
        category_filter: Optional[str] = None
    ) -> List[Tuple[SOPChunk, float]]:
        """Scores all indexed chunks against query terms and returns top_k highest ranked chunks."""
        if not self.chunks or not query_text or not query_text.strip():
            return []

        query_tokens = self.tokenize(query_text)
        if not query_tokens:
            return []

        scores: List[Tuple[int, float]] = []

        for idx, tf in enumerate(self.term_freqs):
            chunk = self.chunks[idx]
            if category_filter and category_filter.upper() != "ALL":
                cf_low = category_filter.lower()
                if chunk.category.lower() != cf_low and chunk.hazard_type.lower() != cf_low:
                    continue

            score = 0.0
            doc_len = self.doc_len[idx]
            len_norm = 1.0 - self.b + self.b * (doc_len / self.avg_doc_len if self.avg_doc_len > 0 else 1.0)

            for q_term in query_tokens:
                if q_term in tf:
                    term_freq = tf[q_term]
                    idf = self.idf.get(q_term, 0.0)
                    numerator = term_freq * (self.k1 + 1.0)
                    denominator = term_freq + self.k1 * len_norm
                    score += idf * (numerator / denominator)

            if score > 0.0:
                scores.append((idx, score))

        # Sort descending by BM25 score
        scores.sort(key=lambda x: x[1], reverse=True)

        results = [(self.chunks[idx], round(score, 4)) for idx, score in scores[:top_k]]
        return results


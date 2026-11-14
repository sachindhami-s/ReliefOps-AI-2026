"""
ReliefOps AI — SOP Document Loader & Meaningful Chunking Engine
Loads synthetic disaster SOP markdown files, parses structured metadata,
and generates semantically coherent chunks with section preservation.
"""

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SOPChunk:
    """Represents a discrete semantic chunk of a disaster SOP document."""
    chunk_id: str
    sop_id: str
    title: str
    category: str
    hazard_type: str
    source_agency: str
    section_title: str
    chunk_index: int
    content: str
    raw_text: str

    def to_metadata(self) -> Dict[str, Any]:
        """Serializes chunk metadata for vector store indexing."""
        return {
            "chunk_id": self.chunk_id,
            "sop_id": self.sop_id,
            "title": self.title,
            "category": self.category,
            "hazard_type": self.hazard_type,
            "source_agency": self.source_agency,
            "section_title": self.section_title,
            "chunk_index": self.chunk_index
        }


class SOPDocumentLoader:
    """Loads markdown SOP documents, extracts metadata, and chunks by semantic sections."""

    def __init__(self, sops_dir: Optional[str] = None):
        if sops_dir is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            sops_dir = os.path.join(base_dir, "data", "sops")
        self.sops_dir = os.path.abspath(sops_dir)

    def parse_frontmatter(self, text: str) -> Tuple[Dict[str, str], str]:
        """Extracts YAML frontmatter and body from a markdown document."""
        metadata = {}
        body = text
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                frontmatter_text = parts[1].strip()
                body = parts[2].strip()
                for line in frontmatter_text.splitlines():
                    if ":" in line:
                        key, val = line.split(":", 1)
                        metadata[key.strip()] = val.strip().strip('"').strip("'")
        return metadata, body

    def clean_text(self, text: str) -> str:
        """Normalizes whitespace and removes extraneous markdown formatting."""
        # Replace multiple newlines with double newline
        cleaned = re.sub(r"\n{3,}", "\n\n", text)
        return cleaned.strip()

    def chunk_document(self, file_path: str) -> List[SOPChunk]:
        """Loads and breaks a single SOP markdown file into section-aware semantic chunks."""
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        meta, body = self.parse_frontmatter(raw_content)
        sop_id = meta.get("sop_id", os.path.splitext(os.path.basename(file_path))[0])
        title = meta.get("title", "Disaster Management SOP")
        category = meta.get("category", "General Relief")
        hazard_type = meta.get("hazard_type", "ALL")
        source_agency = meta.get("source_agency", "Disaster Management Authority")

        # Split document by top-level sections (## headers)
        section_pattern = r"(^##\s+.*$)"
        splits = re.split(section_pattern, body, flags=re.MULTILINE)

        chunks: List[SOPChunk] = []
        chunk_idx = 0

        # Handle introduction/header before first ## section
        if splits and splits[0].strip():
            intro_text = self.clean_text(splits[0])
            if len(intro_text) > 40:
                header_context = f"SOP Document: {sop_id} | {title} | Section: Overview"
                formatted_content = f"{header_context}\n\n{intro_text}"
                chunks.append(
                    SOPChunk(
                        chunk_id=f"{sop_id}-chunk-{chunk_idx}",
                        sop_id=sop_id,
                        title=title,
                        category=category,
                        hazard_type=hazard_type,
                        source_agency=source_agency,
                        section_title="Overview",
                        chunk_index=chunk_idx,
                        content=formatted_content,
                        raw_text=intro_text
                    )
                )
                chunk_idx += 1

        # Process pairs of (header, content)
        for i in range(1, len(splits), 2):
            header = splits[i].replace("##", "").strip()
            content = splits[i + 1].strip() if i + 1 < len(splits) else ""
            cleaned_content = self.clean_text(content)

            if not cleaned_content:
                continue

            # Context enrichment: prepend SOP ID, title and section header to chunk content
            header_context = f"SOP Document: {sop_id} | {title} | Section: {header}"
            formatted_content = f"{header_context}\n\n{cleaned_content}"

            chunks.append(
                SOPChunk(
                    chunk_id=f"{sop_id}-chunk-{chunk_idx}",
                    sop_id=sop_id,
                    title=title,
                    category=category,
                    hazard_type=hazard_type,
                    source_agency=source_agency,
                    section_title=header,
                    chunk_index=chunk_idx,
                    content=formatted_content,
                    raw_text=cleaned_content
                )
            )
            chunk_idx += 1

        return chunks

    def load_all_chunks(self) -> List[SOPChunk]:
        """Loads and chunks all markdown files from the sops directory."""
        if not os.path.exists(self.sops_dir):
            raise FileNotFoundError(f"SOPs directory not found: {self.sops_dir}")

        all_chunks: List[SOPChunk] = []
        md_files = [f for f in os.listdir(self.sops_dir) if f.endswith(".md")]
        md_files.sort()

        for filename in md_files:
            file_path = os.path.join(self.sops_dir, filename)
            doc_chunks = self.chunk_document(file_path)
            all_chunks.extend(doc_chunks)

        return all_chunks


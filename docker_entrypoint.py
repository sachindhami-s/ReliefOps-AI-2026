"""
ReliefOps AI — Non-Destructive Container Startup & Initialization Entrypoint
Ensures SQLite and ChromaDB are safely checked before launching Streamlit:
- If /app/data/reliefops.db already exists, preserves it 100% untouched without reseeding.
- If /app/data/reliefops.db does not exist, initializes schema and seeds baseline data.
- Initializes ChromaDB SOP embeddings only when the collection is empty (count == 0),
  never deleting or recreating existing collections or mutating an existing SQLite DB.
"""

import os
import sys
from typing import Any, Dict, List, Optional

from backend.database.db_manager import DatabaseManager
from backend.database.seeder import seed_database
from backend.rag.document_loader import SOPDocumentLoader
from backend.rag.vector_store import ChromaVectorStore


def ensure_non_destructive_initialization(
    db_path: Optional[str] = None,
    chromadb_path: Optional[str] = None,
    sops_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Performs non-destructive startup checks for SQLite and ChromaDB.

    Returns a dictionary summarizing actions taken:
      - db_existed (bool): True if database file already existed prior to check
      - db_seeded (bool): True only if database did not exist and was newly seeded
      - chroma_existing_count (int): Number of chunks present in ChromaDB before check
      - chroma_indexed (bool): True only if ChromaDB collection was empty and newly indexed
      - sop_files_found (int): Number of SOP markdown files verified in sops_dir
    """
    base_dir = os.path.abspath(os.path.dirname(__file__))

    if db_path is None:
        env_db = os.getenv("DATABASE_PATH", "").strip()
        if env_db:
            db_path = env_db if os.path.isabs(env_db) else os.path.join(base_dir, env_db)
        else:
            db_path = os.path.join(base_dir, "data", "reliefops.db")
    resolved_db_path = os.path.abspath(db_path)

    if chromadb_path is None:
        env_chroma = os.getenv("CHROMADB_PATH", "").strip()
        if env_chroma:
            chromadb_path = env_chroma if os.path.isabs(env_chroma) else os.path.join(base_dir, env_chroma)
        else:
            chromadb_path = os.path.join(base_dir, "data", "chromadb")
    resolved_chroma_path = os.path.abspath(chromadb_path)

    if sops_dir is None:
        env_sops = os.getenv("SOP_DIR", "").strip()
        if env_sops:
            sops_dir = env_sops if os.path.isabs(env_sops) else os.path.join(base_dir, env_sops)
        else:
            sops_dir = os.path.join(base_dir, "data", "sops")
    resolved_sops_dir = os.path.abspath(sops_dir)

    status: Dict[str, Any] = {
        "db_path": resolved_db_path,
        "chromadb_path": resolved_chroma_path,
        "sops_dir": resolved_sops_dir,
        "db_existed": False,
        "db_seeded": False,
        "chroma_existing_count": 0,
        "chroma_indexed": False,
        "sop_files_found": 0,
    }

    # 1. Verify SOP documents directory exists and contains markdown SOPs
    if not os.path.isdir(resolved_sops_dir):
        raise FileNotFoundError(
            f"[ENTRYPOINT ERROR] SOP directory not found at '{resolved_sops_dir}'. "
            "Cannot start without authoritative SOP documents."
        )

    md_files = [f for f in os.listdir(resolved_sops_dir) if f.endswith(".md")]
    if not md_files:
        raise RuntimeError(
            f"[ENTRYPOINT ERROR] No SOP markdown (.md) documents found in '{resolved_sops_dir}'."
        )
    status["sop_files_found"] = len(md_files)

    # 2. Non-destructive SQLite Database Check
    db_exists = os.path.isfile(resolved_db_path) and os.path.getsize(resolved_db_path) > 0
    if db_exists:
        status["db_existed"] = True
        status["db_seeded"] = False
        print(
            f"[ENTRYPOINT] Existing SQLite database detected at '{resolved_db_path}' "
            f"({os.path.getsize(resolved_db_path)} bytes). Preserving untouched without reseeding."
        )
    else:
        print(
            f"[ENTRYPOINT] SQLite database not found at '{resolved_db_path}'. "
            "Initializing schema and seeding baseline disaster data..."
        )
        os.makedirs(os.path.dirname(resolved_db_path), exist_ok=True)
        db = DatabaseManager(db_path=resolved_db_path)
        try:
            seed_database(db)
            status["db_seeded"] = True
            print(f"[ENTRYPOINT] SQLite database initialized at '{resolved_db_path}'.")
        finally:
            db.close()

    # 3. Non-destructive ChromaDB Vector Store Check
    vector_store = ChromaVectorStore(persist_dir=resolved_chroma_path)
    existing_count = vector_store.count()
    status["chroma_existing_count"] = existing_count

    if existing_count > 0:
        status["chroma_indexed"] = False
        print(
            f"[ENTRYPOINT] Existing ChromaDB collection '{vector_store.collection_name}' detected "
            f"({existing_count} indexed chunks at '{resolved_chroma_path}'). Preserving untouched."
        )
    else:
        print(
            f"[ENTRYPOINT] ChromaDB collection '{vector_store.collection_name}' is empty. "
            f"Indexing SOP documents from '{resolved_sops_dir}'..."
        )
        loader = SOPDocumentLoader(sops_dir=resolved_sops_dir)
        chunks = loader.load_all_chunks()
        indexed_count = vector_store.index_chunks(chunks)
        status["chroma_indexed"] = True
        status["chroma_indexed_count"] = indexed_count
        print(f"[ENTRYPOINT] Indexed {indexed_count} SOP chunks into ChromaDB at '{resolved_chroma_path}'.")

    return status


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint that validates initialization before launching Streamlit or a custom command."""
    args = list(sys.argv[1:] if argv is None else argv)

    check_only = False
    if "--check-only" in args:
        check_only = True
        args.remove("--check-only")

    try:
        ensure_non_destructive_initialization()
    except Exception as exc:
        print(f"[ENTRYPOINT FATAL] Initialization failed: {exc}", file=sys.stderr)
        return 1

    if check_only:
        print("[ENTRYPOINT] Non-destructive startup verification succeeded (--check-only).")
        return 0

    if not args:
        port = os.getenv("STREAMLIT_SERVER_PORT", "8501")
        address = os.getenv("STREAMLIT_SERVER_ADDRESS", "0.0.0.0")
        headless = os.getenv("STREAMLIT_SERVER_HEADLESS", "true")
        args = [
            "streamlit",
            "run",
            "app.py",
            f"--server.port={port}",
            f"--server.address={address}",
            f"--server.headless={headless}",
        ]

    print(f"[ENTRYPOINT] Starting application: {' '.join(args)}")
    os.execvp(args[0], args)
    return 0


if __name__ == "__main__":
    sys.exit(main())

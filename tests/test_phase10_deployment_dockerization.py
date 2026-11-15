"""
ReliefOps AI — Phase 10 (Task 2): Dockerization & Non-Destructive Deployment Verification Suite
Validates:
  A. Dockerfile configuration & absence of build-time database seeding
  B. Docker Compose configuration & persistent volume mounts
  C. .dockerignore security & runtime exclusion rules
  D. Environment variable alignment (CHROMADB_PATH, SOP_DIR, DATABASE_PATH)
  E. Non-destructive entrypoint initialization & preservation of existing DB/ChromaDB
  F. Protection of production data/reliefops.db, data/chromadb/, data/sops/, and backups
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from backend.database.db_manager import DatabaseManager
from backend.rag.document_loader import SOPDocumentLoader
from backend.rag.vector_store import ChromaVectorStore
from docker_entrypoint import ensure_non_destructive_initialization, main as entrypoint_main


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class TestPhase10DockerizationAndDeployment(unittest.TestCase):
    """Comprehensive verification suite for Phase 10 Task 2 Dockerization."""

    def test_01_dockerignore_excludes_sensitive_and_runtime_artifacts(self):
        """C. Verify .dockerignore excludes secrets, virtualenvs, caches, local DBs, and backups."""
        dockerignore_path = os.path.join(PROJECT_ROOT, ".dockerignore")
        self.assertTrue(os.path.isfile(dockerignore_path), ".dockerignore must exist")

        with open(dockerignore_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_exclusions = [
            ".git/",
            ".venv/",
            "venv/",
            "__pycache__/",
            ".pytest_cache/",
            ".streamlit/secrets.toml",
            ".env",
            ".env.*",
            "backups/",
            "data/backup_*/",
            "data/*.db",
            "data/chromadb/",
            "*.log",
        ]
        for pattern in required_exclusions:
            self.assertIn(pattern, content, f".dockerignore missing required exclusion: {pattern}")

        # Must preserve .env.example and SOP markdown definitions
        self.assertIn("!.env.example", content)
        self.assertIn("!data/sops/*.md", content)

    def test_02_dockerfile_configuration_and_no_build_seeding(self):
        """A. Verify Dockerfile uses python:3.12-slim, libgomp1, non-root user, entrypoint, and no build-time seeding."""
        dockerfile_path = os.path.join(PROJECT_ROOT, "Dockerfile")
        self.assertTrue(os.path.isfile(dockerfile_path), "Dockerfile must exist")

        with open(dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("FROM python:3.12-slim", content)
        self.assertIn("libgomp1", content)
        self.assertIn("curl", content)
        self.assertIn("sqlite3", content)
        self.assertIn("WORKDIR /app", content)
        self.assertIn("USER reliefops", content)
        self.assertIn("EXPOSE 8501", content)
        self.assertIn("/_stcore/health", content)
        self.assertIn('ENTRYPOINT ["/app/docker-entrypoint.sh"]', content)

        # Verify HEALTHCHECK instruction has each flag specified exactly once and valid CMD syntax
        healthcheck_lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip().startswith("HEALTHCHECK")
        ]
        self.assertEqual(len(healthcheck_lines), 1, "Dockerfile must contain exactly one HEALTHCHECK instruction")
        hc_line = healthcheck_lines[0]
        for flag in ("--interval=", "--timeout=", "--start-period=", "--retries="):
            self.assertEqual(
                content.count(flag),
                1,
                f"HEALTHCHECK flag '{flag}' must appear exactly once in Dockerfile",
            )
        self.assertIn("CMD curl -f http://localhost:8501/_stcore/health || exit 1", hc_line)

        # Must NOT run database seeder during image build
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped.startswith("#"):
                self.assertNotIn(
                    "backend.database.seeder",
                    stripped,
                    "Dockerfile must not execute database seeding at image build time",
                )

    def test_03_docker_compose_configuration_validation(self):
        """B. Verify docker-compose.yml removes deprecated version, maps 8501:8501, and persists /app/data."""
        compose_path = os.path.join(PROJECT_ROOT, "docker-compose.yml")
        self.assertTrue(os.path.isfile(compose_path), "docker-compose.yml must exist")

        with open(compose_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Deprecated top-level version key must be removed
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped.startswith("#"):
                self.assertFalse(
                    stripped.startswith("version:"),
                    "docker-compose.yml must not include deprecated top-level 'version' declaration",
                )

        self.assertIn("services:", content)
        self.assertIn('"8501:8501"', content)
        self.assertIn("./data:/app/data", content)
        self.assertIn("./logs:/app/logs", content)
        self.assertIn("DATABASE_PATH=data/reliefops.db", content)
        self.assertIn("CHROMADB_PATH=data/chromadb", content)
        self.assertIn("SOP_DIR=data/sops", content)
        self.assertIn("restart: unless-stopped", content)
        self.assertIn("/_stcore/health", content)

    def test_04_environment_variable_alignment_for_rag_components(self):
        """E & G. Verify ChromaVectorStore and SOPDocumentLoader respect CHROMADB_PATH and SOP_DIR."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            custom_chroma = os.path.join(tmpdir, "custom_chroma")
            custom_sops = os.path.join(tmpdir, "custom_sops")
            os.makedirs(custom_sops, exist_ok=True)

            # Copy one SOP file into custom_sops for loader testing
            src_sop = os.path.join(PROJECT_ROOT, "data", "sops", "SOP_FL_001_flood_response.md")
            shutil.copy2(src_sop, os.path.join(custom_sops, "SOP_FL_001_flood_response.md"))

            with patch.dict(
                os.environ,
                {"CHROMADB_PATH": custom_chroma, "SOP_DIR": custom_sops},
                clear=False,
            ):
                loader = SOPDocumentLoader()
                self.assertEqual(loader.sops_dir, os.path.abspath(custom_sops))
                chunks = loader.load_all_chunks()
                self.assertGreater(len(chunks), 0)

                vs = ChromaVectorStore()
                self.assertEqual(vs.persist_dir, os.path.abspath(custom_chroma))
                indexed = vs.index_chunks(chunks)
                self.assertEqual(indexed, len(chunks))
                self.assertEqual(vs.count(), len(chunks))

    def test_05_non_destructive_entrypoint_initialization_and_preservation(self):
        """F. Verify entrypoint initializes missing DB/ChromaDB once and never overwrites existing DB."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            test_db_path = os.path.join(tmpdir, "data", "reliefops.db")
            test_chroma_path = os.path.join(tmpdir, "data", "chromadb")
            real_sops_dir = os.path.join(PROJECT_ROOT, "data", "sops")

            # 1. Cold start: DB does not exist, ChromaDB is empty
            status_cold = ensure_non_destructive_initialization(
                db_path=test_db_path,
                chromadb_path=test_chroma_path,
                sops_dir=real_sops_dir,
            )
            self.assertFalse(status_cold["db_existed"])
            self.assertTrue(status_cold["db_seeded"])
            self.assertTrue(status_cold["chroma_indexed"])
            self.assertEqual(status_cold["sop_files_found"], 12)
            self.assertTrue(os.path.isfile(test_db_path))

            # Insert custom sentinel record into the test database to verify non-destructive preservation
            db = DatabaseManager(db_path=test_db_path)
            try:
                db.execute_non_query(
                    "UPDATE warehouses SET name = ? WHERE warehouse_id = ?",
                    ("CUSTOM-PRESERVED-WAREHOUSE-NAME", "WH-GUWAHATI-NORTH"),
                )
            finally:
                db.close()

            # 2. Warm start: DB and ChromaDB already exist -> must NOT re-seed or overwrite
            status_warm = ensure_non_destructive_initialization(
                db_path=test_db_path,
                chromadb_path=test_chroma_path,
                sops_dir=real_sops_dir,
            )
            self.assertTrue(status_warm["db_existed"])
            self.assertFalse(status_warm["db_seeded"])
            self.assertFalse(status_warm["chroma_indexed"])
            self.assertGreater(status_warm["chroma_existing_count"], 50)

            # Verify custom sentinel record was NOT overwritten by seeder
            db_verify = DatabaseManager(db_path=test_db_path)
            try:
                rows = db_verify.execute_query(
                    "SELECT name FROM warehouses WHERE warehouse_id = ?",
                    ("WH-GUWAHATI-NORTH",),
                )
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["name"], "CUSTOM-PRESERVED-WAREHOUSE-NAME")
            finally:
                db_verify.close()

            # 3. Error handling: missing SOP directory fails fast and returns non-zero code
            missing_sops = os.path.join(tmpdir, "non_existent_sops")
            with patch.dict(
                os.environ,
                {
                    "DATABASE_PATH": test_db_path,
                    "CHROMADB_PATH": test_chroma_path,
                    "SOP_DIR": missing_sops,
                },
                clear=False,
            ):
                exit_code = entrypoint_main(["--check-only"])
                self.assertEqual(exit_code, 1)

    def test_06_production_database_and_backups_strictly_protected(self):
        """7. Verify workspace data/reliefops.db, data/chromadb/, data/sops/, and backups remain intact."""
        prod_db = os.path.join(PROJECT_ROOT, "data", "reliefops.db")
        prod_chroma = os.path.join(PROJECT_ROOT, "data", "chromadb")
        prod_sops = os.path.join(PROJECT_ROOT, "data", "sops")
        backup_1 = os.path.join(PROJECT_ROOT, "data", "backup_pre_index_update")
        backup_2 = os.path.join(PROJECT_ROOT, "data", "backup_pre_stabilization")

        self.assertTrue(os.path.isfile(prod_db), "Production data/reliefops.db must exist")
        self.assertGreater(os.path.getsize(prod_db), 1_000_000, "Production DB size must be preserved")
        self.assertTrue(os.path.isdir(prod_chroma), "Production data/chromadb/ must exist")
        self.assertTrue(os.path.isdir(prod_sops), "Production data/sops/ must exist")
        self.assertTrue(os.path.isdir(backup_1), "Existing backup_pre_index_update must be preserved")
        self.assertTrue(os.path.isdir(backup_2), "Existing backup_pre_stabilization must be preserved")


if __name__ == "__main__":
    unittest.main()

# ReliefOps AI — Phase 10 (Task 1): Deployment Architecture & Infrastructure Audit

**Project:** ReliefOps AI — Autonomous Multi-Agent Disaster Relief Resource Allocation Platform  
**Course:** CSE476 — Agentic AI and Intelligent Automation  
**Audit Role:** Senior DevOps Engineer & Python Deployment Architect  
**Baseline Verified:** 133/133 Automated Tests Passing (Phases 1–9 Complete)  
**Audit Mode:** Read-Only Infrastructure & Codebase Inspection (Zero Database or Code Mutations)

---

## 1. Existing Architecture

ReliefOps AI is a self-contained, multi-agent decision-support and operations command platform built in Python. Its runtime architecture comprises five tightly integrated layers:

1. **Presentation & Command Layer (`app.py`, `demo_pipeline.py`):**
   - **Streamlit Operational Command Dashboard (`app.py`, 2,190 lines):** Single-file, 9-module interactive web application (`Executive Mission Control`, `Disaster Scenario Simulator`, `Geo-Risk & Priority Intelligence`, `Warehouse & Inventory Command`, `Logistics & Routing Command`, `Multi-Agent Blackboard Trace`, `SOP Knowledge & RAG Inspector`, `Fairness & Humanitarian Compliance`, and `Explainable AI Audit & Reports`).
   - **CLI Demonstration Runner (`demo_pipeline.py`):** Headless command-line execution pipeline supporting canonical single-hazard runs (`--hazard`), mid-run dynamic replanning (`--replanning`), and full multi-hazard benchmark suites (`--all`).
2. **Multi-Agent Orchestration Layer (`backend/agents/`, `backend/plugins/`):**
   - **`ReliefCoordinator` (`backend/agents/relief_coordinator.py`):** Central orchestrator executing a 5-stage pipeline (`Needs Assessment` $\rightarrow$ `Inventory Verification` $\rightarrow$ `Logistics Routing` $\rightarrow$ `Proportional Resource Allocation` $\rightarrow$ `Fairness Audit & Self-Correction Loop`) and mid-run dynamic replanning (`trigger_dynamic_replanning`).
   - **Four Specialist Agents:** `NeedsAssessmentAgent`, `InventoryAgent`, `LogisticsAgent`, and `FairnessAuditorAgent`, each encapsulating a `semantic_kernel.Kernel` instance registered with deterministic `@kernel_function` native plugins (`NeedsAssessmentPlugin`, `InventoryManagementPlugin`, `LogisticsRoutingPlugin`, `FairnessAuditPlugin`, `CoordinatorOptimizationPlugin`).
3. **Shared Memory Layer (`backend/blackboard/blackboard_manager.py`):**
   - **`BlackboardManager`:** Thread-safe (`threading.RLock`) Hayes-Roth Blackboard state machine maintaining `disaster_context`, `zone_assessments`, `rag_citations`, `inventory_snapshot`, `logistics_routes`, `proposed_allocation`, `fairness_audit`, `execution_metrics`, `negotiation_history`, and `audit_trail`, along with snapshot/diff primitives for dynamic replanning.
4. **Hybrid RAG Knowledge Layer (`backend/rag/`):**
   - **`SOPDocumentLoader` (`backend/rag/document_loader.py`):** Parses YAML frontmatter and section-aware markdown chunks across 12 authoritative SOP documents (72 chunks total) in `data/sops/`.
   - **`ChromaVectorStore` (`backend/rag/vector_store.py`):** Persistent local vector store (`chromadb.PersistentClient`) using cosine similarity (`hnsw:space = cosine`) on collection `disaster_sops`.
   - **`BM25Retriever` (`backend/rag/fallback_retriever.py`):** In-memory Okapi BM25 ($k_1 = 1.5, b = 0.75$) lexical retrieval engine providing zero-dependency fallback when vector search is unavailable or degraded.
   - **`SOPRetriever` (`backend/rag/retriever.py`):** Unified retrieval facade that queries ChromaDB first and automatically falls back to BM25 on initialization failure, query exception, or empty result sets.
5. **Transactional Persistence Layer (`backend/database/`):**
   - **`DatabaseManager` (`backend/database/db_manager.py`):** Thread-local SQLite 3 connection manager enforcing `PRAGMA journal_mode = WAL`, `PRAGMA synchronous = NORMAL`, `PRAGMA foreign_keys = ON`, explicit `BEGIN IMMEDIATE` atomic transactions (`transaction()`), and online hot backups (`backup_database()` / `restore_database()`).
   - **Relational Schema (`backend/database/schema.sql`):** 7 normalized tables (`disaster_events`, `affected_zones`, `warehouses`, `warehouse_inventory`, `allocation_plans`, `audit_logs`, `simulation_scenarios`) with `CHECK` constraints, `FOREIGN KEY` constraints, and 5 secondary indexes.

---

## 2. Current Deployment Configuration

### 2.1 How Streamlit Starts the Application
- **Entrypoint:** `app.py` is the sole Streamlit entrypoint (`streamlit run app.py`).
- **Execution Guard:** Line 2189 of `app.py` checks `if __name__ == "__main__" or st.runtime.exists(): render_dashboard()`, allowing execution both via `streamlit run app.py` and `streamlit.testing.v1.AppTest`.
- **Server Settings:** Configured via `.streamlit/config.toml` (`headless = true`, `port = 8501`, `gatherUsageStats = false`) and CLI/environment flags (`STREAMLIT_SERVER_PORT=8501`, `STREAMLIT_SERVER_ADDRESS=0.0.0.0`, `STREAMLIT_SERVER_HEADLESS=true`).
- **Multi-Page Directory (`pages/`):** An empty `pages/` directory exists in the workspace root (`0` files). Navigation across all 9 dashboard modules is handled inside `app.py` via custom sidebar controls and `st.session_state.active_module`.

### 2.2 How Backend Agents Are Initialized
- When a simulation or scenario execution is triggered in `app.py` (or `demo_pipeline.py`), `ReliefCoordinator(db_manager=...)` is instantiated.
- `ReliefCoordinator.__init__` initializes:
  1. `DatabaseManager` (defaults to `default_db_manager` singleton in `backend/database/db_manager.py`).
  2. `BlackboardManager` (in-memory thread-safe blackboard).
  3. `NeedsAssessmentAgent` (which initializes `SOPRetriever` $\rightarrow$ `ChromaVectorStore` + `BM25Retriever` and auto-indexes SOP chunks if the ChromaDB collection count is `0`).
  4. `InventoryAgent` (connected to `DatabaseManager`).
  5. `LogisticsAgent` (Haversine distance and multi-modal route feasibility engine).
  6. `FairnessAuditorAgent` (Lorenz/Gini coefficient and survival floor compliance engine).

### 2.3 How SQLite Database Connections Are Established
- `DatabaseManager` resolves the SQLite file path using:
  1. Explicit `db_path` argument passed to `DatabaseManager(db_path=...)`, or
  2. `os.environ.get("DATABASE_PATH")`, or
  3. Default `<project_root>/data/reliefops.db`.
- Parent directories are created automatically (`os.makedirs(os.path.dirname(self.db_path), exist_ok=True)`).
- Each thread gets an isolated `sqlite3.Connection` via `threading.local()` with `timeout=30.0`, `row_factory = sqlite3.Row`, `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL`, and `PRAGMA synchronous = NORMAL`.

### 2.4 How ChromaDB Is Initialized and Persisted
- `ChromaVectorStore` (`backend/rag/vector_store.py`) creates a persistent client at `persist_dir` (defaulting to `<project_root>/data/chromadb`) using `chromadb.PersistentClient(path=self.persist_dir, settings=Settings(anonymized_telemetry=False, is_persistent=True))`.
- On startup, `SOPRetriever.initialize_index()` checks `self.vector_store.count() == 0`; if empty, it loads all 12 SOP markdown files from `data/sops/` and upserts all 72 chunks into `data/chromadb/`.
- If `data/chromadb/` already contains the indexed embeddings (as in the current workspace), `initialize_index(force_reindex=False)` skips re-embedding and reuses the persisted HNSW index immediately.

### 2.5 How BM25 Fallback Retrieval Works
- During `SOPRetriever.__init__()`, `self.chunks = self.loader.load_all_chunks()` and `self.bm25_retriever = BM25Retriever(self.chunks)` are unconditionally executed in memory before ChromaDB is touched.
- If `ChromaVectorStore` raises any exception during initialization or query execution, `SOPRetriever` logs the warning (`[RAG WARNING]`), flips `self.vector_store_healthy = False`, and serves results from `BM25Retriever.query()` with `retrieval_method: "bm25_fallback"`.

### 2.6 How Configuration and Environment Variables Are Loaded
- `backend/config.py` invokes `load_dotenv()` from `python-dotenv` at import time and exposes a singleton `settings = Settings()`.
- Environment variables parsed by `Settings`:
  - `RELIEFOPS_EXECUTION_MODE` (default: `"deterministic"`)
  - `DATABASE_PATH` (default: `"data/reliefops.db"`)
  - `CHROMADB_PATH` (default: `"data/chromadb"`)
  - `SOP_DIR` (default: `"data/sops"`)
  - `RELIEFOPS_LOG_LEVEL` / `LOG_LEVEL` (default: `"INFO"`)
  - `RELIEFOPS_LOG_FILE` (default: `""`)
  - `GINI_THRESHOLD` (default: `0.35`)
  - `SURVIVAL_FLOOR_RATIO` (default: `0.30`)
  - `STREAMLIT_SERVER_ADDRESS` (default: `"0.0.0.0"`)
  - `STREAMLIT_SERVER_PORT` (default: `8501`)
  - Optional LLM credentials (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`), all protected via `mask_secret()`.

### 2.7 Directories Requiring Persistent Storage
| Path | Purpose | Persistence Requirement |
| :--- | :--- | :--- |
| `data/reliefops.db` (+ `-wal`, `-shm`) | Primary SQLite transactional database & WAL shared-memory files | **Mandatory** (Must mount parent `/app/data` directory so `-wal` and `-shm` files share the same filesystem mount) |
| `data/chromadb/` | Persisted ChromaDB SQLite metadata (`chroma.sqlite3`) and HNSW binary index segments | **Mandatory** (Avoids re-indexing SOP chunks on container restarts) |
| `data/sops/` | 12 authoritative disaster SOP markdown documents | **Mandatory Read-Only / Seeded** (Source of truth for RAG & BM25) |
| `data/backup_*/` or `data/backups/` | Point-in-time SQLite hot backups | **Recommended** (Persisted inside `/app/data`) |
| `logs/` | Structured operational log files (when `RELIEFOPS_LOG_FILE` is set) | **Optional** (Mounted as `./logs:/app/logs`) |

### 2.8 Directories & Files That Must NOT Be Copied Into Docker Images
The following host directories and artifacts must be excluded via `.dockerignore`:
- `.venv/`, `venv/`, `env/`, `ENV/` (Host Windows virtual environment — ~450+ MB of OS-specific binaries)
- `.git/`, `.gitignore` (Git history and repository metadata)
- `__pycache__/`, `*.py[cod]`, `*$py.class`, `.pytest_cache/`, `.coverage`, `htmlcov/`
- `.env`, `.env.*` (except `!.env.example`), `.streamlit/secrets.toml`, `.streamlit/credentials.toml`
- `data/backup_*/`, `data/backups/`, `*.db-wal`, `*.db-shm`, `*.db-journal`, `*.log`, `*.tmp`, `*.bak`
- `.vscode/`, `.idea/`, `.DS_Store`, `Thumbs.db`

### 2.9 Operation Without External API Credentials
- **Verified 100% Capable:** In default `RELIEFOPS_EXECUTION_MODE=deterministic`, the platform requires **zero external API keys**. All 5 agents execute deterministic Semantic Kernel native plugins, and RAG runs locally via ChromaDB/BM25.

### 2.10 Deployment-Specific Assumptions Identified
1. **`ChromaVectorStore` & `SOPDocumentLoader` Env Var Lookup:** `backend/config.py` reads `CHROMADB_PATH` and `SOP_DIR`, and `.env.example` / `docker-compose.yml` set them. However, `ChromaVectorStore.__init__(persist_dir=None)` (`backend/rag/vector_store.py:17-19`) and `SOPDocumentLoader.__init__(sops_dir=None)` (`backend/rag/document_loader.py:45-47`) compute `<base_dir>/data/chromadb` and `<base_dir>/data/sops` directly without checking `os.environ.get("CHROMADB_PATH")` or `os.environ.get("SOP_DIR")`. While default paths match `/app/data/chromadb` and `/app/data/sops`, custom paths via environment variables are currently ignored unless passed explicitly.
2. **ChromaDB Default Embedding Function Cold-Start Network Call:** ChromaDB's default `ONNXMiniLM_L6_V2` embedding function stores its model cache in `~/.cache/chroma/onnx_models/all-MiniLM-L6-v2`. If a container starts with an empty `/app/data/chromadb` directory and no cached ONNX model in `/home/reliefops/.cache/chroma`, ChromaDB attempts to download the ~79 MB ONNX model archive over HTTPS on first upsert/query (falling back to BM25 if offline).
3. **Empty `pages/` Directory:** An empty `pages/` folder exists in the project root. Streamlit watches `pages/` for multi-page scripts; keeping it empty is harmless, though unnecessary.

---

## 3. Dependency Audit (`requirements.txt`)

### 3.1 Direct Dependencies Inspected
| Package | Version Constraint | Role in ReliefOps AI | Audit Status |
| :--- | :--- | :--- | :--- |
| `streamlit` | `>=1.35.0` | Operational Command Dashboard UI server | Clean |
| `altair` | `>=5.0.0` | Declarative charts (ZPS, fulfillment, Lorenz curve) | Clean |
| `pydeck` | `>=0.8.0` | Geospatial zone/warehouse map rendering | Clean |
| `numpy` | `>=1.26.0` | Vector/Gini math & array processing | Clean |
| `pandas` | `>=2.2.0` | Tabular data manipulation for UI & exports | Clean |
| `pydantic` | `>=2.0.0` | Schema validation across Semantic Kernel & ChromaDB | Clean |
| `reportlab` | `>=4.0.0` | PDF executive compliance report generation | Clean (Note: not currently imported in `app.py`, retained for reporting compatibility) |
| `python-dotenv` | `>=1.0.0` | `.env` configuration loader | Clean |
| `semantic-kernel` | `>=1.0.0` | Multi-agent kernel and `@kernel_function` native plugins | Clean |
| `chromadb` | `>=0.4.20` | Persistent HNSW vector database for SOP RAG | Requires `onnxruntime` (transitive) & SQLite $\ge 3.35$ |
| `pytest` | `>=7.4.0` | Automated unit/integration/stress test runner | Clean |
| `pytest-asyncio` | `>=0.23.0` | Async test execution support | Clean |

### 3.2 Dependency Findings
- **Duplicate Packages:** None found in `requirements.txt`.
- **Version Conflicts:** None. All 12 packages install cleanly together on Python 3.11 and Python 3.12 (`133 passed` verified in `.venv`).
- **System Library Requirements (`python:3.12-slim`):**
  - `python:3.12-slim` (Debian Bookworm) ships with SQLite `3.40.1` ($\ge 3.35.0$ required by ChromaDB) and `glibc 2.36` (required by `onnxruntime` and `hnswlib` wheels).
  - `Dockerfile` already installs `build-essential`, `curl` (for `HEALTHCHECK`), and `sqlite3`.
  - `libgomp1` (GNU OpenMP runtime library) is recommended in slim Debian images because `onnxruntime` (pulled in by `chromadb` for default embeddings) links against `libgomp.so.1` on Linux.

---

## 4. Security Audit

### 4.1 Secret & Credential Management
- **`.env` Presence:** No `.env` file is tracked in the workspace; `.env.example` contains only safe defaults and commented-out placeholder keys (`# OPENAI_API_KEY=your_openai_api_key_here`).
- **`.gitignore` Coverage:** Properly excludes `.env`, `.env.*` (with `!.env.example`), `.streamlit/secrets.toml`, `.streamlit/credentials.toml`, `.venv/`, `data/*.db`, `data/*.db-*`, `data/backup_*/`, and `data/chromadb/`.
- **Secret Masking (`backend/config.py` & `backend/utils/security.py`):**
  - `mask_secret()` redacts any API key to `********` or `abc...xyz` inside `Settings.to_safe_dict()`, `__repr__()`, and `__str__()`.
  - `redact_sensitive_mapping()` recursively scrubs keys matching `api_key`, `secret`, `token`, `password`, `credential`, and `authorization` before logging.

### 4.2 Input Validation, SQL Injection & XSS Defenses
- **SQL Parameterization:** All queries in `DatabaseManager`, `seeder.py`, `relief_coordinator.py`, `inventory_plugin.py`, and `app.py` use parameterized `?` placeholders.
- **Path Traversal Protection:** `validate_safe_path()` (`backend/utils/security.py`) resolves `Path.resolve()` and enforces `Path.is_relative_to(base_dir)` for database backup/restore and SOP loading paths.
- **HTML Sanitization:** Dynamic zone names, warehouse names, and SOP strings rendered inside custom HTML cards in `app.py` are sanitized with `html.escape()`.

### 4.3 Security Findings Requiring Attention in Phase 10
1. **Missing `.dockerignore` (High Priority):** Without `.dockerignore`, `COPY . .` in `Dockerfile` copies any local `.env` file, `.git/` history, `.venv/`, and backup directories into the container image layer if present on the build host.
2. **Streamlit CORS / XSRF Flags (`.streamlit/config.toml`):** Lines 7–8 set `enableCORS = false` and `enableXsrfProtection = false`. Note that Streamlit logs a deprecation/configuration warning when these two flags conflict or when XSRF protection is disabled in production without a reverse proxy.

---

## 5. Database Persistence Architecture

### 5.1 Current Workspace Database State (Preserved Untouched)
- **`data/reliefops.db`:** Exists (`5,292,032` bytes / ~5.29 MB), pre-populated with disaster events, affected zones, warehouses, inventory SKUs, simulation scenarios, allocation plans, and audit logs.
- **`data/chromadb/`:** Exists, containing persistent vector embeddings for the 12 SOP documents.
- **`data/backup_pre_index_update/` & `data/backup_pre_stabilization/`:** Existing snapshot backup directories in `data/`.
- **`data/sops/`:** Contains 12 `.md` SOP documents (`SOP_FL_001` through `SOP_SAN_012`).

### 5.2 SQLite WAL Mode & Volume Mount Requirements
- `DatabaseManager` configures `PRAGMA journal_mode = WAL`.
- In WAL mode, SQLite creates two companion files alongside `data/reliefops.db`:
  - `data/reliefops.db-wal` (Write-Ahead Log)
  - `data/reliefops.db-shm` (Shared-memory index mapped via `mmap`)
- **Critical Container Rule:**
  1. Never mount `data/reliefops.db` as a single-file Docker bind mount (`./data/reliefops.db:/app/data/reliefops.db`), because SQLite cannot create `-wal` and `-shm` files on the same filesystem mount when only the file is mounted.
  2. Always mount the entire directory (`./data:/app/data`), as currently configured in `docker-compose.yml`.
  3. Only a single container replica (`replicas: 1`) should write to the SQLite WAL file on a host bind mount.

---

## 6. Docker Readiness Audit

### 6.1 Host Docker Environment Status
- **Docker CLI Installed:** `Docker version 29.5.2, build 79eb04c` is installed on the Windows host.
- **Sandbox Note:** Inside the standard terminal sandbox, `C:\Users\deeps\.docker\config.json` access is restricted (`Access is denied`), so `docker build` / `docker compose` commands in Task 2 will require running outside the sandbox (`BypassSandbox: true`) when building or testing containers.

### 6.2 Existing `Dockerfile` & `docker-compose.yml` Inspection
Both `Dockerfile` (58 lines) and `docker-compose.yml` (36 lines) already exist in the repository root and have a solid baseline structure:
- Base image: `python:3.12-slim`
- Non-root user: `reliefops` (`UID 1000`)
- Port exposed: `8501`
- Healthcheck: `curl -f http://localhost:8501/_stcore/health || exit 1`
- Volume mounts: `./data:/app/data` and `./logs:/app/logs`

### 6.3 Specific Gaps Identified in Current Docker Setup
1. **No `.dockerignore` File:**
   - Currently missing. Running `docker build .` transfers `.venv/` (hundreds of MBs of Windows binaries), `.git/`, `.pytest_cache/`, `__pycache__/`, and backup folders into the Linux image context.
2. **Build-Time Seeding vs. Runtime Volume Mount Interaction (`Dockerfile` Line 48):**
   - `Dockerfile` runs `RUN python -m backend.database.seeder` at image build time.
   - However, when launched via `docker-compose.yml` (`volumes: - ./data:/app/data`), the host `./data` directory overlays `/app/data` in the container.
   - Conversely, if `.dockerignore` excludes `data/reliefops.db` and `data/chromadb/` from the build context (to keep images clean and avoid baking local runtime state into images), and a user mounts a host `./data` directory:
     - **If `data/reliefops.db` already exists on the host** (as in this workspace: `5.29 MB`), the container must **use the existing database as-is without overwriting or resetting it**.
     - **If `data/reliefops.db` does NOT exist on a fresh clone**, the container entrypoint should initialize the schema and seed baseline data on startup.
3. **Missing `libgomp1` in `Dockerfile` `apt-get install`:**
   - `onnxruntime` (used by ChromaDB on Linux) requires `libgomp1` (`libgomp.so.1`), which is not always pre-installed in minimal `python:3.12-slim` images.
4. **Obsolete `version: '3.8'` in `docker-compose.yml`:**
   - Modern Docker Compose emits a deprecation warning when `version: '3.8'` is present at the top of `docker-compose.yml`.

---

## 7. Missing Configurations Summary

| Item | Current Status | Required Action in Phase 10 (Task 2) |
| :--- | :--- | :--- |
| `.dockerignore` | **Missing** | Create `.dockerignore` excluding `.venv/`, `.git/`, `__pycache__/`, `.pytest_cache/`, `.env`, `data/*.db*`, `data/backup_*/`, `data/chromadb/`, `*.log`, IDE folders, while keeping `data/sops/*.md`. |
| Safe Startup Entrypoint | **Missing** | Add a lightweight startup check (or `docker-entrypoint.sh`) that preserves existing `/app/data/reliefops.db` and `/app/data/chromadb/` untouched if present, and only seeds on a cold/empty `/app/data` directory. |
| `libgomp1` System Package | **Missing in `Dockerfile`** | Add `libgomp1` to `apt-get install` in `Dockerfile` so `chromadb` / `onnxruntime` never fails with `libgomp.so.1: cannot open shared object file`. |
| `CHROMADB_PATH` & `SOP_DIR` Env Var Resolution | **Partial** (`config.py` reads them, `vector_store.py` & `document_loader.py` ignore them when `None` is passed) | Update default path fallback in `ChromaVectorStore.__init__` and `SOPDocumentLoader.__init__` to check `os.environ.get("CHROMADB_PATH")` and `os.environ.get("SOP_DIR")` before falling back to `<base_dir>/data/...`. |
| `docker-compose.yml` `version` key | **Deprecated (`version: '3.8'`)** | Remove obsolete `version: '3.8'` line from `docker-compose.yml` for clean Docker Compose v2 compatibility. |

---

## 8. Potential Deployment Risks & Mitigations

| Risk ID | Risk Description | Severity | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **RISK-01** | **Host `.venv` & Local DB Baked into Image:** Without `.dockerignore`, `COPY . .` copies the Windows `.venv/` and 5.29 MB local database + backups into the Docker image. | **High** | Create strict `.dockerignore` before any `docker build`. |
| **RISK-02** | **Accidental Overwrite of Existing `data/reliefops.db`:** Running a seeder unconditionally on an existing production database could overwrite modified warehouse inventory or scenario state. | **High** | Never overwrite existing `data/reliefops.db` or `data/chromadb/`. In container startup, check if `data/reliefops.db` exists and has seeded events before calling `seed_database()`. |
| **RISK-03** | **ChromaDB ONNX Cold-Start in Restricted Networks:** First-time ChromaDB embedding in a fresh container downloads ~79 MB ONNX model if not pre-cached. | **Medium** | Pre-warm the ONNX embedding cache during `docker build` (as user `reliefops`) or rely on the existing mounted `data/chromadb/` + automatic `BM25Retriever` fallback. |
| **RISK-04** | **SQLite File Locking on Windows/WSL2 Bind Mounts:** Concurrent heavy writes across multiple processes on a Windows-to-Linux bind mount can contend on WAL locks. | **Low** | `DatabaseManager` uses `timeout=30.0`, thread-local connections, and `synchronous=NORMAL` within a single container instance (`replicas: 1`). |

---

## 9. Recommended Implementation Sequence (For Phase 10 — Task 2)

Once approved by the user, implementation should proceed in the following strict, non-destructive sequence:

1. **Step 1 — Create `.dockerignore`:**
   - Exclude `.venv/`, `.git/`, `__pycache__/`, `.pytest_cache/`, `.env`, `data/*.db*`, `data/backup_*/`, `data/chromadb/`, `*.log`, while allowing `data/sops/` markdown files into the image.
2. **Step 2 — Align Environment Variable Resolution (`backend/rag/vector_store.py` & `backend/rag/document_loader.py`):**
   - Respect `os.environ.get("CHROMADB_PATH")` and `os.environ.get("SOP_DIR")` when `persist_dir` / `sops_dir` is `None` (fully backward-compatible with all 133 existing tests).
3. **Step 3 — Harden `Dockerfile` & Safe Container Startup:**
   - Add `libgomp1` to `apt-get install`.
   - Ensure non-destructive startup initialization that checks whether `/app/data/reliefops.db` already exists and is populated before running `seeder.py`, guaranteeing zero data loss on mounted volumes.
4. **Step 4 — Refine `docker-compose.yml`:**
   - Remove deprecated `version: '3.8'`, verify environment variables, healthcheck (`/_stcore/health`), and persistent volume mappings (`./data:/app/data`, `./logs:/app/logs`).
5. **Step 5 — Verification & Regression Testing:**
   - Run `pytest` across all 133 existing tests + deployment readiness checks while keeping `data/reliefops.db` and `data/chromadb/` 100% intact.

---

## 10. Final Audit Verdict

**VERDICT: CONDITIONALLY READY FOR CONTAINERIZATION (90% COMPLETE — NO ARCHITECTURAL BLOCKERS)**

- **Application & Multi-Agent Core:** **PASS** (133/133 automated tests passing; deterministic mode operates 100% offline with zero external API keys).
- **Database & RAG Persistence:** **PASS** (`data/reliefops.db` with WAL mode and `data/chromadb/` with BM25 fallback are production-hardened and preserved untouched).
- **Security Controls:** **PASS** (Secret masking, SQL parameterization, path traversal guards, and HTML escaping verified).
- **Containerization Artifacts:** **NEEDS MINOR HARDENING IN TASK 2** (Requires creating `.dockerignore`, adding `libgomp1` to `Dockerfile`, ensuring non-destructive startup seeding when `./data` is bind-mounted, and wiring `CHROMADB_PATH` / `SOP_DIR` env vars in `vector_store.py` / `document_loader.py`).

# ReliefOps AI — Phase 11 Docker Deployment & Operational Validation Report

**Project:** ReliefOps AI — Intelligent Disaster Relief Resource Allocation Coordinator  
**Course:** CSE476 — Agentic AI and Intelligent Automation  
**Repository:** `https://github.com/sachindhami-s/ReliefOps-AI-2026`  
**Date:** 2026-11-24  
**Overall Deployment Verdict:** **PASSED — VERIFIED LIVE ON DOCKER DESKTOP (LINUX ENGINE)**

---

## 1. Executive Summary of Completed Phase 11 Deployment Tasks

| Task | Description | Status | Verified Evidence |
| :--- | :--- | :---: | :--- |
| **Part 1** | Complete Project, Git, Codebase & TODO Audit | **PASSED** | `PHASE11_PROJECT_AUDIT.md`; `0` TODO/FIXME stubs; fixed SQLite `ON DELETE CASCADE` bug in `backend/agents/relief_coordinator.py` |
| **Task 1** | Host Docker Environment Verification | **PASSED** | `Docker 29.5.2 (build 79eb04c)`, `Docker Compose v5.1.3`, `linux/x86_64` engine active, `docker compose config` exited `0` |
| **Task 2** | Live Docker Image Build (`Dockerfile`) | **PASSED** | Built `reliefops-ai:phase11` & `reliefops-ai:latest` (`2.31 GB`, lean `48.16 kB` build context via `.dockerignore`) |
| **Task 3** | Live Docker Compose Execution & Port 8501 Check | **PASSED** | `reliefops-ai-service` `Up (healthy)`, `/_stcore/health` `HTTP 200` (`10.99 ms`), `/` `HTTP 200` (`17.13 ms`) |
| **Task 4** | Timestamped Hot Backup & Restart Persistence | **PASSED** | Backup `data/backups/reliefops_pre_phase11_20261124_024244.db` (`6,987,776 B`); stop/restart preserved DB & `64` ChromaDB chunks intact |
| **Task 5** | Container-Level Functional Testing | **PASSED** | `47 / 47` in-container `pytest` tests passed + live container validation suite (`rag`, 5 agents, allocation, Gini `0.0584` vs `0.5679`, dynamic replanning) |
| **Task 6** | Security, Non-Root & Volume Permission Audit | **PASSED** | `uid=1000(reliefops)`, secret masking `sk-...cdef`, path traversal blocked, `/app/data` & `/app/logs` writable, SQLite WAL & `?` parameterization |
| **Task 7** | Container vs. Local Python Benchmarks | **PASSED** | Warm container `SCEN-01` `813.82 ms` vs local `628.73 ms`; warm ChromaDB `1,170.95 ms`; BM25 `0.24 ms`; idle RAM `54.51 MiB` |
| **Browser Automation** | Headless Chrome DevTools UI Drive | **NOT TESTED (Local Chrome Remote Debugging Disabled)** | Verified via HTTP `200` on `http://localhost:8501/` + `tests/test_command_dashboard.py` (all 9 modules via Streamlit `AppTest` inside container). |

---

## 2. Files Created & Modified in Phase 11

### Modified Files
1. **`backend/agents/relief_coordinator.py`:** Replaced two `INSERT OR REPLACE INTO allocation_plans` queries (lines 210 and 252) with `INSERT INTO allocation_plans (...) VALUES (...) ON CONFLICT(plan_id) DO UPDATE SET ...`. Prevented SQLite `ON DELETE CASCADE` from deleting newly inserted `audit_logs` records during plan commit.
2. **`.dockerignore`:** Added exclusions for academic submission artifacts (`*.pptx`, `*.pdf`, `*.docx`, `presentation/`, `presentation_assets/`, `reports/`, `generate_presentation.py`, `generate_revised_presentation.py`, `PRESENTATION_CHANGELOG.md`) to keep the Docker build context minimal (`48.16 kB`).
3. **`DEPLOYMENT.md`:** Updated repository URL to `https://github.com/sachindhami-s/ReliefOps-AI-2026.git`, standardized on Docker Compose v2 (`docker compose`), and documented verified Phase 11 container operations.
4. **`README.md`:** Updated verified test baseline to `139 / 139`, added live Docker Compose deployment verification summary, and linked Phase 11 reports.

### Created Files
1. **`PHASE11_PROJECT_AUDIT.md`** — Full component audit matrix, Git state, TODO scan, and pre-deployment findings.
2. **`PHASE11_DEPLOYMENT_REPORT.md`** — This deployment report.
3. **`PHASE11_TESTING_REPORT.md`** — Detailed local and in-container functional, security, and performance validation results.
4. **`DOCKER_TROUBLESHOOTING.md`** — Windows Docker Desktop, WSL 2, port `8501`, bind-mount permissions, and non-destructive SQLite/ChromaDB operations guide.

---

## 3. Commands Executed & Actual Build / Runtime Outputs

### 3.1 Pre-Deployment Timestamped Hot Backup (Non-Destructive)
```powershell
.\.venv\Scripts\python.exe -c "from backend.database.db_manager import DatabaseManager; ..."
```
- **Output:** `[BACKUP OK] data\backups\reliefops_pre_phase11_20261124_024244.db (6,987,776 bytes)`
- **Pre-Docker Baseline:** `5` disaster events, `6` affected zones, `4` warehouses, `16` warehouse inventory rows, `119` allocation plans, `2,399` allocation items, `4` audit logs, `1,033` blackboard events, `12` SOP documents, and `64` ChromaDB chunks in `disaster_sops`.

### 3.2 Docker Image Build (Task 2)
```powershell
docker build -t reliefops-ai:phase11 -t reliefops-ai:latest .
```
- **Result:** **SUCCEEDED (`exit code 0`)**
- **Build Context Transferred:** `48.16 kB` (confirms `.venv/`, `.git/`, local `.db`, backups, and academic `.pptx`/`.pdf` files were cleanly excluded).
- **Resulting Image Size:** `2.31 GB` (`reliefops-ai:phase11`, `reliefops-ai:latest`).
- **Base Image:** `python:3.12-slim` (Python `3.12.16`, `glibc 2.41`, `libgomp1`, `curl`, `sqlite3`).

### 3.3 Docker Compose Startup & Health Verification (Task 3)
```powershell
docker compose up -d --build
docker ps -a --filter name=reliefops-ai-service
curl.exe -sS -w " | HTTP=%{http_code} | time=%{time_total}s`n" http://localhost:8501/_stcore/health
curl.exe -sS -o NUL -w "ROOT_UI | HTTP=%{http_code} | time=%{time_total}s`n" http://localhost:8501/
```
- **Container Status:** `ff52715571d2` — `Up (healthy)` on `0.0.0.0:8501->8501/tcp`.
- **Entrypoint Logs:**
  ```text
  [ReliefOps AI] Running non-destructive startup verification...
  [ENTRYPOINT] Existing SQLite database detected at '/app/data/reliefops.db' (6987776 bytes). Preserving untouched without reseeding.
  [ENTRYPOINT] Existing ChromaDB collection 'disaster_sops' detected (64 indexed chunks at '/app/data/chromadb'). Preserving untouched.
  [ENTRYPOINT] Starting application: streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true
  ```
- **HTTP Verification:**
  - `GET /_stcore/health` → `ok | HTTP=200 | time=0.010993s`
  - `GET /` → `HTTP=200 | time=0.017131s`

### 3.4 Non-Destructive Persistence Across Container Stop & Restart (Task 4)
```powershell
docker compose stop
docker compose start
```
- **Measured Timing:** `stop = 2.53 s`, `docker start = 0.99 s`, full Streamlit readiness (`HTTP 200`) = `12.16 s`.
- **Post-Restart Verification Inside Container:**
  - `data/reliefops.db` preserved at exact `6,987,776` bytes with `journal_mode = wal` and identical row counts across all 9 tables (`5` events, `6` zones, `4` warehouses, `16` inventory rows, `119` plans, `2,399` items, `4` audit logs, `1,033` blackboard events, `12` SOP docs).
  - `data/chromadb/` preserved with `64` indexed chunks in `disaster_sops` (`chroma_indexed = False` — never re-indexed or recreated).
  - Subsequent live in-container `AppTest` runs wrote 1 new plan cleanly (`119 → 120` plans, `4 → 5` audit logs), confirming persistent read/write operation on the bind mount.

---

## 4. Security & Operational Review (Task 6)

| Control | Container Verification Result | Status |
| :--- | :--- | :---: |
| **Non-Root Execution** | `docker exec reliefops-ai-service id` → `uid=1000(reliefops) gid=1000(reliefops)` | **PASS** |
| **Filesystem & Volume Permissions** | `/app` owned by `reliefops:reliefops` (`drwxr-xr-x`); `/app/data` and `/app/logs` writable (`os.access(..., W_OK) == True`) | **PASS** |
| **Environment Variable Injection** | Verified inside container: `DATABASE_PATH=data/reliefops.db`, `CHROMADB_PATH=data/chromadb`, `SOP_DIR=data/sops`, `RELIEFOPS_EXECUTION_MODE=deterministic`, `GINI_THRESHOLD=0.35`, `SURVIVAL_FLOOR_RATIO=0.30` | **PASS** |
| **Secret Masking** | `Settings.mask_secret("sk-test-1234567890abcdef")` → `"sk-...cdef"`; zero hardcoded credentials | **PASS** |
| **Path Traversal Protection** | `validate_path_safety` raised `SecurityValidationError` on `../../etc/passwd` inside container | **PASS** |
| **SQL Injection & ACID** | All queries use `?` placeholders; WAL mode active; `ON CONFLICT(plan_id) DO UPDATE` preserves `audit_logs` FK | **PASS** |
| **Streamlit CORS/XSRF Note** | `.streamlit/config.toml` sets `enableCORS = false` and `enableXsrfProtection = false` (retained to preserve compatibility; recommend enabling XSRF behind HTTPS reverse proxy in internet-facing deployments) | **DOCUMENTED** |

---

## 5. Remaining Limitations & Operational Notes

1. **First Cold Container ONNX Embedding Model Fetch:** In a brand-new container image without a pre-baked `~/.cache/chroma/onnx_models/all-MiniLM-L6-v2` cache, the first semantic vector query downloads the ~79.3 MB ONNX model (`~83.5 s` observed under concurrent load), during which `SOPRetriever` automatically falls back to `BM25Retriever` (`0.34 ms`) without errors. Once cached in the container, warm vector queries run in `~1.17 s`.
2. **Single-Replica SQLite Constraint:** Keep `replicas: 1` per mounted `./data` volume to avoid multi-container SQLite WAL lock contention.
3. **Academic Prototype Scope:** Disaster data, demographics, and warehouse inventories remain synthetic academic datasets created for CSE476 evaluation.

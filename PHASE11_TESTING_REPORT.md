# ReliefOps AI — Phase 11 Container Testing & Performance Benchmark Report

**Project:** ReliefOps AI — Intelligent Disaster Relief Resource Allocation Coordinator  
**Course:** CSE476 — Agentic AI and Intelligent Automation  
**Date:** 2026-11-24  
**Local Regression Baseline:** **`139 / 139` PASSED (`119.08s`, Python `3.12.1` on Windows 11)**  
**Container Functional Suite:** **`47 / 47` PASSED (`196.65s`, Python `3.12.16` inside Linux Docker Container `reliefops-ai-service`)**

---

## 1. Defect Discovered, Root Cause & Regression Verification

During Phase 11 Part 1 validation, running the full `pytest` suite uncovered a genuine persistence defect:
- **Initial Failure:** `tests/test_phase9_end_to_end_validation.py::TestPhase9EndToEndValidation::test_05_phase5_dynamic_replanning_nine_step_lifecycle` failed (`138 passed, 1 failed`) because `audit_logs` returned `None` after plan commit.
- **Root Cause:** `backend/agents/relief_coordinator.py` executed `INSERT OR REPLACE INTO allocation_plans` after `FairnessAuditorAgent` had already inserted an `audit_logs` row referencing `plan_id`. Under `PRAGMA foreign_keys = ON` and `FOREIGN KEY (plan_id) REFERENCES allocation_plans(plan_id) ON DELETE CASCADE`, SQLite's `INSERT OR REPLACE` performs `DELETE` + `INSERT`, cascade-deleting the `audit_logs` record.
- **Fix Applied:** Replaced both `INSERT OR REPLACE INTO allocation_plans` statements in `backend/agents/relief_coordinator.py` with `ON CONFLICT(plan_id) DO UPDATE SET ...`.
- **Verification:** Re-verified on both **Local Windows (`139 / 139 passed`)** and **Inside Linux Docker Container (`47 / 47 passed`, including `test_05` and live `audit_log_persisted = true`)**.

---

## 2. Container-Level Functional Verification Matrix (Task 5)

All container tests ran inside the live `reliefops-ai-service` container (`Linux-6.6.87.2-microsoft-standard-WSL2-x86_64`, `uid=1000(reliefops)`):

| Category | Scope Verified Inside Container | Method / Evidence | Status |
| :--- | :--- | :--- | :---: |
| **A. Dashboard (9 Modules)** | Executive Overview, Disaster Monitoring, GIS Command Map, Resource Management, AI Allocation Engine, Fairness Analytics, RAG Knowledge Assistant, Dynamic Replanning, Audit & Explainability | `docker exec reliefops-ai-service pytest tests/test_command_dashboard.py` (`8/8` Streamlit `AppTest` passing) + `HTTP 200` on `http://localhost:8501/` and `/_stcore/health` | **PASSED** |
| **B. Multi-Agent System** | `ReliefCoordinator`, `NeedsAssessmentAgent`, `InventoryAgent`, `LogisticsAgent`, `FairnessAuditorAgent`, and all 8 populated Blackboard sections (`disaster_context`, `sop_context`, `zone_needs`, `inventory_snapshot`, `logistics_matrix`, `allocation_draft`, `audit_verdict`, `final_allocation_plan`) | Live container suite (`phase11_bench.py`) + `test_phase9_end_to_end_validation.py` (`9/9` passed) | **PASSED** |
| **C. Hybrid RAG** | ChromaDB vector retrieval (`vector_chromadb`, `3` hits, `SOP-FL-001`), Okapi BM25 fallback (`bm25_keyword_fallback`, `3` hits, `SOP-EQ-002`), citation grounding & hazard filtering | Live container suite (`tests.rag.passed = true`) + `tests/test_rag.py` (`7/7` passed) | **PASSED** |
| **D. Allocation Engine** | `30%` baseline target (`Z1=454, Z2=226, Z3=120` totaling `800` on illustrative check), ZPS-weighted residual allocation, resource conservation (`allocated <= available` and `allocated <= demanded`) | Live container suite (`conservation_ok = true`, `waterfilling_floor_30pct_ok = true`) | **PASSED** |
| **E. Fairness Auditor** | Gini coefficient (`SCEN-01` fair `0.0584` ≤ `0.35` → `FAIRNESS_APPROVED`; greedy `0.5679` > `0.35` → `FAIRNESS_REJECTED`), zero-allocation checks, `audit_logs` SQLite persistence | Live container suite (`passed = true`, `audit_log_persisted = true`) + `tests/test_advanced_fairness_auditor.py` (`10/10` passed) | **PASSED** |
| **F. Dynamic Replanning** | `SCEN-03` (`CYCLONE`) mid-run surge (`Tezpur Foothills Corridor`, `2.0×`, damage `5`, `BLOCKED`), Blackboard invalidation, hazard preservation (`CYCLONE`), population `187,000 → 219,000`, revised Gini `0.0561`, revised plan & audit persisted | Live container suite (`tests.dynamic_replanning.passed = true`) + `test_phase9_end_to_end_validation.py::test_05` | **PASSED** |
| **G. Security & Dockerization** | Secret masking (`sk-...cdef`), path traversal rejection, ACID rollback, hot backup/restore, Dockerfile/Compose/entrypoint preservation | `tests/test_production_readiness.py` (`7/7` passed) + `tests/test_phase10_deployment_dockerization.py` (`6/6` passed) | **PASSED** |
| **H. Automated Chrome UI Drive** | Live browser automation via Chrome DevTools | Not tested because host Chrome remote debugging (`DevToolsActivePort`) was not enabled; dashboard UI verified via Streamlit `AppTest` + live HTTP `200` probe. | **NOT TESTED** |

---

## 3. Automated Test Suite Execution Summary

| Execution Environment | Command | Result | Duration |
| :--- | :--- | :---: | :---: |
| **Local Host (Windows 11, Python 3.12.1)** | `.\.venv\Scripts\python.exe -m pytest -q tests` | **`139 passed, 0 failed`** | `119.08 s` |
| **Docker Container (Linux WSL2, Python 3.12.16)** | `docker exec reliefops-ai-service pytest -q tests/test_command_dashboard.py tests/test_rag.py tests/test_advanced_fairness_auditor.py tests/test_production_readiness.py tests/test_phase10_deployment_dockerization.py tests/test_phase9_end_to_end_validation.py` | **`47 passed, 0 failed`** | `196.65 s` |

---

## 4. Reproducible Performance & Reliability Benchmarks (Task 7)

All measurements below were captured using identical Python workloads (`phase11_bench.py`) executing against an isolated temporary copy of `data/reliefops.db` so production records were untouched.

| Benchmark Metric | Local Windows Python (`3.12.1`) | Docker Linux Container — Warm (`3.12.16`) | Docker Linux Container — Cold First ONNX Fetch | Notes / Observations |
| :--- | :---: | :---: | :---: | :--- |
| **Container Stop Time** | N/A | `2.53 s` | N/A | Graceful shutdown via `docker compose stop` |
| **Container Start Time** | N/A | `0.99 s` | N/A | `docker compose start` |
| **App Ready Time (`HTTP 200`)** | N/A | `12.16 s` | `< 20 s` | Entrypoint verification + Streamlit server ready on `:8501` |
| **Healthcheck HTTP Latency** | N/A | `10.99 ms` (`/_stcore/health`) | `10.99 ms` | `HTTP 200` (`ok`); Root `/` = `17.13 ms` |
| **SQLite Init & Query** | `35.20 ms` | `205.31 ms` | `241.57 ms` | Expected WSL2 Windows-to-Linux bind-mount file-I/O overhead |
| **ChromaDB ONNX Vector RAG** | `1,606.82 ms` | **`1,170.95 ms`** (`vector_chromadb`) | `83,539.08 ms` (first 79.3 MB ONNX model download + BM25 fallback) | Warm Linux container outperforms local Windows on vector retrieval |
| **Okapi BM25 RAG Fallback** | `0.19 ms` | **`0.24 ms`** | `0.34 ms` | Sub-millisecond lexical fallback in both environments |
| **End-to-End `SCEN-01` Cycle** | `628.73 ms` | **`813.82 ms`** | `72,135.68 ms` (included cold ONNX fetch) | Includes all 5 agents, RAG, Water-Filling, Gini audit & SQLite commit |
| **Python Peak Traced Memory** | `1.36 MB` | **`1.36 MB`** | `1.41 MB` | Identical memory footprint (`tracemalloc`) |
| **Container Memory (`docker stats`)** | N/A | Idle: `54.51 MiB` (`0.72%`) / Warm: `388.4 MiB` (`5.11%`) | Peak during parallel tests: `570.2 MiB` (`7.50%`) | Comfortable headroom under 7.42 GiB WSL2 limit |

---

## 5. Persistent Storage Verification Record (Task 4)

| Checkpoint | `reliefops.db` Size | `events` | `zones` | `warehouses` | `inventory` | `plans` | `items` | `audit_logs` | `sop_docs` | ChromaDB Chunks |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Pre-Docker Backup Baseline** | `6,987,776 B` | `5` | `6` | `4` | `16` | `119` | `2,399` | `4` | `12` | `64` |
| **Post-Start & Post-Restart (Untouched)** | `6,987,776 B` | `5` | `6` | `4` | `16` | `119` | `2,399` | `4` | `12` | `64` |
| **Post In-Container `AppTest` Write** | `7,057,408 B` | `5` | `6` | `4` | `16` | `120` | `2,419` | `5` | `12` | `64` |

**Result:** **PASSED** — Existing SQLite and ChromaDB data were preserved 100% intact across container build, startup, stop, and restart, and live writes from inside the container persisted cleanly to the host mount.

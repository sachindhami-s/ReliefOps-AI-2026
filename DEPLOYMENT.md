# ReliefOps AI — Production Deployment & Operations Guide

**Course:** CSE476 — Agentic AI and Intelligent Automation  
**Target Environment:** Academic Demonstration, Local Cloud, or Containerized Production

---

## 1. Production Architecture Overview

ReliefOps AI is engineered to be deployed as an autonomous, self-contained multi-agent platform. It can run in either **Deterministic Mode** (default, offline, zero API costs) or **LLM Mode** (leveraging external frontier models for unstructured text synthesis).

```
                      INTERNET / INTRANET
                               │
                               ▼
                 [ Reverse Proxy / TLS (NGINX) ]
                               │ (Port 8501)
                               ▼
                 [ Docker Container: reliefops ]
                 ┌─────────────────────────────┐
                 │  Streamlit Web Dashboard    │
                 │  Hayes-Roth Blackboard      │
                 │  Five Autonomous Agents     │
                 │  ChromaDB Vector Engine     │
                 │  SQLite Transactional DB    │
                 └──────────────┬──────────────┘
                                │
                                ▼
                 [ Persistent Storage Volumes ]
                 ├── data/reliefops.db (WAL)
                 ├── data/chromadb/
                 └── logs/reliefops.log
```

---

## 2. Docker & Containerized Deployment (Recommended — Verified in Phase 11)

Containerization guarantees 100% reproducible execution across Linux, macOS, and Windows (Docker Desktop + WSL 2 Linux engine) environments.

### Step 1: Clone and Configure Environment

```bash
git clone https://github.com/sachindhami-s/ReliefOps-AI-2026.git
cd ReliefOps-AI-2026
cp .env.example .env
```

Review `.env` settings:
```ini
RELIEFOPS_EXECUTION_MODE=deterministic
RELIEFOPS_LOG_LEVEL=INFO
DATABASE_PATH=data/reliefops.db
CHROMADB_PATH=data/chromadb
SOP_DIR=data/sops
GINI_THRESHOLD=0.35
SURVIVAL_FLOOR_RATIO=0.30
ROUTING_MODE=HAVERSINE_FALLBACK
OSRM_BASE_URL=https://router.project-osrm.org
ROUTING_TIMEOUT_SECONDS=5.0
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
STREAMLIT_SERVER_HEADLESS=true
```

### Step 2: Build and Launch Container (Docker Compose v2)

```bash
docker compose up --build -d
```

> **Non-Destructive Startup Guarantee (`docker_entrypoint.py`):** On container startup, `/app/docker-entrypoint.sh` verifies `./data/reliefops.db` and `./data/chromadb/` non-destructively. Existing SQLite databases and ChromaDB collections (`64` SOP chunks) are preserved untouched without reseeding. Cold initialization only runs when `/app/data/reliefops.db` does not exist or ChromaDB has `0` chunks.

### Step 3: Verify Container Health & Status

```bash
# Check container status (expected: Up ... (healthy))
docker ps --filter name=reliefops-ai-service

# Check HTTP healthcheck endpoint (expected: ok, HTTP 200)
curl -f http://localhost:8501/_stcore/health

# Inspect non-destructive startup & Streamlit logs
docker compose logs -f
```

### Step 4: Safe Stop & Restart (Preserve Persistent Data)

```bash
# Stop without deleting persistent volumes or data
docker compose stop

# Restart while preserving SQLite and ChromaDB data
docker compose start
```

> **Warning:** Never run `docker compose down -v` on an environment holding active database records without first running an online SQLite hot backup (`Section 4`). See `DOCKER_TROUBLESHOOTING.md` and `PHASE11_DEPLOYMENT_REPORT.md` for Windows Docker Desktop guidance and live verification benchmarks.

---

## 3. Native Linux Server Deployment (Systemd)

For bare-metal or VM deployments (e.g., Ubuntu 22.04 LTS):

### 1. Create Dedicated Service User
```bash
sudo useradd -r -s /bin/false -m -d /opt/reliefops reliefops
sudo git clone https://github.com/sachindhami-s/ReliefOps-AI-2026.git /opt/reliefops/app
sudo chown -R reliefops:reliefops /opt/reliefops/app
```

### 2. Set Up Virtual Environment
```bash
cd /opt/reliefops/app
sudo -u reliefops python3 -m venv .venv
sudo -u reliefops /opt/reliefops/app/.venv/bin/pip install --upgrade pip
sudo -u reliefops /opt/reliefops/app/.venv/bin/pip install -r requirements.txt
sudo -u reliefops /opt/reliefops/app/.venv/bin/python -m backend.database.seeder
```

### 3. Configure Systemd Service Unit
Create `/etc/systemd/system/reliefops.service`:
```ini
[Unit]
Description=ReliefOps AI Multi-Agent Platform
After=network.target

[Service]
Type=simple
User=reliefops
Group=reliefops
WorkingDirectory=/opt/reliefops/app
EnvironmentFile=/opt/reliefops/app/.env
ExecStart=/opt/reliefops/app/.venv/bin/streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

### 4. Enable and Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable reliefops
sudo systemctl start reliefops
sudo systemctl status reliefops
```

---

## 4. Database Reliability, Maintenance & Backups

ReliefOps AI uses SQLite with **Write-Ahead Logging (WAL)** mode enabled, providing high concurrency, low latency, and atomic transactional integrity.

### Online Hot Backup (Zero Downtime)
Do not copy active `.db` files directly with operating system commands while writers are active, as this can result in incomplete WAL frames. Instead, execute the integrated hot backup routine using SQLite's native backup API:

```python
from pathlib import Path
from backend.database.db_manager import default_db_manager

backup_file = Path("data/backups/reliefops_backup_20261115.db")
default_db_manager.backup_database(backup_file)
print(f"Database successfully backed up to {backup_file}")
```

### Database Restoration Procedure
In the event of hardware failure or simulation reset:

```python
from pathlib import Path
from backend.database.db_manager import default_db_manager

backup_file = Path("data/backups/reliefops_backup_20261115.db")
default_db_manager.restore_database(backup_file)
print("Database restored to point-in-time snapshot.")
```

### Automated Nightly Cron Job
Add to `/etc/cron.d/reliefops-backup`:
```cron
0 2 * * * reliefops /opt/reliefops/app/.venv/bin/python -c "from pathlib import Path; from backend.database.db_manager import default_db_manager; import datetime; ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S'); default_db_manager.backup_database(Path(f'/opt/reliefops/backups/db_{ts}.db'))"
```

---

## 5. Security & Hardening Checklist

| Security Control | Implementation Mechanism | Verification Test |
| :--- | :--- | :--- |
| **Credential Masking** | Sensitive keys masked as `********` or `abc...xyz` in string dumps. | `tests/test_production_readiness.py::test_01` |
| **Input Boundary Checks** | Demographics, coordinates, and damages validated with strict bounds. | `tests/test_production_readiness.py::test_02` |
| **Path Traversal Shield** | Path safety validator rejects `../` and directory escapes. | `tests/test_production_readiness.py::test_02` |
| **SQL Injection Defense** | All database calls parameterized via SQLite `?` placeholders. | Verified in `db_manager.py` |
| **Atomic Transactions** | Allocation commits wrapped in `BEGIN IMMEDIATE; COMMIT; / ROLLBACK;`. | `tests/test_production_readiness.py::test_04` |
| **Non-Root Execution** | Docker container executes under unprivileged UID `1000:1000`. | Verified in `Dockerfile` |
| **Plan ID Collision Free** | Sub-second timestamps paired with 8-character cryptographic random hex UUID. | `tests/test_production_readiness.py::test_03` |

# ReliefOps AI — Docker & Windows Container Troubleshooting Guide

**Project:** ReliefOps AI — Intelligent Disaster Relief Resource Allocation Coordinator  
**Course:** CSE476 — Agentic AI and Intelligent Automation  
**Verified Host Tooling:** Docker CLI `29.5.2` (`build 79eb04c`), Docker Compose `v5.1.3`, Windows 10/11

---

## 1. Docker Daemon Not Running (`dockerDesktopLinuxEngine` Pipe Missing)

### Symptom
Running `docker info`, `docker build`, or `docker compose up` fails with:

```text
failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine;
check if the path is correct and if the daemon is running:
open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
```

### Root Cause
Docker Desktop is installed (`C:\Program Files\Docker\Docker\Docker Desktop.exe`), but the Docker Desktop background application and its Linux container engine (WSL 2 backend) are not currently running.

### Exact Windows Resolution Steps
1. **Launch Docker Desktop:**
   - Press the **Windows** key, type **Docker Desktop**, and open it (or run `C:\Program Files\Docker\Docker\Docker Desktop.exe`).
2. **Wait for Engine Initialization:**
   - Wait until the whale icon in the Windows system tray stops animating and displays **"Docker Desktop running"** (bottom-left status bar inside Docker Desktop turns green: **Engine running**).
3. **Ensure the Linux Container Engine Is Active:**
   - Right-click the Docker whale icon in the Windows system tray.
   - If the menu displays **"Switch to Linux containers..."**, click it and wait for the switch to complete.
   - If it displays **"Switch to Windows containers..."**, the Linux container engine is already active (required because `Dockerfile` uses `FROM python:3.12-slim`).
4. **Verify WSL 2 Backend (if Docker Desktop fails to start):**
   - Open Docker Desktop → **Settings (Gear Icon)** → **General** → confirm **"Use the WSL 2 based engine"** is checked.
   - In an elevated PowerShell window, verify WSL 2 status:
     ```powershell
     wsl --status
     wsl --update
     ```
5. **Confirm Daemon Readiness in PowerShell:**
   ```powershell
   docker info --format "{{.ServerVersion}} | {{.OSType}}"
   ```
   Expected output: `29.5.2 | linux` (or similar version followed by `| linux`).

---

## 2. Port 8501 Already in Use

### Symptom
`Bind for 0.0.0.0:8501 failed: port is already allocated`

### Resolution
Check if a local non-Docker Streamlit process is listening on port `8501`:
```powershell
netstat -ano | findstr :8501
```
Stop the local Streamlit process (`Stop-Process -Id <PID>`), or temporarily map a different host port in `docker-compose.yml` (e.g., `"8502:8501"`).

---

## 3. Preserving Existing SQLite & ChromaDB Data (Non-Destructive Rules)

ReliefOps AI mounts the entire `./data` directory into `/app/data`:
- `./data:/app/data` (keeps `reliefops.db`, `reliefops.db-wal`, `reliefops.db-shm`, `data/chromadb/`, and `data/sops/` on one mount)
- `./logs:/app/logs`

**Critical Safety Rules:**
1. **Never** run `docker compose down -v` without first creating a verified timestamped backup of `data/reliefops.db` and `data/chromadb/`.
2. **Never** mount `data/reliefops.db` as a single file (SQLite WAL requires `-wal` and `-shm` companion files in the same directory mount).
3. Run only **1 container replica** against the mounted SQLite database to avoid multi-process WAL write contention.
4. Create a safe online backup before major upgrades:
   ```powershell
   .\.venv\Scripts\python.exe -c "from backend.database.db_manager import default_db_manager; print(default_db_manager.backup_database())"
   ```

---

## 4. Windows Bind-Mount File Permissions (`user: "1000:1000"`)

### Symptom
Inside the Linux container, SQLite or ChromaDB logs `PermissionError` or `readonly database` when writing to `/app/data`.

### Resolution
- On Docker Desktop for Windows (WSL 2), bind-mounted host folders under `C:\Users\...` are typically writable by UID `1000`.
- Verify permissions inside a running container:
  ```powershell
  docker exec reliefops-ai-service id
  docker exec reliefops-ai-service ls -la /app/data
  ```
- Ensure Windows antivirus or another local Python/Streamlit process does not hold an exclusive lock on `data\reliefops.db`.

---

## 5. ChromaDB ONNX Model Download Timeout in Restricted Networks

### Symptom
On a cold start with an empty `data/chromadb/`, ChromaDB attempts to download the `all-MiniLM-L6-v2` ONNX model (~79 MB) and times out.

### Resolution
- Mounting the pre-indexed `./data:/app/data` directory reuses the existing `64` chunks in `data/chromadb/` immediately without re-indexing.
- If vector search is unavailable or offline during cold start, `SOPRetriever` (`backend/rag/retriever.py`) automatically falls back to `BM25Retriever` (`< 1.0 ms` lexical retrieval across all 12 SOPs).

---

## 6. Entrypoint CRLF Line-Ending Error (`exec /app/docker-entrypoint.sh: no such file or directory`)

### Cause & Verification
Windows Git checkouts can introduce `\r\n` (CRLF) endings in shell scripts. `Dockerfile` already neutralizes this during build:
```dockerfile
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && \
    chmod +x /app/docker-entrypoint.sh /app/docker_entrypoint.py
```
If you rebuild after editing `docker-entrypoint.sh`, ensure `--no-cache` or a clean build step re-runs this `sed` normalization.

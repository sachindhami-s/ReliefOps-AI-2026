# ReliefOps AI — Installation & Environment Setup Guide

This guide provides end-to-end instructions for installing, configuring, and verifying the **ReliefOps AI** multi-agent disaster relief resource allocation platform on Windows, Linux, and macOS systems.

---

## 1. System Requirements

| Component | Minimum Specification | Recommended Specification |
| :--- | :--- | :--- |
| **Operating System** | Windows 10/11, Ubuntu 22.04 LTS, macOS 13+ | Windows 11 / Ubuntu 22.04 |
| **Python** | Python 3.11 or 3.12 | Python 3.12.x |
| **Memory (RAM)** | 4 GB | 8 GB or higher |
| **Disk Space** | 1 GB free | 2 GB free (including vector embeddings) |
| **Database** | SQLite 3.35+ (bundled with standard Python) | SQLite 3.40+ |
| **Optional Tooling** | Docker 24+, Docker Compose v2+ | Docker Engine with Compose plugin |

---

## 2. Step-by-Step Installation

### Step 1: Clone the Repository

Clone the project repository to your local development machine:

```bash
git clone https://github.com/your-username/reliefops-ai.git
cd reliefops-ai
```

### Step 2: Create a Dedicated Virtual Environment

Always use an isolated Python virtual environment to avoid package dependency conflicts.

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

*Note: If PowerShell displays an `Execution_Policies` restriction error, run:*
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\.venv\Scripts\Activate.ps1
```

**On Linux / macOS (Bash / Zsh):**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Verify your active Python interpreter:
```bash
python --version  # Should report Python 3.11.x or 3.12.x
```

### Step 3: Upgrade Pip & Install Dependencies

Install all pinned production and academic dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Verify key package installations:
```bash
python -c "import streamlit, chromadb, semantic_kernel, pydantic, altair; print('All core libraries verified!')"
```

### Step 4: Configure Environment Variables

Copy the provided `.env.example` template to `.env`:

**On Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**On Linux / macOS:**
```bash
cp .env.example .env
```

By default, `RELIEFOPS_EXECUTION_MODE=deterministic`. No external OpenAI, Azure, or Gemini API keys are required. The system runs fully offline with zero API cost using deterministic semantic plugins and local ChromaDB embeddings.

### Step 5: Initialize the Database & Seed Authoritative Scenarios

Run the database seeder to construct the SQLite database schema, ingest the disaster event records, seed regional warehouses, populate affected zones, and build evaluation scenarios:

```bash
python -m backend.database.seeder
```

Expected output:
```
[SUCCESS] SQLite database successfully seeded with master disaster data and 5 evaluation scenarios.
```

### Step 6: Verify ChromaDB Vector Store Ingestion

Verify that the authoritative Standard Operating Procedures (`SOP-FL-001`, `SOP-EQ-002`, `SOP-CY-004`, `SOP-LS-003`) are indexed in the ChromaDB vector database:

```bash
python -c "from backend.agents.needs_assessment_agent import NeedsAssessmentAgent; agent = NeedsAssessmentAgent(); res = agent._retrieve_sop_rag('FLOOD', 'SEVERE'); print('Retrieved SOP:', res.get('sop_ids'))"
```

Expected output:
```
Retrieved SOP: ['SOP-FL-001']
```

---

## 3. Verification & Validation

### Run the Automated Test Suite

Execute pytest across all 109 automated unit, integration, stress, and resilience tests:

```bash
python -m pytest -v
```

Expected result:
```
============================= 109 passed in 40.47s =============================
```

### Run the Dedicated Production Readiness Audit

```bash
python -m pytest -v tests/test_production_readiness.py
```

Expected result: `7 passed` verifying configuration masking, security boundaries, zero plan ID collisions, atomic transaction rollbacks, database hot backups, structured telemetry, and explainability trails.

---

## 4. Launching the System

### Option 1: Interactive Streamlit Web Deck

Start the interactive operations dashboard:

```bash
streamlit run app.py
```

The Streamlit web dashboard will automatically open in your default browser at:
`http://localhost:8501`

### Option 2: Terminal Multi-Hazard Demonstration CLI

To run the full end-to-end multi-agent pipeline in the terminal:

```bash
# Baseline Flood Response
python demo_pipeline.py

# Canonical Earthquake Response
python demo_pipeline.py --hazard EARTHQUAKE

# Mid-Run Dynamic Re-Planning Surge
python demo_pipeline.py --replanning

# All 4 Hazards + Replanning
python demo_pipeline.py --all
```

---

## 5. Troubleshooting & FAQ

### Issue 1: Port 8501 is already in use
If another application or previous Streamlit process is occupying port 8501:
```bash
streamlit run app.py --server.port 8502
```

### Issue 2: ChromaDB SQLite Version Error
ChromaDB requires SQLite version $\ge 3.35.0$. Standard Python $\ge 3.10$ ships with an up-to-date SQLite binary. If running on an older Linux distribution:
```bash
pip install pysqlite3-binary
```
And add to the top of your execution script:
```python
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
```

### Issue 3: Stale Database Records or Migration Reset
To cleanly re-seed the SQLite database:
```bash
python -m backend.database.seeder
```
The seeder uses `ON CONFLICT DO UPDATE` and `INSERT OR REPLACE` to safely refresh master records without dropping relational constraints.

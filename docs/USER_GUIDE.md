# ReliefOps AI — Operational Command Dashboard User Guide

**Target Audience:** Emergency Operations Commanders, Humanitarian Logisticians, AI Systems Evaluators, and CSE476 Course Instructors.  
**Application Entry Point:** `app.py` (Streamlit Operational Command Center)  
**Default URL:** `http://localhost:8501`

---

## 1. Installation & Dashboard Startup

### 1.1 Installation
```bash
# Activate virtual environment
.\.venv\Scripts\activate   # Windows
# source .venv/bin/activate # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Initialize and seed the SQLite database (data/reliefops.db)
python -m backend.database.seeder
```

### 1.2 Launching the Command Dashboard
```bash
streamlit run app.py
```
On startup, the dashboard connects to `data/reliefops.db` and `data/chromadb`, automatically executes the initial canonical coordination cycle (`SCEN-01`), and populates all 9 operational modules with live backend telemetry.

---

## 2. Sidebar Navigation & Tactical Controls

The left sidebar is organized into three operational control groups:

1. **🧭 EOC Command Navigation:**
   - Select **`ALL MODULES (Command Tabs)`** to access all 9 modules simultaneously via the horizontal tab bar.
   - Or select any individual module (`1. Executive Overview` through `9. Audit & Explainability`) to isolate that module in full-screen command mode.
2. **⚙️ Scenario & Hazard Control:**
   - **Select Evaluation Scenario:** Choose `SCEN-01` (Flood), `SCEN-02` (Earthquake), `SCEN-03` (Cyclone), `SCEN-04` (Landslide & Dynamic Replanning), `SCEN-05` (Fairness Veto Benchmark), or `Custom User Scenario`.
   - **Hazard Type & Severity Level:** Switch between `FLOOD`, `EARTHQUAKE`, `CYCLONE`, and `LANDSLIDE` across `MODERATE`, `SEVERE`, and `CATASTROPHIC` severities.
   - **Planning Horizon (Days):** Adjust replenishment horizon from `1` to `30` days.
   - **Affected Geographical Zones Editor:** Dynamically edit zone populations, damage levels (`1–5`), vulnerability (`0–1`), medical urgency (`0–1`), and road access (`OPEN`, `DEGRADED`, `BLOCKED`, `AIR_ONLY`).
   - **🚀 Execute Multi-Agent Coordination:** Runs all 5 autonomous agents (`NeedsAssessmentAgent`, `InventoryAgent`, `LogisticsAgent`, `FairnessAuditorAgent`, `ReliefCoordinator`) over the shared Blackboard.
3. **🔎 Tactical Telemetry Filters:**
   - Filter displayed sectors by **Road Access Status** (`OPEN`, `DEGRADED`, `BLOCKED`, `AIR_ONLY`).
   - Filter displayed dispatches and resource ledgers by **Resource Category** (`FOOD_RATIONS`, `CLEAN_WATER`, `MEDICAL_KITS`, `SHELTER_TENTS`).

---

## 3. Walkthrough of the 9 Command Dashboard Modules

### Module 1: 📊 Executive Overview
- Displays 7 high-contrast EOC KPI cards sourced directly from `ReliefCoordinator` and `BlackboardManager`:
  - **Total Affected Population** & **Displaced Population**
  - **Active Disaster Incident** (`event_id`, `hazard`, `severity`, `governing_sop`)
  - **Total Resources Demanded**
  - **Total Resources Allocated** & **Shipment Legs**
  - **Critical Resource Shortages** (count and specific deficit SKUs)
  - **Latest Allocation Plan ID** & **Overall Verdict Badge**
  - **Overall Fairness Score (Gini)** vs. the $\le 0.35$ humanitarian threshold
- Includes the **Sector Priority & Resource Demand Matrix** and interactive **ZPS Ranking Bar Chart**.

### Module 2: 🌪️ Disaster Monitoring
- Monitors `FLOOD`, `EARTHQUAKE`, `CYCLONE`, and `LANDSLIDE` hazards.
- Displays the **SOP Section 2 Severity Equivalence** (e.g., `Level 3 (Severe Inundation)`, `Level 3 (Heavy Damage)`, `Level 3 (Very Severe Cyclone)`, `Level 3 (Major Slope Failure)`).
- Provides expandable sector telemetry cards detailing affected population, displacement ratio, damage severity, demographic vulnerability, medical urgency, road status, and SOP-computed demands.

### Module 3: 🗺️ GIS Command Map
- Renders an interactive 2D/3D **PyDeck** map using actual database coordinates:
  - **Emerald Markers:** Regional operational warehouses (`Guwahati`, `Jorhat`, `Siliguri`, `Tezpur`) with live stock tooltips.
  - **Sector Markers:** Affected disaster zones scaled by Zone Priority Score ($ZPS$) and color-coded by road access and damage severity.
  - **Dispatch Corridors (`ArcLayer` & `LineLayer`):** Active supply routes from depots to disaster zones with hover tooltips for distance, ETA, and cargo manifest.
- Includes layer visibility checkboxes, a 3D pitch slider (`0°–60°`), and the **Active Logistics Dispatch Corridors** table.

### Module 4: 📦 Resource Management
- Provides 4 dedicated SKU KPI cards and an itemized ledger for `FOOD_RATIONS`, `CLEAN_WATER`, `MEDICAL_KITS`, and `SHELTER_TENTS`.
- Independently reports:
  - **Total Demanded**
  - **Total Available**
  - **Total Allocated**
  - **Fulfillment Percentage:** $\min(100\%, (\text{Allocated} / \text{Demanded}) \times 100)$
  - **Unfulfilled Shortage**
  - **Surplus Inventory**
- Displays the **Regional Warehouse Fleet Stock Snapshot** and an Altair **Resource Fulfillment Percentage Chart**.

### Module 5: 🤖 AI Allocation Engine
- Displays the latest synthesized allocation plan (`plan_id`, `Two-Phase Water-Filling` policy, negotiation iterations).
- **Zone-Wise Resource Allocation & Coverage Summary:** Shows per-sector fulfillment percentages across all 4 resources and AI allocation justification.
- **Warehouse-Wise Outbound Dispatch Summary:** Aggregates shipment legs, total units dispatched, and mean transit distance per depot.
- **Itemized Multi-Depot Logistics Dispatch Schedule:** Full shipment manifest with one-click **CSV Export**.

### Module 6: ⚖️ Fairness Analytics
- Separately audits **Dimension A (Distributive Fairness)** and **Dimension B (Resource Adequacy)**.
- Contrasts **ReliefOps AI Two-Phase Water-Filling** (`FAIRNESS_APPROVED`, $\text{Gini} \le 0.35$) against **Naive Greedy Optimization** (`FAIRNESS_REJECTED`, $\text{Gini} \approx 0.5679$).
- Renders the interactive Altair **Empirical Lorenz Curve Comparison Chart** with equal sector weighting satisfying trapezoidal integration $\text{Gini} = 1 - \sum (Y_i + Y_{i-1})(X_i - X_{i-1})$.

### Module 7: 📚 RAG Knowledge Assistant
- Connects directly to the **ChromaDB** vector store and **Okapi BM25** fallback engine.
- Allows operators to select preset doctrine queries or enter custom disaster-response questions, filter by hazard scope (`ALL`, `FLOOD`, `EARTHQUAKE`, `CYCLONE`, `LANDSLIDE`), and configure `Top-K` passages.
- Generates a **Grounded Operational Guidance** summary with explicit `[SOP-ID | Chunk-ID]` citations and expandable verbatim SOP chunks.

### Module 8: 🌊 Dynamic Replanning
- Allows operators to select a target sector, configure a **Population Surge Multiplier** (`1.2x–2.5x`), **Escalated Damage Level** (`3–5`), and **Post-Incident Road Access** (`BLOCKED`, `DEGRADED`, `AIR_ONLY`).
- Clicking **🚨 Trigger Mid-Run Incident & Execute Dynamic Re-Planning** runs the full backend replanning workflow while preserving the active hazard context, displaying side-by-side deltas for Population, Displaced Population, Fairness Gini, Shipment Legs, and a **Sector-by-Sector Progression Diff Table**.

### Module 9: 🔍 Audit & Explainability
- Displays the **Traceable AI Decision Audit Trail** (Distributive Justice rationale, Sector Prioritization rationales, Resource Shortage root-cause explanations).
- Shows the **Committed SQLite Allocation Plans Ledger** (`allocation_plans`) and the filterable **Synchronized Blackboard Event Journal** (`blackboard_events`).

---

## 4. Configuration & Known Limitations
- **Database Auto-Recovery:** If `data/reliefops.db` is empty or missing tables, the dashboard displays a warning banner with a one-click **Initialize & Seed Master Operational Database** button.
- **Offline Operation:** All vector embeddings and BM25 indices execute locally without external network dependencies.

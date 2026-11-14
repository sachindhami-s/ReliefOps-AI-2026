# ReliefOps AI — Development Roadmap & Academic Evaluation Specification
## Phased Implementation Plan, University Evaluation Scenarios & Risk Management
**Target Delivery Date:** 15 November 2026  
**Course:** CSE476 — Agentic AI and Intelligent Automation  
**Author:** Senior Multi-Agent Systems Architect  
**Workspace:** `C:\Users\deeps\.gemini\antigravity\scratch\reliefops_ai`

---

## 1. Phased Development Roadmap

The implementation is structured into six discrete, test-driven phases designed to guarantee an end-to-end working platform before adding visual polish:

```
+---------------------------------------------------------------------------------------------------+
| Nov 11: Phase 1    | Nov 12: Phase 2    | Nov 12-13: Phase 3 | Nov 13: Phase 4    | Nov 14: Phase 5 | Nov 15: Phase 6 |
| Foundation & Data  | ChromaDB RAG & SOP | 5 Semantic Kernel  | Blackboard Engine  | Streamlit UI &  | Scenarios, Diff |
| Models (SQLite)    | Ingestion Engine   | Specialized Agents | & Negotiation Loop | 3D Spatial Maps | Reports & Audit |
+---------------------------------------------------------------------------------------------------+
```

### Phase 1: Project Scaffolding & Persistent Data Foundation
- Initialize repository structure in `C:\Users\deeps\.gemini\antigravity\scratch\reliefops_ai`.
- Create Python virtual environment configuration and `requirements.txt`.
- Implement `backend/database/schema.sql` and database connection manager (`backend/database/db_manager.py`).
- Implement synthetic seed data script populating 4 warehouses, 6 disaster zones, realistic inventory balances, and baseline scenario parameters.
- Unit test SQLite operations: foreign key enforcement, WAL mode, atomic stock commitment transactions.

### Phase 2: Knowledge Ingestion & ChromaDB RAG Pipeline
- Author curated markdown SOP documents:
  - `data/sops/sphere_water_sanitation.md`
  - `data/sops/sphere_food_nutrition.md`
  - `data/sops/sphere_shelter_settlement.md`
  - `data/sops/ndma_medical_emergency_sop.md`
- Implement ChromaDB vector store wrapper (`backend/rag/vector_store.py`) with chunking, indexing, and local embedding initialization.
- Provide a robust local keyword/TF-IDF deterministic fallback if remote embedding downloads encounter sandbox network restrictions.
- Test semantic retrieval of per-capita humanitarian minimum norms.

### Phase 3: The Five Specialized Agents & Semantic Kernel Plugins
- Configure Microsoft Semantic Kernel instance with pluggable execution engine.
- Implement `NeedsAssessmentPlugin` (demand derivation, ZPS scoring, SOP retrieval).
- Implement `InventoryPlugin` (stock querying, holds, atomic deductions).
- Implement `LogisticsPlugin` (Haversine formula, road degradation coefficients, transit hours).
- Implement `FairnessAuditPlugin` (Gini index calculation, zero-allocation violation detection, minimum floor verification).
- Implement `CoordinatorPlugin` (two-phase bounded water-filling optimization algorithm).
- Unit test each plugin in complete isolation using deterministic mock inputs.

### Phase 4: Blackboard Working Memory & Multi-Agent Negotiation Loop
- Implement `backend/blackboard/blackboard.py` (thread-safe, observable shared memory state with state invalidation semantics).
- Implement `backend/orchestrator/coordinator.py` driving the full coordination cycle:
  - Initialize -> Assess (Needs Agent) -> Check Stock & Feasibility (Inventory + Logistics Agents) -> Synthesize Draft -> Audit (Fairness Agent) -> Revision Loop -> Human Approval / Release.
- Implement the Fairness Rejection feedback loop: automatically inject constraints when a draft fails the Gini threshold or starves a vulnerable zone, forcing re-synthesis until convergence.
- Test mid-run re-planning: dynamic invalidation when new disaster telemetry is injected.

### Phase 5: Streamlit Interactive Operations Command Center
- Build multi-page Streamlit application (`app.py` + `pages/`):
  1. *Operations Center (Dashboard):* High-level operational situation, active alerts, overall delivery status.
  2. *Disaster Map & Spatial Logistics:* PyDeck 3D map rendering affected zones with color-coded severity rings, warehouse depots, transit route vectors, and road access badges.
  3. *Live Blackboard & Agent Timeline:* Real-time inspector showing current blackboard state, agent execution logs, and step-by-step reasoning traces.
  4. *Warehouse & Fleet Command:* Interactive inventory gauges, stock depletion curves, simulated restocking.
  5. *Fairness & Audit Gatekeeper:* Interactive Gini curve, zone satisfaction ratio comparison bars, audit violation details, and one-click Human-in-the-Loop approval/override switch.
  6. *Scenario Simulator & Re-Planning (What-If):* Injection control panel for secondary disasters, road collapses, and supply cuts with side-by-side plan diff comparison.
  7. *Historical Reports & Analytics:* Searchable SQLite audit logs, CSV dispatch manifest download, automated PDF briefing generation.

### Phase 6: Scenario Validation, University Demonstration & Packaging
- Execute all five mandatory academic evaluation scenarios.
- Verify explainability output: ensure every allocation decision links back to an SOP citation and fairness metric.
- Package demonstration scripts and comprehensive README.
- Final portfolio quality audit for interview presentation.

---

## 2. Specification of the Five University Evaluation Scenarios

To demonstrate the academic rigor and robustness of ReliefOps AI in course CSE476, the system will feature five pre-configured, reproducible evaluation scenarios:

| Scenario ID & Name | Operational Context | Key Agent Stress Test | Success Criteria & Verification Metric |
| :--- | :--- | :--- | :--- |
| **SCEN-01: Baseline Multi-Zone Flood (Rapid Onset)** | 4 affected zones along river valley; 2 regional warehouses operational; moderate resource scarcity (supplies cover ~70% of total demand). | Standard end-to-end coordination; Needs Agent derives demands via SOP RAG; Coordinator executes equitable distribution. | Plan passes Fairness Audit on Iteration 1 with Gini $< 0.20$; zero zones starved; total stock safely reserved. |
| **SCEN-02: Severe Resource Deficit (Mountain Earthquake)** | High-magnitude earthquake with extreme scarcity (total warehouse stock covers only 35% of aggregate demand). Severe trauma in remote zones. | Fairness Auditor prevents greedy allocation to nearest city; enforces guaranteed minimum survival floor for all communities. | No zone receives 0% allocation; high-vulnerability peripheral zones receive critical trauma packs; Gini coefficient remains $< 0.30$. |
| **SCEN-03: Infrastructure Collapse & Logistics Blockade** | Primary bridge washed away; main highway into Zone 4 (`DHEMAJI`) blocked; road condition set to `BLOCKED`. | Logistics Agent identifies route impedance; penalizes road transit; re-routes dispatch to secondary depot; requests aerial drop flag. | System bypasses blocked primary corridor; selects feasible staging depot; transit times updated accurately; no stranded dispatches. |
| **SCEN-04: Mid-Run Dynamic Re-Planning (Secondary Surge)** | While Plan 1 is in `AUDITING` stage, a catastrophic embankment breach surges into Zone 3, doubling affected population and spiking damage from 3 to 5. | Dynamic state invalidation on Blackboard; previous uncommitted holds released; Needs Agent surges Zone 3 priority; real-time plan diff generated. | System automatically invalidates outdated draft; generates Plan Iteration 2; Zone 3 allocation surges; visual diff displays shifted resources. |
| **SCEN-05: Fairness Auditor Veto & Negotiation Loop** | Coordinator is intentionally forced to run an unconstrained greedy cost/distance-minimizing algorithm that gives 0% water to distant Zone 6. | Fairness Auditor detects strict zero-allocation violation and high Gini ($> 0.45$); issues **HARD VETO**; posts floor constraint to Blackboard. | Plan Draft 1 is rejected with detailed audit explanation; Coordinator re-runs with constrained water-filling; Plan Draft 2 passes audit. |

---

## 3. Technology Risk Matrix & Mitigation Strategies

| Technical Risk / Potential Bottleneck | Probability | Impact | Mitigation Strategy Implemented in ReliefOps AI |
| :--- | :--- | :--- | :--- |
| **External LLM Rate Limits or Missing API Keys** | High | High | **Dual-Engine Architecture:** Microsoft Semantic Kernel configured with a seamless deterministic fallback engine. Every agent can execute mathematically pure, rule-based SOP logic offline without external internet or API tokens. |
| **ChromaDB Dependency or Architecture Mismatch** | Medium | Medium | In addition to native ChromaDB vector storage, include a pure Python embedded vector retriever (Cosine Similarity over cached embeddings / BM25 fallback) requiring zero external binary dependencies. |
| **Streamlit State Reset on Widget Interactions** | High | Medium | Store all core state in SQLite and a centralized singleton session manager (`st.session_state['blackboard']`), preventing loss of agent execution state during page navigation. |
| **Long Agent Deliberation Causing UI Freeze** | Medium | Medium | Streamlit asynchronous callbacks with step-by-step progress spinners and real-time event streaming directly from the Blackboard journal. |
| **SQLite Concurrency Contention** | Low | Low | Enforce SQLite Write-Ahead Logging (`PRAGMA journal_mode=WAL`), short atomic transactions, and `threading.Lock` guards on Blackboard writes. |

---

## 4. Portfolio & Interview Readiness Benchmark

To ensure the project serves as an exceptional final-year B.Tech portfolio centerpiece, it will satisfy:
- **Clean Code & Modular Architecture:** Strict separation of concerns (no 1,000-line monolithic files; clean interfaces, Pydantic type validation, docstrings).
- **Academic Soundness:** Direct alignment with multi-agent systems theory (Blackboard pattern, Hayes-Roth coordination, Gini equity metrics).
- **Observable AI & Explainability:** Interactive visual logs showing *why* an agent made a decision, citing specific SOP clauses and math formulas.
- **Production-Grade UI:** High-polish dark-mode Streamlit dashboard with 3D PyDeck maps, dynamic dataframes, and exportable PDF/CSV reports.
- **Reproducibility:** A single command setup with pre-seeded SQLite databases and automated unit/scenario test suites.


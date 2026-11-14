# ReliefOps AI — System Architecture Specification
## Complete Blackboard Multi-Agent Architectural Design
**Document Version:** 1.0.0  
**Target Platform:** Python 3.12+ | Microsoft Semantic Kernel | ChromaDB | SQLite | Streamlit  
**Workspace:** `C:\Users\deeps\.gemini\antigravity\scratch\reliefops_ai`

---

## 1. High-Level Architectural Paradigm: The Blackboard Pattern

ReliefOps AI adopts the classic AI **Blackboard Architecture** (Hayes-Roth, 1985; Nii, 1986), an established multi-agent coordination pattern specifically engineered for ill-structured, multi-constraint, collaborative problem solving under uncertainty.

In contrast to brittle peer-to-peer message passing or rigid sequential pipelines, the Blackboard pattern decouples individual problem-solving modules (**Knowledge Sources / Agents**) from direct dependency on one another. All agents interact strictly through a central, shared, transactional working memory (**The Blackboard**), moderated by a deterministic control and arbitration engine (**The Relief Coordinator**).

```
+--------------------------------------------------------------------------------------------------+
|                                    STREAMLIT PRESENTATION TIER                                   |
|  [Operations Center]  [Disaster Map]  [Blackboard Timeline]  [Inventory]  [Fairness Gate] [Sim]  |
+--------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
|                                    COORDINATION & CONTROL TIER                                   |
|                        Relief Coordinator (Blackboard Controller & Arbiter)                      |
|           - Agent Lifecycle Scheduler        - Mid-Run State Invalidator                         |
|           - Conflict Resolution Engine       - Consensus Convergence Monitor                     |
+--------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
|                                      THE SHARED BLACKBOARD                                       |
|  +-----------------------+  +-----------------------+  +-----------------------+                 |
|  |   Disaster Context    |  |     SOP Guidelines    |  |    Inventory State    |                 |
|  | (Zones, Damage, Pop)  |  |  (Sphere, NDMA norms) |  |   (Depots, Reserves)  |                 |
|  +-----------------------+  +-----------------------+  +-----------------------+                 |
|  +-----------------------+  +-----------------------+  +-----------------------+                 |
|  |    Logistics Matrix   |  |   Allocation Drafts   |  |   Audit & Violations  |                 |
|  |  (Routes, Impedance)  |  |  (Candidate Plans)    |  |  (Gini, Floor Bounds) |                 |
|  +-----------------------+  +-----------------------+  +-----------------------+                 |
|  +-------------------------------------------------------------------------+                 |
|  |            Chronological Event Journal & Agent Action Stream            |                 |
|  +-------------------------------------------------------------------------+                 |
+--------------------------------------------------------------------------------------------------+
          ^                          ^                         ^                         ^
          |                          |                         |                         |
+-------------------+      +-------------------+     +-------------------+     +-------------------+
| Needs Assessment  |      |  Inventory Agent  |     |  Logistics Agent  |     | Fairness Auditor  |
|    Agent (RAG)    |      |                   |     |                   |     |      (Gate)       |
+-------------------+      +-------------------+     +-------------------+     +-------------------+
          |                          |                         |                         |
+-------------------+      +-------------------+     +-------------------+                 |
| ChromaDB (Vector) |      | Inventory Plugin  |     |  Distance Plugin  |                 |
|  - SOP Documents  |      | - SQLite Store    |     | - Route Optimizer |                 |
+-------------------+      +-------------------+     +-------------------+                 |
          |                          |                         |                           |
+--------------------------------------------------------------------------------------------------+
|                                 PERSISTENT DATA & STORAGE TIER                                   |
|                    SQLite Database (ACID Relational State & Historical Logs)                     |
|  - disaster_events  - affected_zones  - warehouses  - inventory  - plans  - audit_trail           |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. Blackboard Internal State Machine & Data Model

The Blackboard is not a simple key-value dictionary; it is a structured, observable state container that tracks versioned hypothesis generation, agent contributions, and state invalidation tags.

### 2.1 Blackboard Data Sections

```python
class BlackboardState(BaseModel):
    plan_id: str
    iteration: int = 1
    status: Literal["INITIALIZING", "ASSESSING", "SOLVING", "AUDITING", "APPROVED", "REVISION_REQUIRED", "RELEASED"]
    
    # Section 1: Disaster Context
    disaster_context: DisasterContext
    
    # Section 2: SOP Knowledge Context (Extracted via RAG)
    sop_context: Dict[str, SOPGuideline]
    
    # Section 3: Available Inventory Snapshot
    inventory_snapshot: Dict[str, WarehouseStock]
    
    # Section 4: Logistics Feasibility Matrix
    logistics_matrix: Dict[Tuple[str, str], RouteMetrics]  # (warehouse_id, zone_id) -> metrics
    
    # Section 5: Zone Need Vectors
    zone_needs: Dict[str, ZoneNeedProfile]  # zone_id -> calculated demand & priority
    
    # Section 6: Candidate Allocation Draft
    allocation_draft: Optional[AllocationPlanDraft]
    
    # Section 7: Fairness Audit Results
    audit_verdict: Optional[FairnessAuditReport]
    
    # Section 8: Event Journal (Chronological append-only trace)
    event_log: List[BlackboardEvent]
```

### 2.2 Blackboard Lifecycle & State Transitions

The execution lifecycle follows a rigorous deterministic state machine:

```
[START]
   |
   v
[INITIALIZING] ──> Coordinator populates disaster context from field reports
   |
   v
[ASSESSING] ─────> Needs Assessment Agent queries ChromaDB SOPs & posts Zone Need Vectors
   |
   v
[SOLVING] ───────> Inventory Agent posts stock snapshot;
                   Logistics Agent posts route feasibility matrix;
                   Coordinator synthesizes candidate Allocation Plan Draft
   |
   v
[AUDITING] ──────> Fairness Auditor Agent evaluates draft against Gini & Zero-Allocation rules
   |
   +---> If AUDIT REJECTED (Gini > threshold OR zero-allocation to vulnerable zone):
   |        |
   |        v
   |     [REVISION_REQUIRED] ──> Coordinator incorporates audit constraints & loops back to [SOLVING]
   |
   +---> If AUDIT PASSED:
            |
            v
         [APPROVED] ──> Human-in-the-Loop review / Automated execution trigger
            |
            v
         [RELEASED] ──> Inventory Agent commits atomic stock deductions to SQLite;
                        Logistics manifests generated; Final report exported.
```

---

## 3. Microsoft Semantic Kernel (Python) Integration Strategy

To ensure genuine compliance with university coursework requirements and avoid naive mock classes, the agent layer is built on the **Microsoft Semantic Kernel (SK)** Python SDK.

### 3.1 Kernel Configuration & Pluggable Architecture

Each agent is equipped with a Semantic Kernel instance or shared Kernel context configured with:
1. **Kernel Plugins:** Distinct functional tools wrapped with `@kernel_function` decorators.
2. **Context Variables (`KernelArguments`):** Passing blackboard slices into prompt templates and function invocations.
3. **Pluggable Execution Connector:**
   - **Production LLM Mode:** Configured with `AzureChatCompletion`, `OpenAIChatCompletion`, or `GoogleAI / Gemini` connectors for natural language interpretation, explanation generation, and nuanced SOP synthesis.
   - **Deterministic Fallback Engine (`MockChatCompletionService` / Deterministic Pipeline):** When API keys are missing or offline mode is toggled, Semantic Kernel executes native Python functions deterministically without breaking the SK abstraction.

### 3.2 Agent Tooling via Semantic Kernel Plugins

```
+------------------------------------------------------------------------------------------+
|                               SEMANTIC KERNEL PLUGIN LAYER                               |
+------------------------------------------------------------------------------------------+
|  +------------------------+  +------------------------+  +-----------------------------+ |
|  | NeedsAssessmentPlugin  |  |    InventoryPlugin     |  |       LogisticsPlugin       | |
|  | - query_sop_guidelines |  | - get_available_stock  |  | - calculate_distance_matrix | |
|  | - calculate_zone_need  |  | - reserve_stock        |  | - evaluate_road_passability | |
|  | - rank_zone_priorities |  | - commit_deduction     |  | - compute_transit_hours     | |
|  +------------------------+  +------------------------+  +-----------------------------+ |
|  +----------------------------------------------------+  +-----------------------------+ |
|  |                 FairnessAuditPlugin                |  |      CoordinatorPlugin      | |
|  | - compute_gini_coefficient                         |  | - synthesize_initial_draft  | |
|  | - verify_minimum_floor                             |  | - apply_audit_constraints   | |
|  | - check_zero_allocation_violations                 |  | - finalize_allocation_plan  | |
|  +----------------------------------------------------+  +-----------------------------+ |
+------------------------------------------------------------------------------------------+
```

---

## 4. Subsystem Component Breakdown

### 4.1 Frontend Tier (Streamlit)
The user interface is structured as a multi-page operational command center with persistent session state:
- **`app.py`:** Main entrypoint, sidebar state navigation, theme injection.
- **Pages & Modules:**
  - `pages/1_Operations_Dashboard.py`: Executive situation report, high-level metrics, active alerts.
  - `pages/2_Disaster_Map.py`: Spatial PyDeck 3D visualization showing zones, warehouses, route vectors, and road statuses.
  - `pages/3_Agent_Blackboard.py`: Live Blackboard monitor, agent timeline, and message exchange inspector.
  - `pages/4_Inventory_Monitoring.py`: Warehouse capacity gauges, itemized stock bars, supply burn rates.
  - `pages/5_Fairness_Auditor.py`: Detailed audit gate, Gini curve, zone satisfaction ratios, approval/override triggers.
  - `pages/6_Scenario_Simulation.py`: Dynamic injection of secondary disasters (aftershock, flood surge), route destruction, and mid-run re-planning comparison.
  - `pages/7_Reports_Analytics.py`: Historical query log, CSV export, and PDF manifest generation.

### 4.2 Backend & Orchestration Tier
- **`backend/blackboard/`**: Thread-safe in-memory Blackboard manager with SQLite transaction mirroring and event journal.
- **`backend/orchestrator/`**: The Relief Coordinator engine that schedules agent execution passes, tracks iteration depth (maximum 3 revision cycles), and enforces convergence.
- **`backend/agents/`**: Isolated modules implementing the five specialized agents using Semantic Kernel.
- **`backend/plugins/`**: Native Kernel plugins housing business logic for inventory querying, geospatial distance, RAG query interfaces, and fairness calculations.

### 4.3 Knowledge & Data Storage Tier
- **`backend/rag/`**: Vector index builder and retriever using ChromaDB.
  - Embedding pipeline: Local ONNX / MiniLM embeddings with graceful string-matching/TF-IDF fallback.
  - Document chunking: Markdown chunking of humanitarian SOPs (Sphere standards, NDMA disaster relief codes).
- **`backend/database/`**: SQLite database engine containing normalized schemas, migrations, seed data scripts, and transaction rollback mechanics.

---

## 5. End-to-End System Data Flow Sequence

The interaction across tiers during a complete allocation and re-planning cycle is illustrated in the sequence below:

```
User/Incident     Coordinator       Needs Agent      Inventory/Logistics     Fairness Auditor      SQLite/Chroma
     |                 |                 |                    |                      |                   |
     |--- Inject ----->|                 |                    |                      |                   |
     |    Disaster     |--- Writes ----->|                    |                      |                   |
     |    Report       |    Context      |                    |                      |                   |
     |                 |                 |--- Query SOPs ----------------------------------------------->| (ChromaDB)
     |                 |                 |<-- Norms/Ratios ----------------------------------------------|
     |                 |                 |--- Post Needs ---->|                      |                   |
     |                 |                 |    & Priority      |                      |                   |
     |                 |                                      |--- Query Stock/Dist -------------------->| (SQLite)
     |                 |                                      |<-- Stock/Distances ----------------------|
     |                 |                                      |--- Post Inventory -> |                   |
     |                 |                                      |    & Route Matrix    |                   |
     |                 |<-- Synthesizes ----------------------|                      |                   |
     |                 |    Draft Plan                                               |                   |
     |                 |--- Posts Draft -------------------------------------------->|                   |
     |                 |                                                             |-- Evaluates Gini  |
     |                 |                                                             |   & Zero-Alloc    |
     |                 |                                                             |                   |
     |                 |<-- [VERDICT: REJECTED / REVISION REQUIRED] -----------------|                   |
     |                 |    (Violations: Zone 4 has 0% water allocation)             |                   |
     |                 |                                                             |                   |
     |                 |-- Re-computes with Guaranteed Floor Constraints             |                   |
     |                 |-- Posts Revised Draft ------------------------------------->|                   |
     |                 |<-- [VERDICT: APPROVED (Gini: 0.18, Min Floor: 45%)] --------|                   |
     |                 |                                                                                 |
     |<-- Present -----|                                                                                 |
     |    for Review   |                                                                                 |
     |--- Approve ---->|                                                                                 |
     |    (HITL)       |--- Commit Deductions ---------------------------------------------------------->| (SQLite)
     |                 |--- Persist Plan & Manifests --------------------------------------------------->|
     |                 |--- Emit Released Status                                                         |
```

---

## 6. Resilience, Fallback & Boundary Specifications

1. **LLM Degradation Boundary:**
   - If OpenAI/Gemini API is unreachable or environment variables are blank, agents seamlessly toggle to the `DeterministicFallbackEngine`.
   - The fallback engine computes exact mathematical formulas (Sphere per-capita demands, linear programming / priority-weighted proportional allocation, and exact Gini index), ensuring the application never crashes or behaves unpredictably.

2. **Concurrency & State Synchronization:**
   - In-memory Blackboard modifications are synchronized using Python `threading.Lock` primitives to prevent race conditions during parallel agent read/write operations.
   - All state transitions write an append-only event to the `blackboard_events` table in SQLite for auditing and replayability.

3. **Re-Planning Invalidation Semantics:**
   - When a mid-run incident update is injected, the Coordinator issues a `STATE_INVALIDATION` event.
   - `zone_needs`, `allocation_draft`, and `audit_verdict` are marked dirty, forcing a fresh pass of Needs Assessment, Inventory check, Logistics re-routing, and Fairness Audit.
   - Any uncommitted stock reservations from the previous draft are safely released.


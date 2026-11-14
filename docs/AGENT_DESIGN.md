# ReliefOps AI — Multi-Agent System & Agent Design Specification
## Deep Design of the Five Specialised Agents, Semantic Kernel Plugins & Blackboard Collaboration
**Document Version:** 1.0.0  
**Framework:** Microsoft Semantic Kernel (Python) | ChromaDB RAG | Blackboard Pattern  
**Course:** CSE476 — Agentic AI and Intelligent Automation  
**Workspace:** `C:\Users\deeps\.gemini\antigravity\scratch\reliefops_ai`

---

## 1. Multi-Agent System Overview

ReliefOps AI implements five distinct, decoupled agent modules. In compliance with the **Blackboard Architecture**, agents do not exchange point-to-point RPC messages; instead, each agent acts as an autonomous **Knowledge Source** that monitors specific slices of the shared Blackboard, evaluates trigger conditions, executes reasoning through **Semantic Kernel Plugins**, and writes validated hypotheses and outputs back to the Blackboard.

```
+-------------------------------------------------------------------------------------------------------+
|                                        SHARED BLACKBOARD STATE                                        |
|  [disaster_context] [sop_context] [zone_needs] [inventory_snapshot] [logistics_matrix] [draft] [audit]|
+-------------------------------------------------------------------------------------------------------+
        |                 |                    |                     |                     |
        v                 v                    v                     v                     v
+---------------+ +---------------+  +-------------------+  +-------------------+  +---------------+
|     NEEDS     | |   INVENTORY   |  |     LOGISTICS     |  |     FAIRNESS      |  |    RELIEF     |
|  ASSESSMENT   | |     AGENT     |  |       AGENT       |  |     AUDITOR       |  |  COORDINATOR  |
|     AGENT     | |               |  |                   |  |      AGENT        |  |               |
|               | |               |  |                   |  | (Approval Gate)   |  | (Controller)  |
| - ChromaDB RAG| | - SQLite Inv  |  | - Distance Tool   |  | - Gini Evaluator  |  | - Arbiter     |
| - SOP Norms   | | - Stock Audit |  | - Route Impedance |  | - Min Floor Check |  | - Allocator   |
| - Priority Sc.| | - Commit      |  | - Transit Matrix  |  | - Veto/Pass Gate  |  | - Re-Planner  |
+---------------+ +---------------+  +-------------------+  +-------------------+  +---------------+
```

---

## 2. Agent 1: Needs Assessment Agent

### 2.1 Role & Objectives
The **Needs Assessment Agent** bridges raw ground-truth disaster telemetry with normative humanitarian standards. It ingests damage reports, retrieves corresponding Standard Operating Procedures (SOPs) from ChromaDB, calculates per-capita resource requirements, and computes a multi-attribute **Zone Priority Score (ZPS)**.

### 2.2 Blackboard Interface
- **Reads from Blackboard:** `disaster_context` (affected zones, population, vulnerability indices, damage severity, medical urgency).
- **Writes to Blackboard:** `sop_context` (retrieved humanitarian guidelines), `zone_needs` (itemized resource demand vectors and calculated priority scores).
- **Activation Trigger:** Dispatched when `status == 'INITIALIZING'` or when a `STATE_INVALIDATION` event signals new disaster data.

### 2.3 Semantic Kernel Plugin: `NeedsAssessmentPlugin`
```python
class NeedsAssessmentPlugin:
    """Semantic Kernel Plugin for SOP retrieval, demand derivation, and zone prioritization."""
    
    @kernel_function(
        name="retrieve_sop_guidelines",
        description="Queries ChromaDB vector store for disaster management SOPs matching hazard type."
    )
    def retrieve_sop_guidelines(self, disaster_type: str, severity: str) -> str:
        """Retrieves minimum Sphere standards and NDMA relief guidelines."""
        ...
        
    @kernel_function(
        name="calculate_zone_demands",
        description="Calculates required quantities of food, water, medical kits, and tents for a zone."
    )
    def calculate_zone_demands(
        self, population: int, vulnerability_idx: float, damage_lvl: int, medical_urgency: float
    ) -> str:
        """Computes standardized per-capita supply vectors."""
        ...

    @kernel_function(
        name="compute_zone_priority",
        description="Calculates composite Zone Priority Score (ZPS) between 0.0 and 100.0."
    )
    def compute_zone_priority(
        self, vulnerability_idx: float, damage_lvl: int, medical_urgency: float, population: int
    ) -> float:
        """Multi-attribute priority formulation."""
        ...
```

### 2.4 Mathematical Formulation: Zone Priority Score (ZPS)
The agent calculates the normalized priority score $P_i \in [0, 100]$ for each zone $i$ using a weighted multi-criteria utility function:

$$P_i = 100 \times \left( w_d \cdot \frac{D_i}{5} + w_v \cdot V_i + w_m \cdot M_i + w_p \cdot \frac{\log_{10}(Pop_i)}{\log_{10}(Pop_{max})} \right)$$

Where:
- $D_i \in [1, 5]$: Infrastructure damage severity (weight $w_d = 0.35$)
- $V_i \in [0, 1]$: Demographic vulnerability index (weight $w_v = 0.25$)
- $M_i \in [0, 1]$: Medical emergency urgency (weight $w_m = 0.25$)
- $Pop_i$: Residing population (weight $w_p = 0.15$)
- $\sum w = 1.0$

### 2.5 SOP RAG Pipeline Integration
1. **Document Ingestion:** The agent references a ChromaDB collection (`disaster_sops`) seeded with curated excerpts from the **Sphere Humanitarian Handbook (2018)** and **NDMA Relief Code**:
   - *Water Supply Standard 2.1:* Minimum 15 liters per person per day for drinking, cooking, and personal hygiene.
   - *Food Security Standard 1.1:* 2,100 kcal per person per day (1 ration pack covers 3 person-days).
   - *Shelter Standard 1:* 1 weatherproof family shelter tent per displaced family (average 5 persons per family; displacement factor $= D_i \times 0.15$).
   - *Health Action Standard 2:* 1 emergency trauma/medical kit per 100 affected persons at medical urgency $\ge 0.70$.
2. **Context Augmentation:** In LLM mode, the agent synthesizes narrative justifications citing the exact retrieved SOP section. In deterministic mode, it calculates the formulas directly from cached SOP constants.

---

## 3. Agent 2: Inventory Agent

### 3.1 Role & Objectives
The **Inventory Agent** maintains authoritative oversight of physical supply availability. It audits stock across regional warehouses, verifies expiration and usability, manages temporary reservations during drafting cycles, and executes atomic stock commitments upon final plan release.

### 3.2 Blackboard Interface
- **Reads from Blackboard:** `zone_needs` (aggregate demand), `allocation_draft` (quantities proposed for dispatch).
- **Writes to Blackboard:** `inventory_snapshot` (available vs. reserved quantities across warehouses), stock deficit alerts.
- **Activation Trigger:** Dispatched when `zone_needs` are posted, and during final commitment after approval.

### 3.3 Semantic Kernel Plugin: `InventoryPlugin`
```python
class InventoryPlugin:
    """Semantic Kernel Plugin for querying and mutating warehouse stock in SQLite."""

    @kernel_function(
        name="get_available_inventory",
        description="Returns current available unreserved stock across all operational warehouses."
    )
    def get_available_inventory(self) -> str:
        """Queries warehouse_inventory table for available quantities."""
        ...

    @kernel_function(
        name="reserve_stock_for_plan",
        description="Places temporary reservation holds on inventory items for an active plan draft."
    )
    def reserve_stock_for_plan(self, plan_id: str, reservations_json: str) -> bool:
        """Updates reserved_quantity in warehouse_inventory."""
        ...

    @kernel_function(
        name="commit_released_allocation",
        description="Permanently deducts allocated stock and releases reservation holds upon approval."
    )
    def commit_released_allocation(self, plan_id: str) -> bool:
        """Executes atomic SQL transaction deducting stock."""
        ...
```

---

## 4. Agent 3: Logistics Agent

### 4.1 Role & Objectives
The **Logistics Agent** computes physical delivery feasibility. It evaluates transit distances between warehouses and destination zones, models road network degradation (e.g., mudslide disruptions, submerged roads), selects optimal origin depots for each zone, and calculates estimated transit hours.

### 4.2 Blackboard Interface
- **Reads from Blackboard:** `disaster_context` (zone coordinates, road access status), `inventory_snapshot` (active warehouses).
- **Writes to Blackboard:** `logistics_matrix` (origin-to-destination distance matrix, road impedance multipliers, transit time estimates).
- **Activation Trigger:** Dispatched concurrently with the Inventory Agent once `disaster_context` is established.

### 4.3 Semantic Kernel Plugin: `LogisticsPlugin`
```python
class LogisticsPlugin:
    """Semantic Kernel Plugin for route distance and transit feasibility modeling."""

    @kernel_function(
        name="calculate_distance_matrix",
        description="Computes great-circle distances and road-adjusted transit distances between depots and zones."
    )
    def calculate_distance_matrix(self, warehouses_json: str, zones_json: str) -> str:
        """Calculates distance matrix incorporating terrain winding factor."""
        ...

    @kernel_function(
        name="estimate_transit_metrics",
        description="Calculates estimated transit hours considering road degradation and vehicle speed."
    )
    def estimate_transit_metrics(self, distance_km: float, road_status: str) -> str:
        """Applies road degradation penalty multipliers."""
        ...
```

### 4.4 Distance & Route Feasibility Algorithm
1. **Haversine Distance Formulation:**
   $$d_{harv} = 2 R \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)}\right)$$
2. **Road Network Winding & Impedance Model:**
   Real-world road distance $D_{eff}$ accounts for terrestrial routing winding ($W_t = 1.35$):
   $$D_{eff} = d_{harv} \times W_t$$
3. **Road Degradation & Transit Duration:**
   Transit time $T_{hours}$ is derived based on access condition:
   $$T_{hours} = \frac{D_{eff}}{V_{base} \times \eta_{road}}$$
   Where $V_{base} = 45 \text{ km/h}$, and the impedance coefficient $\eta_{road}$ is:
   - `OPEN`: $\eta = 1.0$ ($45 \text{ km/h}$)
   - `DEGRADED`: $\eta = 0.50$ ($22.5 \text{ km/h}$)
   - `BLOCKED`: $\eta = 0.15$ (impending air-drop / amphibious transport, $6.75 \text{ km/h}$)
   - `AIR_ONLY`: Specialized aerial corridor calculation ($90 \text{ km/h}$ flight transit).

---

## 5. Agent 4: Fairness Auditor Agent (Mandatory Approval Gate)

### 5.1 Role & Objectives
The **Fairness Auditor Agent** enforces humanitarian ethics and equitable distribution standards. It acts as an **independent, mandatory gatekeeper** that sits between draft synthesis and execution release. It scrutinizes proposed allocations to ensure that vulnerable, peripheral, or less vocal zones are not starved due to pure distance-minimization or naive greedy heuristics.

### 5.2 Blackboard Interface
- **Reads from Blackboard:** `allocation_draft`, `zone_needs`, `inventory_snapshot`.
- **Writes to Blackboard:** `audit_verdict` (status `APPROVED` or `REJECTED`, Gini index, minimum coverage ratio, detected violations, and corrective guidance).
- **Activation Trigger:** Dispatched automatically whenever the Relief Coordinator posts a new `allocation_draft`.

### 5.3 Semantic Kernel Plugin: `FairnessAuditPlugin`
```python
class FairnessAuditPlugin:
    """Semantic Kernel Plugin acting as an automated ethical compliance and equity gatekeeper."""

    @kernel_function(
        name="audit_allocation_equity",
        description="Audits candidate allocation draft against Gini threshold and zero-allocation rules."
    )
    def audit_allocation_equity(self, allocation_draft_json: str, zone_needs_json: str) -> str:
        """Computes fairness metrics and issues binding PASS/FAIL verdict."""
        ...

    @kernel_function(
        name="explain_audit_findings",
        description="Generates natural language breakdown of fairness violations and required revisions."
    )
    def explain_audit_findings(self, violations_json: str, metrics_json: str) -> str:
        """Produces transparent audit report for human commanders and the Coordinator."""
        ...
```

### 5.4 Fairness Metrics & Inviolable Audit Rules

1. **Zone Satisfaction Ratio ($S_{i,r}$):**
   For zone $i$ and resource $r$:
   $$S_{i,r} = \frac{\text{Allocated}_{i,r}}{\text{Need}_{i,r}} \in [0.0, 1.0]$$

2. **Resource-Specific & Mean Gini Coefficient ($G$):**
   The degree of inequality among zone satisfaction ratios is measured using the Gini coefficient:
   $$G_r = \frac{\sum_{i=1}^N \sum_{j=1}^N |S_{i,r} - S_{j,r}|}{2 N \sum_{i=1}^N S_{i,r}}$$
   - **Audit Threshold:** If $G_r > 0.35$ for any essential resource under moderate scarcity, the audit **REJECTS** the draft.

3. **Inviolable Audit Rules:**
   - **Rule 1: Strict Zero-Allocation Ban on High-Need Zones:**
     $$\text{If } Need_{i,r} > 0 \text{ and } ZPS_i \ge 50.0 \text{ and } Stock_r > 0 \implies \text{Allocated}_{i,r} > 0$$
     Allocating zero supplies to an accessible high-priority zone results in an immediate **HARD VETO**.
   - **Rule 2: Guaranteed Minimum Floor Protection:**
     Under global stock ratio $\rho_r = \frac{\text{Total Available}_r}{\text{Total Need}_r}$:
     Every accessible zone must receive at least:
     $$\text{Floor}_{i,r} = \min(0.25 \cdot Need_{i,r}, \rho_r \cdot 0.50 \cdot Need_{i,r})$$
   - **Rule 3: Vulnerability Monotonicity:**
     A zone with higher priority score $ZPS_A > ZPS_B$ must not have a satisfaction ratio significantly lower than zone $B$ ($S_{A,r} \ge S_{B,r} - 0.10$).

---

## 6. Agent 5: Relief Coordinator (Blackboard Controller)

### 6.1 Role & Objectives
The **Relief Coordinator** is the central orchestrator and scheduler of the Blackboard. It drives the problem-solving cycle, synthesizes data from the specialized agents, executes the constrained allocation optimization algorithm, receives feedback from the Fairness Auditor, and controls the re-planning loop.

### 6.2 Blackboard Interface
- **Reads from Blackboard:** All sections (`disaster_context`, `sop_context`, `zone_needs`, `inventory_snapshot`, `logistics_matrix`, `audit_verdict`).
- **Writes to Blackboard:** `status`, `allocation_draft`, finalized release records, blackboard control instructions.
- **Activation Trigger:** Continuous execution cycle controller until consensus or termination.

### 6.3 Semantic Kernel Plugin: `CoordinatorPlugin`
```python
class CoordinatorPlugin:
    """Semantic Kernel Plugin managing blackboard cycle, draft synthesis, and revision adaptation."""

    @kernel_function(
        name="synthesize_allocation_draft",
        description="Synthesizes priority-weighted, logistics-constrained allocation draft across all zones."
    )
    def synthesize_allocation_draft(self, iteration: int, constraints_json: str = "{}") -> str:
        """Solves allocation optimization model respecting active constraints."""
        ...

    @kernel_function(
        name="coordinate_replanning",
        description="Invalidates outdated blackboard state and triggers targeted agent re-runs upon new reports."
    )
    def coordinate_replanning(self, incident_delta_json: str) -> str:
        """Executes mid-run dynamic adaptation."""
        ...
```

### 6.4 The Constrained Multi-Objective Allocation Algorithm
The Coordinator optimizes a multi-objective balance between **Need Fulfillment**, **Priority Weighting**, **Logistics Efficiency**, and **Fairness Bounds**:

$$\max \sum_{i \in Z} \sum_{w \in W} \sum_{r \in R} \left( P_i \cdot \frac{x_{i,w,r}}{Demand_{i,r}} - \lambda \cdot \frac{Dist_{w,i}}{Dist_{max}} \cdot x_{i,w,r} \right)$$

Subject to:
1. **Capacity Constraint:** $\sum_{i \in Z} x_{i,w,r} \le Available_{w,r} \quad \forall w \in W, r \in R$
2. **Demand Cap:** $\sum_{w \in W} x_{i,w,r} \le Demand_{i,r} \quad \forall i \in Z, r \in R$
3. **Fairness Floor (Prescribed by Auditor):** $\sum_{w \in W} x_{i,w,r} \ge \text{Floor}_{i,r} \quad \forall i \in Z$ where $Status_i \neq \text{'BLOCKED'}$
4. **Non-negativity:** $x_{i,w,r} \ge 0$

When solved by the deterministic engine, this executes via a fast **Two-Phase Bounded Water-Filling Algorithm**:
- **Phase 1 (Equity Base):** Allocates the mandatory floor to all valid zones.
- **Phase 2 (Priority Gradient):** Allocates remaining stock proportionally to $P_i \times (Demand_{i,r} - \text{Floor}_{i,r})$ while minimizing delivery transit impedance.

---

## 7. Dynamic Mid-Run Re-Planning Protocol

When external field updates occur during an active operation (e.g., dam breach flooding Zone 3, or landslide blocking Route 2):

```
       New Incident Report Ingested
                   |
                   v
       Coordinator: Emit BLACKBOARD_INVALIDATE
                   |
  +----------------+----------------+
  |                                 |
  v                                 v
Update disaster_context         Release uncommitted
(Zone 3 Damage: 3 -> 5)         inventory reservations
  |                                 |
  +----------------+----------------+
                   |
                   v
Needs Assessment Agent Re-Runs
- Re-queries SOPs for sudden displacement
- Computes new ZPS (Zone 3 priority surges)
                   |
                   v
Logistics Agent Re-Runs
- Re-evaluates road impedance and alternative depots
                   |
                   v
Coordinator Synthesizes Plan Iteration (k + 1)
                   |
                   v
Fairness Auditor Re-Audits Plan
                   |
                   v
New Plan Released & Displayed on Diff UI
```


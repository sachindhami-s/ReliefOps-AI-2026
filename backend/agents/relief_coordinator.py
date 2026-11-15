"""
ReliefOps AI — Relief Coordinator (Blackboard Controller)
Central orchestrator implementing the multi-agent control loop, two-phase water-filling
synthesis, revision management, and final release commitment.

Academic Disclaimer:
Synthetic demonstration agent developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import datetime
import json
import uuid
from typing import Any, Dict, List, Optional
from semantic_kernel import Kernel
from backend.agents.base_agent import BaseAgent
from backend.agents.needs_assessment_agent import NeedsAssessmentAgent
from backend.agents.inventory_agent import InventoryAgent
from backend.agents.logistics_agent import LogisticsAgent
from backend.agents.fairness_auditor_agent import FairnessAuditorAgent
from backend.database.db_manager import DatabaseManager, default_db_manager
from backend.plugins.coordinator_plugin import CoordinatorPlugin
from backend.plugins.inventory_plugin import InventoryPlugin
from backend.utils.logger import observer


class ReliefCoordinator(BaseAgent):
    """
    Relief Coordinator Agent for ReliefOps AI.
    Inherits from BaseAgent, acts as the central Blackboard Controller, orchestrates
    specialized agent execution, synthesizes allocation drafts, and manages audit revisions.
    """

    def __init__(
        self,
        name: str = "ReliefCoordinator",
        kernel: Optional[Kernel] = None,
        blackboard: Optional[Any] = None,
        plugin: Optional[CoordinatorPlugin] = None,
        db: Optional[DatabaseManager] = None,
    ):
        super().__init__(name=name, kernel=kernel, blackboard=blackboard)
        self.plugin = plugin or CoordinatorPlugin()
        self._db = db or default_db_manager
        self._inv_plugin = InventoryPlugin(db=self._db)

        if "Coordinator" not in self.kernel.plugins:
            self.kernel.add_plugin(self.plugin, plugin_name="Coordinator")

    def run_full_coordination_cycle(
        self,
        disaster_context: Optional[Dict[str, Any]] = None,
        max_revisions: int = 3,
        policy: str = "fair",
    ) -> Dict[str, Any]:
        """
        Orchestrates the entire multi-agent disaster response pipeline end-to-end:
        1. Needs Assessment (SOP RAG + demands + ZPS)
        2. Inventory Audit (Supply feasibility)
        3. Logistics Routing (Distance matrix + ETAs)
        4. Allocation Synthesis (Two-phase water-filling)
        5. Fairness & Resource Adequacy Audit (Gini <= 0.35 + zero-allocation check + shortage audit)
        6. Iterative Revision Loop (if fairness requires adjustment)
        7. Final Commitment & Persistence (SQLite)
        """
        self.log(">>> Initiating Multi-Agent Disaster Response Coordination Cycle <<<")

        # Preserve active hazard context across dynamic re-planning cycles if not explicitly overridden
        prior_ctx = self.read_section("disaster_context") or {}
        prior_sop = self.read_section("sop_context") or {}
        prior_hazard = (
            prior_ctx.get("disaster_type")
            or prior_ctx.get("hazard")
            or prior_sop.get("hazard")
            or prior_sop.get("disaster_type")
        )

        # Set disaster context on Blackboard
        if disaster_context:
            self.write_section("disaster_context", disaster_context)

        plan_id = f"PLAN-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8].upper()}"
        event_id = (
            (disaster_context.get("event_id") or prior_ctx.get("event_id") or "EVT-2026-FL01")
            if disaster_context
            else (prior_ctx.get("event_id") or "EVT-2026-FL01")
        )
        raw_hazard = (
            (disaster_context.get("disaster_type") or disaster_context.get("hazard") or prior_hazard or "FLOOD")
            if disaster_context
            else (prior_hazard or "FLOOD")
        )
        disaster_type = str(raw_hazard).strip().upper()
        if disaster_context is not None and isinstance(disaster_context, dict):
            disaster_context["disaster_type"] = disaster_type
            disaster_context["hazard"] = disaster_type
            self.write_section("disaster_context", disaster_context)
        severity = (
            (disaster_context.get("severity") or disaster_context.get("severity_level") or "SEVERE")
            if disaster_context
            else "SEVERE"
        )
        now_init = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Ensure disaster_event exists in SQLite so foreign keys are satisfied
        try:
            self._db.execute_non_query(
                """
                INSERT OR IGNORE INTO disaster_events 
                (event_id, name, disaster_type, severity_level, reported_at, status, total_affected_pop)
                VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?)
                """,
                (
                    event_id,
                    disaster_context.get("name", f"Disaster Response Event {event_id}") if disaster_context else "Disaster Response Event",
                    disaster_type,
                    severity if severity in ("MODERATE", "SEVERE", "CATASTROPHIC") else "SEVERE",
                    now_init,
                    100000,
                ),
            )
        except Exception as exc:
            self.log(f"Notice: event table initialization check: {exc}", level="INFO")

        # 1. Needs Assessment Agent
        needs_agent = NeedsAssessmentAgent(kernel=self.kernel, blackboard=self.blackboard)
        needs_agent.execute(disaster_context)

        # Ensure evaluated zones exist in affected_zones table (batched in a single transaction for 500-zone scalability)
        zone_needs = self.read_section("zone_needs") or []
        zone_batch_params = []
        for zp in zone_needs:
            try:
                zid = zp.get("zone_id")
                zname = zp.get("zone_name", zid)
                zpop = max(1, int(zp.get("affected_population", 1000)))
                zlat = float(zp.get("lat") if zp.get("lat") is not None else 26.5)
                zlon = float(zp.get("lon") if zp.get("lon") is not None else 93.0)
                zvuln = float(zp.get("vulnerability_index", 0.5))
                zdmg = max(1, min(5, int(zp.get("damage_level", 3))))
                zmed = float(zp.get("medical_urgency", 0.5))
                zacc = zp.get("road_status", "OPEN")
                if zacc not in ("OPEN", "DEGRADED", "BLOCKED", "AIR_ONLY"):
                    zacc = "OPEN"
                zone_batch_params.append((zid, event_id, zname, zlat, zlon, zpop, zvuln, zdmg, zmed, zacc))
            except Exception as exc:
                self.log(f"Notice: zone parameter preparation check: {exc}", level="INFO")

        if zone_batch_params:
            try:
                with self._db.transaction() as cur:
                    cur.executemany(
                        """
                        INSERT OR IGNORE INTO affected_zones
                        (zone_id, event_id, name, latitude, longitude, population, vulnerability_index, damage_level, medical_urgency, access_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        zone_batch_params,
                    )
            except Exception as exc:
                self.log(f"Notice: zone table batch initialization check: {exc}", level="INFO")

        # 2. Inventory Agent (using coordinated DB)
        inv_agent = InventoryAgent(kernel=self.kernel, blackboard=self.blackboard, plugin=self._inv_plugin)
        inv_agent.execute()

        # 3. Logistics Agent
        log_agent = LogisticsAgent(kernel=self.kernel, blackboard=self.blackboard)
        log_agent.execute()

        # 4. Synthesis & Audit Revision Loop
        fairness_agent = FairnessAuditorAgent(kernel=self.kernel, blackboard=self.blackboard, db=self._db)

        floor_ratio = 0.30
        iteration = 1
        audit_verdict = None
        allocation_draft = None
        draft_resource_summary = {}

        while iteration <= max_revisions:
            self.log(f"--- Coordination Iteration {iteration}/{max_revisions} (Floor Ratio: {floor_ratio:.2f}) ---")

            # Synthesize draft
            zone_needs = self.read_section("zone_needs")
            inv_snapshot = self.read_section("inventory_snapshot")
            log_matrix = self.read_section("logistics_matrix")

            draft_raw = self.plugin.synthesize_allocation_draft(
                zone_needs_json=zone_needs,
                inventory_snapshot_json=inv_snapshot,
                logistics_matrix_json=log_matrix,
                floor_ratio=floor_ratio,
                policy=policy,
            )
            draft_res = json.loads(draft_raw) if isinstance(draft_raw, str) else draft_raw
            draft_resource_summary = draft_res.get("resource_summary", {})
            allocation_draft = {
                "plan_id": plan_id,
                "iteration": iteration,
                "dispatches": draft_res.get("dispatches", []),
                "total_dispatches": draft_res.get("total_dispatches", 0),
                "resource_summary": draft_resource_summary,
            }
            self.write_section("allocation_draft", allocation_draft)

            # Record plan in AUDITING state so audit logs can link to it
            now_iter = datetime.datetime.now(datetime.timezone.utc).isoformat()
            try:
                self._db.execute_non_query(
                    """
                    INSERT OR REPLACE INTO allocation_plans (plan_id, event_id, iteration, status, created_at)
                    VALUES (?, ?, ?, 'AUDITING', ?)
                    """,
                    (plan_id, event_id, iteration, now_iter),
                )
            except Exception:
                pass

            # Audit draft
            audit_res = fairness_agent.execute()["audit_verdict"]
            verdict = audit_res.get("verdict")

            if verdict == "APPROVED":
                self.log(
                    f"Allocation draft fairness APPROVED on iteration {iteration} "
                    f"(Overall Status: {audit_res.get('overall_status')})."
                )
                audit_verdict = audit_res
                break
            else:
                self.log(
                    f"Iteration {iteration} rejected: {audit_res.get('violations', [])}. Adapting floor ratio...",
                    level="WARNING",
                )
                audit_verdict = audit_res
                floor_ratio = min(0.60, floor_ratio + 0.15)
                iteration += 1

        fairness_verdict = audit_verdict.get("fairness_verdict", "FAIRNESS_REJECTED") if audit_verdict else "FAIRNESS_REJECTED"
        adequacy_status = audit_verdict.get("adequacy_status", "RESOURCE_ADEQUATE") if audit_verdict else "RESOURCE_ADEQUATE"
        overall_status = audit_verdict.get("overall_status", "REJECTED") if audit_verdict else "REJECTED"
        db_status = "APPROVED" if fairness_verdict == "FAIRNESS_APPROVED" else "REJECTED"

        # 5. Commit & Persist
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        dispatches = allocation_draft.get("dispatches", []) if allocation_draft else []

        # Persist Plan to SQLite in an ATOMIC transaction (rolls back on failure)
        try:
            with self._db.transaction() as cur:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO allocation_plans (plan_id, event_id, iteration, status, fairness_score, approved_by, created_at, approved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plan_id,
                        event_id,
                        min(iteration, max_revisions),
                        db_status,
                        audit_verdict.get("gini_coefficient", 0.0) if audit_verdict else 0.0,
                        self.name,
                        now,
                        now,
                    ),
                )

                # Persist itemized dispatches atomically
                for d in dispatches:
                    if d.get("allocated_qty", 0) > 0 and d.get("warehouse_id") != "NONE":
                        cur.execute(
                            """
                            INSERT INTO allocation_items (plan_id, zone_id, warehouse_id, resource_type, requested_qty, allocated_qty, distance_km, est_transit_hours)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                plan_id,
                                d.get("zone_id"),
                                d.get("warehouse_id"),
                                d.get("resource_type"),
                                d.get("requested_qty", 0),
                                d.get("allocated_qty", 0),
                                d.get("distance_km", 0.0),
                                d.get("est_transit_hours", 0.0),
                            ),
                        )
        except Exception as exc:
            self.log(f"Database plan persistence error (rolled back): {exc}", level="WARNING")

        # Build explainability decision audit trail (Phase 6)
        sop_context = self.read_section("sop_context") or {}
        sop_ids = sop_context.get("sop_ids", ["SOP-GENERAL"])
        sop_primary = sop_ids[0] if sop_ids else "SOP-GENERAL"

        decision_audit_trail = {
            "disaster_summary": {
                "event_id": event_id,
                "hazard": disaster_type,
                "disaster_type": disaster_type,
                "severity": severity,
                "governing_sop": sop_primary,
                "policy_executed": policy,
            },
            "zone_explanations": [],
            "shortage_explanations": [],
            "fairness_explanation": "",
        }

        # Build zone-level traceable explanations
        zone_needs = self.read_section("zone_needs") or []
        for zn in zone_needs:
            zid = zn.get("zone_id")
            zname = zn.get("zone_name", zid)
            zps = zn.get("zps", zn.get("zps_score", 0.0))
            rank = zn.get("priority_rank", 1)
            dmg = zn.get("damage_level", 3)
            vuln = zn.get("vulnerability_index", 0.5)
            med = zn.get("medical_urgency", 0.5)
            acc = zn.get("road_status", "OPEN")
            demands = zn.get("demands", {})

            # Summarize allocations for this zone
            zone_allocs = {}
            for d in dispatches:
                if d.get("zone_id") == zid:
                    rtype = d.get("resource_type")
                    zone_allocs[rtype] = zone_allocs.get(rtype, 0) + d.get("allocated_qty", 0)

            reasoning = (
                f"Zone '{zname}' was ranked #{rank} (ZPS {zps:.1f}/100) under {disaster_type} priority weighting. "
                f"Evaluation factors: Damage Severity {dmg}/5, Vulnerability {vuln:.2f}, Medical Urgency {med:.2f}, Access '{acc}'. "
                f"Governing guideline: {sop_primary}. Minimum survival floor was guaranteed before residual allocation."
            )

            decision_audit_trail["zone_explanations"].append({
                "zone_id": zid,
                "zone_name": zname,
                "priority_rank": rank,
                "zps_score": round(zps, 2),
                "damage_level": dmg,
                "vulnerability_index": vuln,
                "medical_urgency": med,
                "access_status": acc,
                "demands": demands,
                "allocations": zone_allocs,
                "priority_reasoning": reasoning,
            })

        resource_summary = audit_verdict.get("resource_adequacy", draft_resource_summary) if audit_verdict else draft_resource_summary
        for rtype, summary in resource_summary.items():
            if summary.get("unfulfilled_qty", 0) > 0:
                deficit = summary.get("unfulfilled_qty", 0)
                dem = summary.get("demanded", 0)
                pct = summary.get("fulfillment_pct", 0.0)
                decision_audit_trail["shortage_explanations"].append({
                    "resource_type": rtype,
                    "demanded": dem,
                    "available": summary.get("available", 0),
                    "allocated": summary.get("allocated", 0),
                    "unfulfilled": deficit,
                    "fulfillment_pct": pct,
                    "explanation": f"{rtype} experienced a {100.0 - pct:.1f}% deficit ({deficit:,} units unmet). Regional depot stocks were exhausted after satisfying guaranteed floor allocations.",
                })

        gini_val = audit_verdict.get("gini_coefficient", 0.0) if audit_verdict else 0.0
        decision_audit_trail["fairness_explanation"] = (
            f"The Fairness Auditor issued verdict '{fairness_verdict}' with Gini coefficient {gini_val:.4f} "
            f"(threshold: <= 0.35). Distributive justice policy '{policy}' guaranteed baseline survival quotas "
            f"to all eligible administrative sectors without starving peripheral or cut-off communities."
        )

        final_plan = {
            "plan_id": plan_id,
            "scenario_id": disaster_context.get("scenario_id") if disaster_context else None,
            "event_id": event_id,
            "hazard": disaster_type,
            "disaster_type": disaster_type,
            "status": overall_status,
            "overall_status": overall_status,
            "fairness_status": fairness_verdict,
            "fairness_verdict": fairness_verdict,
            "adequacy_status": adequacy_status,
            "db_status": db_status,
            "iterations": min(iteration, max_revisions),
            "audit_verdict": audit_verdict,
            "resource_summary": resource_summary,
            "shortage_resources": audit_verdict.get("shortage_resources", []) if audit_verdict else [],
            "shortage_warnings": audit_verdict.get("shortage_warnings", []) if audit_verdict else [],
            "dispatches": dispatches,
            "total_dispatches": len(dispatches),
            "decision_audit_trail": decision_audit_trail,
        }
        self.write_section("final_allocation_plan", final_plan)

        # Structured application observability logging (Phase 4)
        observer.log_allocation_decision(plan_id, policy, len(dispatches), resource_summary)
        observer.log_fairness_audit(
            plan_id,
            gini_val,
            fairness_verdict,
            adequacy_status,
            overall_status,
            len(audit_verdict.get("violations", [])) if audit_verdict else 0,
        )

        self.log(
            f">>> Multi-Agent Coordination Complete. "
            f"Fairness: {fairness_verdict} | Adequacy: {adequacy_status} | Overall Status: {overall_status} <<<"
        )

        return final_plan

    def evaluate_greedy_baseline(
        self,
        disaster_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes and audits a naive greedy cost-minimization allocation plan (SCEN-05 benchmark).
        Demonstrates the mandatory fairness gate by intentionally bypassing the survival floor.
        """
        self.log("Evaluating Naive Greedy Cost-Minimization baseline plan for fairness comparison...")
        zone_needs = self.read_section("zone_needs")
        inv_snapshot = self.read_section("inventory_snapshot")
        log_matrix = self.read_section("logistics_matrix")

        if not zone_needs or not inv_snapshot or not log_matrix:
            if disaster_context:
                self.write_section("disaster_context", disaster_context)
            needs_agent = NeedsAssessmentAgent(kernel=self.kernel, blackboard=self.blackboard)
            needs_agent.execute(disaster_context)
            inv_agent = InventoryAgent(kernel=self.kernel, blackboard=self.blackboard, plugin=self._inv_plugin)
            inv_agent.execute()
            log_agent = LogisticsAgent(kernel=self.kernel, blackboard=self.blackboard)
            log_agent.execute()
            zone_needs = self.read_section("zone_needs")
            inv_snapshot = self.read_section("inventory_snapshot")
            log_matrix = self.read_section("logistics_matrix")

        greedy_raw = self.plugin.synthesize_allocation_draft(
            zone_needs_json=zone_needs,
            inventory_snapshot_json=inv_snapshot,
            logistics_matrix_json=log_matrix,
            floor_ratio=0.0,
            policy="greedy",
        )
        greedy_res = json.loads(greedy_raw) if isinstance(greedy_raw, str) else greedy_raw
        dispatches = greedy_res.get("dispatches", [])

        fairness_agent = FairnessAuditorAgent(kernel=self.kernel, blackboard=self.blackboard, db=self._db)
        audit_raw = fairness_agent.plugin.audit_allocation_equity(
            allocations_json=dispatches,
            zone_demands_json=zone_needs,
            inventory_snapshot_json=inv_snapshot,
        )
        audit_res = json.loads(audit_raw) if isinstance(audit_raw, str) else audit_raw

        return {
            "policy": "greedy",
            "plan_id": f"GREEDY-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8].upper()}",
            "dispatches": dispatches,
            "total_dispatches": len(dispatches),
            "resource_summary": greedy_res.get("resource_summary", {}),
            "audit_verdict": audit_res,
            "fairness_verdict": audit_res.get("fairness_verdict", "FAIRNESS_REJECTED"),
            "gini_coefficient": audit_res.get("gini_coefficient", 1.0),
            "min_coverage_ratio": audit_res.get("min_coverage_ratio", 0.0),
            "zero_allocation_check_passed": audit_res.get("zero_allocation_check_passed", False),
            "violations": audit_res.get("violations", []),
            "shortage_warnings": audit_res.get("shortage_warnings", []),
        }

    def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """BaseAgent execute hook: delegates to run_full_coordination_cycle."""
        disaster_context = (context and context.get("disaster_context")) or context
        plan = self.run_full_coordination_cycle(disaster_context=disaster_context)
        return {"status": "SUCCESS", "final_allocation_plan": plan}

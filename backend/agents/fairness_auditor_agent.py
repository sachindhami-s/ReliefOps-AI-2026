"""
ReliefOps AI — Fairness Auditor Agent
Advanced Distributive Justice and Resource Adequacy Auditing Agent.
Audits allocation plans for Gini coefficient equity, zero-allocation bans,
vulnerability prioritisation, resource fulfillment & shortage percentages,
and writes explainable audit reports to the Blackboard and SQLite database.

Academic Disclaimer:
Synthetic demonstration agent developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import datetime
import json
from typing import Any, Dict, List, Optional
from semantic_kernel import Kernel
from backend.agents.base_agent import BaseAgent
from backend.database.db_manager import DatabaseManager, default_db_manager
from backend.plugins.fairness_plugin import FairnessPlugin


class FairnessAuditorAgent(BaseAgent):
    """
    Advanced Fairness & Resource Adequacy Auditor Agent for ReliefOps AI.
    Inherits from BaseAgent, integrates with Microsoft Semantic Kernel and FairnessPlugin,
    evaluates distributive equity, vulnerability prioritisation, and resource adequacy,
    and writes explainable audit reports to the Blackboard and SQLite database.
    """

    def __init__(
        self,
        name: str = "FairnessAuditorAgent",
        kernel: Optional[Kernel] = None,
        blackboard: Optional[Any] = None,
        plugin: Optional[FairnessPlugin] = None,
        db: Optional[DatabaseManager] = None,
        gini_threshold: float = 0.35,
    ):
        super().__init__(name=name, kernel=kernel, blackboard=blackboard)
        self.gini_threshold: float = float(gini_threshold)
        self.plugin: FairnessPlugin = plugin or FairnessPlugin(gini_threshold=self.gini_threshold)
        self._db: DatabaseManager = db or default_db_manager

        if "Fairness" not in self.kernel.plugins:
            self.kernel.add_plugin(self.plugin, plugin_name="Fairness")

    def evaluate_verdict(
        self,
        fairness_approved: bool,
        has_shortages: bool,
        is_complete_shortage: bool = False,
    ) -> str:
        """
        Verdict Engine evaluator:
        Produces one of: FAIRNESS_APPROVED, RESOURCE_SHORTAGE, APPROVED_WITH_SHORTAGES, REJECTED.
        """
        return self.plugin.determine_verdict(
            fairness_approved=fairness_approved,
            has_shortages=has_shortages,
            is_complete_shortage=is_complete_shortage,
        )

    def audit(
        self,
        allocations: Any,
        zone_demands: Any,
        inventory_snapshot: Optional[Any] = None,
        gini_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Direct programmatic auditing method for allocation equity and resource adequacy.
        """
        threshold = gini_threshold if gini_threshold is not None else self.gini_threshold
        raw_res = self.plugin.audit_allocation_equity(
            allocations_json=allocations,
            zone_demands_json=zone_demands,
            inventory_snapshot_json=inventory_snapshot,
            gini_threshold=threshold,
        )
        return json.loads(raw_res) if isinstance(raw_res, str) else raw_res

    def generate_explainable_report(self, audit_result: Dict[str, Any]) -> str:
        """
        Generates a human-readable, structured Markdown audit report.
        """
        verdict = audit_result.get("audit_verdict") or audit_result.get("overall_status", "UNKNOWN")
        gini = audit_result.get("gini_coefficient", 0.0)
        threshold = audit_result.get("gini_threshold", self.gini_threshold)
        min_cov = audit_result.get("min_coverage_ratio", 0.0)

        lines = [
            f"# ReliefOps AI — Explainable Distributive Justice & Adequacy Report",
            f"**Audit Verdict:** `{verdict}` | **Gini Coefficient:** `{gini:.4f}` (Threshold: `{threshold:.2f}`)",
            f"**Minimum Zone Coverage:** `{min_cov:.1%}`",
            "",
            "## 1. Executive Summary",
            audit_result.get("explanation", "No explanation available."),
            "",
            "## 2. Resource-Wise Adequacy Analysis",
            "| Resource | Requested | Available Stock | Allocated | Fulfilled | Unfulfilled | Fulfilment % | Shortage % | Status |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        res_adeq = audit_result.get("resource_adequacy", {})
        for rtype, info in res_adeq.items():
            lines.append(
                f"| **{rtype}** | {info.get('demanded', 0):,} | {info.get('available', 0):,} | "
                f"{info.get('allocated', 0):,} | {info.get('fulfilled_qty', 0):,} | {info.get('unfulfilled_qty', 0):,} | "
                f"{info.get('fulfillment_pct', 0.0):.1f}% | {info.get('shortage_pct', 0.0):.1f}% | `{info.get('status', 'UNKNOWN')}` |"
            )

        lines.extend([
            "",
            "## 3. Zone-Wise Distributive Fairness Analysis",
            "| Zone | Population | ZPS Score | Total Demanded | Total Allocated | Coverage % | Priority Rationale |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for z in audit_result.get("zone_summaries", []):
            lines.append(
                f"| **{z.get('zone_name')}** | {z.get('population', 0):,} | {z.get('zps', 0.0):.1f} | "
                f"{z.get('total_demanded', 0):,} | {z.get('total_allocated', 0):,} | "
                f"{z.get('coverage_ratio', 0.0):.1%} | {z.get('priority_explanation', 'N/A')} |"
            )

        crit_alerts = audit_result.get("critical_shortage_alerts", [])
        if crit_alerts:
            lines.extend(["", "## 4. Critical Shortage Alerts"])
            for ca in crit_alerts:
                lines.append(f"- {ca}")

        recs = audit_result.get("recommendations", [])
        if recs:
            lines.extend(["", "## 5. Actionable Recommendations"])
            for rec in recs:
                lines.append(f"- 💡 {rec}")

        return "\n".join(lines)

    def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Audits candidate allocations for distributive equity and resource adequacy, writing the verdict to the Blackboard.
        """
        self.log("Beginning distributive justice and resource adequacy audit on allocation draft...")

        # 1. Retrieve allocation draft, zone needs, and inventory snapshot
        allocation_draft = (context and context.get("allocation_draft")) or self.read_section("allocation_draft")
        zone_needs = (context and context.get("zone_needs")) or self.read_section("zone_needs")
        inventory_snapshot = (context and context.get("inventory_snapshot")) or self.read_section("inventory_snapshot")

        if not allocation_draft or not zone_needs:
            self.log("Missing allocation draft or zone needs; audit cannot proceed.", level="WARNING")
            audit_res = self.audit(
                allocations=None,
                zone_demands=None,
                inventory_snapshot=None,
            )
            self.write_section("audit_verdict", audit_res)
            return {"status": "SUCCESS", "audit_verdict": audit_res}

        dispatches = (
            allocation_draft.get("dispatches", allocation_draft)
            if isinstance(allocation_draft, dict)
            else allocation_draft
        )

        # 2. Audit via FairnessPlugin
        audit_res = self.audit(
            allocations=dispatches,
            zone_demands=zone_needs,
            inventory_snapshot=inventory_snapshot,
            gini_threshold=self.gini_threshold,
        )

        verdict = audit_res.get("verdict", "REJECTED")
        audit_verdict = audit_res.get("audit_verdict", "REJECTED")
        fairness_verdict = audit_res.get("fairness_verdict", "FAIRNESS_REJECTED")
        adequacy_status = audit_res.get("adequacy_status", "RESOURCE_ADEQUATE")
        gini = audit_res.get("gini_coefficient", 0.0)
        min_cov = audit_res.get("min_coverage_ratio", 0.0)
        violations = audit_res.get("violations", [])
        shortage_warnings = audit_res.get("shortage_warnings", [])
        explanation = audit_res.get("explanation", "")

        # 3. Write structured audit verdict to Blackboard
        self.write_section("audit_verdict", audit_res)

        # 4. Persist to SQLite audit_logs table (fail-safe)
        # Note: audit_logs.verdict CHECK constraint allows ('APPROVED', 'REJECTED', 'WARNING_OVERRIDDEN')
        db_verdict = "APPROVED" if verdict == "APPROVED" else "REJECTED"
        try:
            plan_id = (
                allocation_draft.get("plan_id", "PLAN-ACTIVE")
                if isinstance(allocation_draft, dict)
                else "PLAN-ACTIVE"
            )
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            combined_issues = violations + shortage_warnings
            self._db.execute_non_query(
                """
                INSERT INTO audit_logs (plan_id, auditor_agent, verdict, gini_coefficient, min_coverage_ratio, violations_json, explanation, audited_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    self.name,
                    db_verdict,
                    gini,
                    min_cov,
                    json.dumps(combined_issues),
                    explanation,
                    now,
                ),
            )
        except Exception as exc:
            self.log(f"Could not persist audit record to database: {exc}", level="WARNING")

        self.log(
            f"Audit finished: Verdict={audit_verdict}, Fairness={fairness_verdict}, Adequacy={adequacy_status}, "
            f"Gini={gini:.4f} (threshold={self.gini_threshold}), "
            f"Min Coverage={min_cov:.1%}, Violations={len(violations)}."
        )

        return {"status": "SUCCESS", "audit_verdict": audit_res}

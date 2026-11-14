"""
ReliefOps AI — Fairness Auditor Agent
Specialized agent responsible for verifying distributive justice, auditing Gini inequality,
enforcing the zero-allocation ban, evaluating resource adequacy, and persisting audit records to SQLite.

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
    Fairness Auditor Agent for ReliefOps AI.
    Inherits from BaseAgent, integrates with Microsoft Semantic Kernel and FairnessPlugin,
    evaluates allocation equity and resource adequacy, and writes audit reports to the Blackboard.
    """

    def __init__(
        self,
        name: str = "FairnessAuditorAgent",
        kernel: Optional[Kernel] = None,
        blackboard: Optional[Any] = None,
        plugin: Optional[FairnessPlugin] = None,
        db: Optional[DatabaseManager] = None,
    ):
        super().__init__(name=name, kernel=kernel, blackboard=blackboard)
        self.plugin = plugin or FairnessPlugin()
        self._db = db or default_db_manager

        if "Fairness" not in self.kernel.plugins:
            self.kernel.add_plugin(self.plugin, plugin_name="Fairness")

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
            audit_res = {
                "verdict": "REJECTED",
                "fairness_verdict": "FAIRNESS_REJECTED",
                "adequacy_status": "RESOURCE_SHORTAGE",
                "overall_status": "REJECTED",
                "gini_coefficient": 1.0,
                "min_coverage_ratio": 0.0,
                "violations": ["Missing allocation draft or zone needs."],
                "shortage_resources": [],
                "shortage_warnings": [],
                "resource_adequacy": {},
                "explanation": "Insufficient data to audit allocation equity.",
            }
            self.write_section("audit_verdict", audit_res)
            return {"status": "SUCCESS", "audit_verdict": audit_res}

        dispatches = allocation_draft.get("dispatches", allocation_draft) if isinstance(allocation_draft, dict) else allocation_draft

        # 2. Audit via FairnessPlugin
        audit_raw = self.plugin.audit_allocation_equity(
            allocations_json=dispatches,
            zone_demands_json=zone_needs,
            inventory_snapshot_json=inventory_snapshot,
        )
        audit_res = json.loads(audit_raw) if isinstance(audit_raw, str) else audit_raw

        verdict = audit_res.get("verdict", "REJECTED")
        fairness_verdict = audit_res.get("fairness_verdict", "FAIRNESS_REJECTED")
        adequacy_status = audit_res.get("adequacy_status", "RESOURCE_ADEQUATE")
        overall_status = audit_res.get("overall_status", "REJECTED")
        gini = audit_res.get("gini_coefficient", 0.0)
        min_cov = audit_res.get("min_coverage_ratio", 0.0)
        violations = audit_res.get("violations", [])
        shortage_warnings = audit_res.get("shortage_warnings", [])
        explanation = audit_res.get("explanation", "")

        # 3. Write to Blackboard
        self.write_section("audit_verdict", audit_res)

        # 4. Persist to SQLite audit_logs table (fail-safe)
        # Note: audit_logs.verdict CHECK constraint allows ('APPROVED', 'REJECTED', 'WARNING_OVERRIDDEN')
        db_verdict = "APPROVED" if verdict == "APPROVED" else "REJECTED"
        try:
            plan_id = allocation_draft.get("plan_id", "PLAN-ACTIVE") if isinstance(allocation_draft, dict) else "PLAN-ACTIVE"
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
            f"Audit finished: Fairness={fairness_verdict}, Adequacy={adequacy_status}, Overall={overall_status}, "
            f"Gini={gini:.4f} (threshold={self.plugin.GINI_THRESHOLD}), "
            f"Min Coverage={min_cov:.1%}, Violations={len(violations)}."
        )

        return {"status": "SUCCESS", "audit_verdict": audit_res}

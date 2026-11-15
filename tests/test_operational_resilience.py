"""
ReliefOps AI — Phase 4 & Phase 6: Operational Resilience & Performance Benchmarking Suite
Validates multi-agent communication integrity, blackboard snapshot isolation, error handling,
repeated execution idempotency, and actual latency/memory performance metrics.

Academic Disclaimer:
Synthetic test suite developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import json
import time
import unittest
from typing import Any, Dict, List

from backend.agents.fairness_auditor_agent import FairnessAuditorAgent
from backend.agents.inventory_agent import InventoryAgent
from backend.agents.logistics_agent import LogisticsAgent
from backend.agents.needs_assessment_agent import NeedsAssessmentAgent
from backend.plugins.coordinator_plugin import CoordinatorPlugin
from backend.plugins.fairness_plugin import FairnessPlugin
from backend.plugins.needs_plugin import NeedsAssessmentPlugin
from tests.stress_fixtures import IsolatedStressEnvironment, STRESS_SCENARIOS


class TestOperationalResilience(unittest.TestCase):
    """
    Validates inter-agent protocol reliability, blackboard transaction safety,
    fault tolerance, and measures actual operational execution benchmarks.
    """

    def setUp(self):
        self.env = IsolatedStressEnvironment()

    def tearDown(self):
        self.env.cleanup()

    def test_01_multi_agent_metadata_consistency(self):
        """1. Multi-Agent Consistency: Needs, Inventory, Logistics, Fairness, and Coordinator agree on disaster metadata."""
        sc = STRESS_SCENARIOS["SCEN_03_SEVERE_EARTHQUAKE"]
        plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc)

        # Check blackboard sections for metadata consistency
        ctx = self.env.blackboard.read("disaster_context")
        sop_ctx = self.env.blackboard.read("sop_context")
        zone_needs = self.env.blackboard.read("zone_needs")
        inv_snap = self.env.blackboard.read("inventory_snapshot")
        log_mat = self.env.blackboard.read("logistics_matrix")
        final_plan = self.env.blackboard.read("final_allocation_plan")

        self.assertEqual(ctx.get("event_id"), sc["event_id"])
        self.assertEqual(ctx.get("disaster_type"), "EARTHQUAKE")
        self.assertEqual(sop_ctx.get("disaster_type"), "EARTHQUAKE")
        self.assertEqual(final_plan.get("event_id"), sc["event_id"])

        # All zones in needs assessment must match zones in logistics matrix
        needs_zids = {z["zone_id"] for z in zone_needs}
        log_zids = {r["zone_id"] for r in log_mat.get("matrix", [])}
        self.assertEqual(needs_zids, log_zids)

    def test_02_blackboard_snapshot_isolation(self):
        """2. Blackboard Isolation: Snapshots are immutable representations of state at time of capture."""
        sc = STRESS_SCENARIOS["SCEN_01_BASELINE_FLOOD"]
        snap_before = self.env.blackboard.get_snapshot()

        plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc)
        snap_after = self.env.blackboard.get_snapshot()

        # Before snapshot must not contain allocation draft or final plan
        self.assertNotIn("final_allocation_plan", snap_before)
        self.assertIn("final_allocation_plan", snap_after)
        self.assertEqual(snap_after["final_allocation_plan"]["plan_id"], plan["plan_id"])

    def test_03_invalid_agent_inputs_handled_safely(self):
        """3. Fault Tolerance: Invalid or malformed JSON inputs do not crash synthesis or fairness auditing plugins."""
        coord_plugin = CoordinatorPlugin()
        fairness_plugin = FairnessPlugin()

        # A. Malformed JSON to synthesize_allocation_draft
        raw_res = coord_plugin.synthesize_allocation_draft(
            zone_needs_json="MALFORMED_NON_JSON",
            inventory_snapshot_json="{}",
            logistics_matrix_json="{}",
        )
        res = json.loads(raw_res)
        self.assertFalse(res.get("success", False))
        self.assertEqual(res.get("total_dispatches"), 0)

        # B. None/empty inputs to audit_allocation_equity
        audit_res_raw = fairness_plugin.audit_allocation_equity(
            allocations_json=None,
            zone_demands_json=None,
        )
        audit_res = json.loads(audit_res_raw)
        self.assertEqual(audit_res.get("verdict"), "REJECTED")
        self.assertFalse(audit_res.get("success", True))
        self.assertIn("invalid", audit_res.get("explanation", "").lower())

    def test_04_failed_operations_prevent_database_corruption(self):
        """4. Transaction Safety: Missing or empty zones context fails gracefully without creating orphan DB records."""
        empty_ctx = {
            "event_id": "EVT-STRESS-EMPTY",
            "disaster_type": "FLOOD",
            "zones": [],
        }
        plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=empty_ctx)

        # Plan dispatches must be empty
        self.assertEqual(len(plan.get("dispatches", [])), 0)
        # Database allocation_items must not contain records for this plan
        items = self.env.db.execute_query(
            "SELECT * FROM allocation_items WHERE plan_id = ?",
            (plan.get("plan_id"),),
        )
        self.assertEqual(len(items), 0)

    def test_05_repeated_coordination_idempotency(self):
        """5. Idempotency: Repeated execution cycles succeed cleanly without primary key collisions or side effects."""
        sc = STRESS_SCENARIOS["SCEN_05_SEVERE_CYCLONE"]

        for i in range(3):
            # Advance event_id suffix to test distinct cycles
            sc_iter = dict(sc)
            sc_iter["event_id"] = f"{sc['event_id']}-ITER-{i}"
            plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc_iter)
            self.assertEqual(plan.get("fairness_verdict"), "FAIRNESS_APPROVED")
            self.assertGreater(len(plan.get("dispatches", [])), 0)

    def test_06_performance_benchmarking_latencies(self):
        """6. Performance: Measure component and end-to-end latencies (SOP, synthesis, audit, replanning)."""
        sc = STRESS_SCENARIOS["SCEN_01_BASELINE_FLOOD"]
        needs_plugin = NeedsAssessmentPlugin()
        coord_plugin = CoordinatorPlugin()
        fairness_plugin = FairnessPlugin()

        # A. Measure SOP RAG Retrieval Latency
        t0 = time.perf_counter()
        raw_sop = needs_plugin.retrieve_sop_guidelines("FLOOD", "Level 2 (Moderate Inundation)")
        sop_latency_ms = (time.perf_counter() - t0) * 1000.0
        self.assertLess(sop_latency_ms, 2500.0, f"SOP retrieval too slow: {sop_latency_ms:.2f}ms")

        # B. Measure End-to-End Coordination Latency
        t0 = time.perf_counter()
        plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc)
        e2e_latency_ms = (time.perf_counter() - t0) * 1000.0
        self.assertLess(e2e_latency_ms, 5000.0, f"End-to-end coordination too slow: {e2e_latency_ms:.2f}ms")

        # C. Measure Synthesis Draft Computation Latency
        zone_needs = self.env.blackboard.read("zone_needs")
        inv_snap = self.env.blackboard.read("inventory_snapshot")
        log_mat = self.env.blackboard.read("logistics_matrix")

        t0 = time.perf_counter()
        coord_plugin.synthesize_allocation_draft(
            zone_needs_json=zone_needs,
            inventory_snapshot_json=inv_snap,
            logistics_matrix_json=log_mat,
        )
        synthesis_latency_ms = (time.perf_counter() - t0) * 1000.0
        self.assertLess(synthesis_latency_ms, 500.0, f"Synthesis too slow: {synthesis_latency_ms:.2f}ms")

        # D. Measure Fairness Audit Latency
        t0 = time.perf_counter()
        fairness_plugin.audit_allocation_equity(
            allocations_json=plan.get("dispatches", []),
            zone_demands_json=zone_needs,
            inventory_snapshot_json=inv_snap,
        )
        audit_latency_ms = (time.perf_counter() - t0) * 1000.0
        self.assertLess(audit_latency_ms, 500.0, f"Fairness audit too slow: {audit_latency_ms:.2f}ms")

        # Log measured performance
        print(f"\n--- Operational Performance Benchmarks ---")
        print(f"  SOP RAG Retrieval Latency:      {sop_latency_ms:.2f} ms")
        print(f"  Allocation Synthesis Latency:    {synthesis_latency_ms:.2f} ms")
        print(f"  Fairness Audit Latency:          {audit_latency_ms:.2f} ms")
        print(f"  End-to-End Coordination Latency: {e2e_latency_ms:.2f} ms")

    def test_07_repeated_execution_stability_and_memory(self):
        """7. Stability: Run 5 consecutive coordination cycles to verify no degradation or instability."""
        sc = STRESS_SCENARIOS["SCEN_07_SEVERE_LANDSLIDE"]
        durations: List[float] = []

        for i in range(5):
            t0 = time.perf_counter()
            plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc)
            durations.append((time.perf_counter() - t0) * 1000.0)
            self.assertEqual(plan.get("fairness_verdict"), "FAIRNESS_APPROVED")

        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)
        print(f"\n--- 5-Cycle Stability Measurements ---")
        print(f"  Average Cycle Latency: {avg_duration:.2f} ms")
        print(f"  Maximum Cycle Latency: {max_duration:.2f} ms")
        self.assertLess(max_duration, 5000.0)


if __name__ == "__main__":
    unittest.main()

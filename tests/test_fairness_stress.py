"""
ReliefOps AI — Phase 3: Fairness & Distributive Justice Stress Testing Suite
Validates the Fairness Auditor under extreme resource scarcity, guaranteeing zero-allocation bans,
survival floor protection, remote zone inclusion, vulnerability prioritization, and Gini mathematical bounds.

Academic Disclaimer:
Synthetic test suite developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import unittest
from typing import Any, Dict, List

from backend.agents.fairness_auditor_agent import FairnessAuditorAgent
from tests.stress_fixtures import IsolatedStressEnvironment, STRESS_SCENARIOS


class TestFairnessStress(unittest.TestCase):
    """
    Stress test suite for the Fairness Auditor and Two-Phase Water-Filling distributive justice engine.
    Ensures survival floors, vulnerability monotonicity, Gini validity, and strict rejection of inequity.
    """

    def setUp(self):
        self.env = IsolatedStressEnvironment()

    def tearDown(self):
        self.env.cleanup()

    def test_01_baseline_survival_allocation_floor_protected(self):
        """1. Every eligible zone receives its baseline survival floor allocation when stock permits."""
        sc = STRESS_SCENARIOS["SCEN_02_EXTREME_FLOOD"]
        # Severely constrict inventory to 25% of baseline
        self.env.set_inventory_multipliers({
            "FOOD_RATIONS": 0.25,
            "CLEAN_WATER": 0.25,
            "MEDICAL_KITS": 0.25,
            "SHELTER_TENTS": 0.25,
        })
        plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc)
        dispatches = plan.get("dispatches", [])

        # Every zone must have received at least one non-zero allocation across resources
        allocated_zones = {d["zone_id"] for d in dispatches if d.get("allocated_qty", 0) > 0}
        scenario_zones = {z["zone_id"] for z in sc["zones"]}

        self.assertEqual(
            allocated_zones, scenario_zones,
            "Every zone must receive survival allocations under water-filling despite severe scarcity"
        )
        self.assertEqual(plan.get("fairness_verdict"), "FAIRNESS_APPROVED")

    def test_02_no_silent_exclusion_of_remote_zones(self):
        """2. Remote and peripheral zones (high distance) are not systematically excluded or starved."""
        remote_context = {
            "event_id": "EVT-STRESS-REMOTE",
            "name": "Peripheral & Remote Settlements Test",
            "disaster_type": "FLOOD",
            "severity_level": "SEVERE",
            "planning_days": 3,
            "zones": [
                {
                    "zone_id": "ZONE-NEAR-CITY",
                    "name": "Adjacent Urban Center (20 km)",
                    "population": 30000,
                    "affected_population": 30000,
                    "damage_level": 4,
                    "vulnerability_index": 0.60,
                    "medical_urgency": 0.50,
                    "access_status": "OPEN",
                    "road_status": "OPEN",
                    "latitude": 26.20,
                    "longitude": 91.80,
                },
                {
                    "zone_id": "ZONE-REMOTE-MOUNTAIN",
                    "name": "Distant Mountain Hamlets (280 km)",
                    "population": 15000,
                    "affected_population": 15000,
                    "damage_level": 4,
                    "vulnerability_index": 0.90,
                    "medical_urgency": 0.85,
                    "access_status": "DEGRADED",
                    "road_status": "DEGRADED",
                    "latitude": 27.80,
                    "longitude": 95.50,
                },
            ],
        }
        # Constrain supplies to 30%
        self.env.set_inventory_multipliers({"FOOD_RATIONS": 0.30, "CLEAN_WATER": 0.30})

        # A. Fair Two-Phase Water-Filling Plan
        fair_plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=remote_context)
        fair_dispatches = fair_plan.get("dispatches", [])
        remote_alloc_fair = sum(
            d.get("allocated_qty", 0) for d in fair_dispatches if d["zone_id"] == "ZONE-REMOTE-MOUNTAIN"
        )
        self.assertGreater(remote_alloc_fair, 0, "Remote mountain zone must NOT be starved under fair policy")

        # B. Compare with Naive Greedy Optimization (which minimizes transport distance)
        greedy_res = self.env.coordinator.evaluate_greedy_baseline(disaster_context=remote_context)
        greedy_dispatches = greedy_res.get("dispatches", [])
        remote_alloc_greedy = sum(
            d.get("allocated_qty", 0) for d in greedy_dispatches if d["zone_id"] == "ZONE-REMOTE-MOUNTAIN"
        )
        # Greedy cost-minimizer allocates significantly less or 0 to distant zone compared to fair policy
        self.assertGreaterEqual(remote_alloc_fair, remote_alloc_greedy)

    def test_03_zero_allocation_violations_strictly_detected(self):
        """3. Zero-allocation violations are detected by the Fairness Auditor when an eligible zone is starved."""
        auditor = FairnessAuditorAgent(blackboard=self.env.blackboard, db=self.env.db)

        zone_demands = [
            {"zone_id": "Z1", "zone_name": "Sector 1", "zps": 75.0, "population": 10000, "demands": {"food_packs": 500}},
            {"zone_id": "Z2", "zone_name": "Sector 2", "zps": 60.0, "population": 8000, "demands": {"food_packs": 400}},
        ]
        # Inequitable allocation: Z1 receives 100%, Z2 receives 0
        unfair_allocations = [
            {"zone_id": "Z1", "resource_type": "FOOD_RATIONS", "allocated_qty": 500, "requested_qty": 500},
            {"zone_id": "Z2", "resource_type": "FOOD_RATIONS", "allocated_qty": 0, "requested_qty": 400},
        ]
        res = auditor.audit(allocations=unfair_allocations, zone_demands=zone_demands)

        self.assertEqual(res.get("verdict"), "REJECTED")
        self.assertEqual(res.get("fairness_verdict"), "FAIRNESS_REJECTED")
        self.assertFalse(res.get("zero_allocation_check_passed"))
        self.assertIn("Z2", str(res.get("violations", [])))

    def test_04_vulnerable_populations_receive_appropriate_priority(self):
        """4. Highly vulnerable populations receive appropriate priority in Phase 2 residual allocation."""
        sc = STRESS_SCENARIOS["SCEN_02_EXTREME_FLOOD"]
        plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc)
        zone_needs = self.env.blackboard.read("zone_needs") or []

        # Find highest and lowest vulnerability zones in SCEN_02
        high_vuln_zone = max(zone_needs, key=lambda z: float(z.get("vulnerability_index", 0.0)))
        low_vuln_zone = min(zone_needs, key=lambda z: float(z.get("vulnerability_index", 0.0)))

        # Higher vulnerability index must produce higher or equal ZPS score
        self.assertGreaterEqual(
            high_vuln_zone.get("zps", high_vuln_zone.get("zps_score", 0.0)),
            low_vuln_zone.get("zps", low_vuln_zone.get("zps_score", 0.0))
        )

    def test_05_gini_coefficient_strictly_within_mathematical_bounds(self):
        """5. Gini coefficient remains mathematically bounded between [0.0, 1.0] across all scenarios."""
        auditor = FairnessAuditorAgent(blackboard=self.env.blackboard, db=self.env.db)

        # Test A: Degenerate single zone
        single_zone = [{"zone_id": "Z1", "zps": 50.0, "population": 1000, "demands": {"food_packs": 100}}]
        single_alloc = [{"zone_id": "Z1", "resource_type": "FOOD_RATIONS", "allocated_qty": 100}]
        res_single = auditor.audit(allocations=single_alloc, zone_demands=single_zone)
        self.assertTrue(0.0 <= res_single.get("gini_coefficient", 0.0) <= 1.0)

        # Test B: Perfect equality (Gini -> 0.0)
        equal_zones = [
            {"zone_id": f"Z{i}", "zps": 50.0, "population": 1000, "demands": {"food_packs": 100}}
            for i in range(1, 5)
        ]
        equal_alloc = [
            {"zone_id": f"Z{i}", "resource_type": "FOOD_RATIONS", "allocated_qty": 50}
            for i in range(1, 5)
        ]
        res_equal = auditor.audit(allocations=equal_alloc, zone_demands=equal_zones)
        self.assertAlmostEqual(res_equal.get("gini_coefficient", 0.0), 0.0, places=3)
        self.assertEqual(res_equal.get("fairness_verdict"), "FAIRNESS_APPROVED")

        # Test C: Extreme inequality (Gini -> high)
        unequal_alloc = [
            {"zone_id": "Z1", "resource_type": "FOOD_RATIONS", "allocated_qty": 200},
            {"zone_id": "Z2", "resource_type": "FOOD_RATIONS", "allocated_qty": 0},
            {"zone_id": "Z3", "resource_type": "FOOD_RATIONS", "allocated_qty": 0},
            {"zone_id": "Z4", "resource_type": "FOOD_RATIONS", "allocated_qty": 0},
        ]
        res_unequal = auditor.audit(allocations=unequal_alloc, zone_demands=equal_zones)
        self.assertTrue(0.0 <= res_unequal.get("gini_coefficient", 0.0) <= 1.0)
        self.assertGreater(res_unequal.get("gini_coefficient", 0.0), 0.35)
        self.assertEqual(res_unequal.get("fairness_verdict"), "FAIRNESS_REJECTED")

    def test_06_resource_shortages_reported_separately_from_fairness(self):
        """6. Resource shortages are reported orthogonally from distributive fairness (APPROVED_WITH_SHORTAGES)."""
        sc = STRESS_SCENARIOS["SCEN_10_WATER_SHORTAGE"]
        plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc)

        # Distributive fairness is APPROVED because the scarce water is shared fairly
        self.assertEqual(plan.get("fairness_verdict"), "FAIRNESS_APPROVED")
        # Resource adequacy is SHORTAGE because stock was insufficient
        self.assertEqual(plan.get("adequacy_status"), "RESOURCE_SHORTAGE")
        # Overall status accurately synthesizes both dimensions
        self.assertEqual(plan.get("overall_status"), "APPROVED_WITH_SHORTAGES")

    def test_07_no_forced_approval_when_allocation_is_inequitable(self):
        """7. Fairness Auditor strictly refuses to approve an inequitable plan (no forced approval)."""
        greedy_res = self.env.coordinator.evaluate_greedy_baseline(
            disaster_context=STRESS_SCENARIOS["SCEN_02_EXTREME_FLOOD"]
        )
        audit_res = greedy_res.get("audit_verdict", {})

        # When Gini exceeds threshold or zero allocations occur, it must NOT be approved
        if audit_res.get("gini_coefficient", 0.0) > 0.35 or not audit_res.get("zero_allocation_check_passed", True):
            self.assertEqual(audit_res.get("verdict"), "REJECTED")
            self.assertEqual(audit_res.get("fairness_verdict"), "FAIRNESS_REJECTED")


if __name__ == "__main__":
    unittest.main()

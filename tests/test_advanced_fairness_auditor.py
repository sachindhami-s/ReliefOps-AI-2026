"""
ReliefOps AI — Advanced Fairness & Resource Adequacy Auditor Agent Test Suite
Comprehensive unit and integration tests verifying distributive justice, Gini coefficient thresholds,
vulnerability prioritisation, resource adequacy, dynamic replanning audit, and verdict engine.

Academic Disclaimer:
Synthetic test suite developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import json
import os
import tempfile
import unittest
from backend.agents.fairness_auditor_agent import FairnessAuditorAgent
from backend.blackboard.blackboard_manager import BlackboardManager
from backend.database.db_manager import DatabaseManager
from backend.database.seeder import seed_database
from backend.plugins.fairness_plugin import FairnessPlugin


class TestAdvancedFairnessAuditor(unittest.TestCase):
    """Test suite covering the 10 core audit capabilities of FairnessAuditorAgent and FairnessPlugin."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_fairness.db")
        self.db = DatabaseManager(self.db_path)
        seed_database(self.db)
        self.bb = BlackboardManager(db=self.db)
        self.plugin = FairnessPlugin(gini_threshold=0.35)
        self.agent = FairnessAuditorAgent(blackboard=self.bb, plugin=self.plugin, db=self.db)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_1_perfectly_equal_allocation(self):
        """1. Verify perfectly equal allocation yields Gini ~ 0.0 and FAIRNESS_APPROVED."""
        zones = [
            {"zone_id": "Z1", "zone_name": "Sector Alpha", "zps": 75.0, "population": 5000, "demands": {"water_liters": 10000, "food_packs": 500}},
            {"zone_id": "Z2", "zone_name": "Sector Beta", "zps": 75.0, "population": 5000, "demands": {"water_liters": 10000, "food_packs": 500}},
            {"zone_id": "Z3", "zone_name": "Sector Gamma", "zps": 75.0, "population": 5000, "demands": {"water_liters": 10000, "food_packs": 500}},
            {"zone_id": "Z4", "zone_name": "Sector Delta", "zps": 75.0, "population": 5000, "demands": {"water_liters": 10000, "food_packs": 500}},
        ]
        # Exactly 50% coverage to each zone
        dispatches = [
            {"zone_id": "Z1", "resource_type": "CLEAN_WATER", "allocated_qty": 5000},
            {"zone_id": "Z1", "resource_type": "FOOD_RATIONS", "allocated_qty": 250},
            {"zone_id": "Z2", "resource_type": "CLEAN_WATER", "allocated_qty": 5000},
            {"zone_id": "Z2", "resource_type": "FOOD_RATIONS", "allocated_qty": 250},
            {"zone_id": "Z3", "resource_type": "CLEAN_WATER", "allocated_qty": 5000},
            {"zone_id": "Z3", "resource_type": "FOOD_RATIONS", "allocated_qty": 250},
            {"zone_id": "Z4", "resource_type": "CLEAN_WATER", "allocated_qty": 5000},
            {"zone_id": "Z4", "resource_type": "FOOD_RATIONS", "allocated_qty": 250},
        ]
        res = self.agent.audit(allocations=dispatches, zone_demands=zones)

        self.assertAlmostEqual(res["gini_coefficient"], 0.0, places=3)
        self.assertEqual(res["fairness_verdict"], "FAIRNESS_APPROVED")
        self.assertTrue(res["zero_allocation_check_passed"])
        self.assertEqual(res["verdict"], "APPROVED")

    def test_2_unequal_resource_allocation(self):
        """2. Verify unequal allocation increases Gini and is captured in zone-wise analysis."""
        zones = [
            {"zone_id": "Z1", "zone_name": "Zone 1", "zps": 60.0, "population": 2000, "demands": {"food_packs": 100}},
            {"zone_id": "Z2", "zone_name": "Zone 2", "zps": 60.0, "population": 2000, "demands": {"food_packs": 100}},
            {"zone_id": "Z3", "zone_name": "Zone 3", "zps": 60.0, "population": 2000, "demands": {"food_packs": 100}},
            {"zone_id": "Z4", "zone_name": "Zone 4", "zps": 60.0, "population": 2000, "demands": {"food_packs": 100}},
        ]
        # Skewed dispatches: Z1 gets 100%, others get 10%
        dispatches = [
            {"zone_id": "Z1", "resource_type": "FOOD_RATIONS", "allocated_qty": 100},
            {"zone_id": "Z2", "resource_type": "FOOD_RATIONS", "allocated_qty": 10},
            {"zone_id": "Z3", "resource_type": "FOOD_RATIONS", "allocated_qty": 10},
            {"zone_id": "Z4", "resource_type": "FOOD_RATIONS", "allocated_qty": 10},
        ]
        res = self.agent.audit(allocations=dispatches, zone_demands=zones)

        self.assertGreater(res["gini_coefficient"], 0.35)
        self.assertEqual(len(res["zone_summaries"]), 4)
        covs = [z["coverage_ratio"] for z in res["zone_summaries"]]
        self.assertEqual(max(covs), 1.0)
        self.assertEqual(min(covs), 0.1)

    def test_3_gini_threshold_violation(self):
        """3. Verify exceeding the Gini threshold results in REJECTED verdict and fairness failure."""
        zones = [
            {"zone_id": "Z1", "zone_name": "Favored Zone", "zps": 50.0, "population": 1000, "demands": {"food_packs": 100}},
            {"zone_id": "Z2", "zone_name": "Deprived Zone 1", "zps": 50.0, "population": 1000, "demands": {"food_packs": 100}},
            {"zone_id": "Z3", "zone_name": "Deprived Zone 2", "zps": 50.0, "population": 1000, "demands": {"food_packs": 100}},
            {"zone_id": "Z4", "zone_name": "Deprived Zone 3", "zps": 50.0, "population": 1000, "demands": {"food_packs": 100}},
        ]
        dispatches = [
            {"zone_id": "Z1", "resource_type": "FOOD_RATIONS", "allocated_qty": 100},
            {"zone_id": "Z2", "resource_type": "FOOD_RATIONS", "allocated_qty": 5},
            {"zone_id": "Z3", "resource_type": "FOOD_RATIONS", "allocated_qty": 5},
            {"zone_id": "Z4", "resource_type": "FOOD_RATIONS", "allocated_qty": 5},
        ]
        # Test with strict threshold 0.35
        res = self.agent.audit(allocations=dispatches, zone_demands=zones, gini_threshold=0.35)

        self.assertGreater(res["gini_coefficient"], 0.35)
        self.assertEqual(res["fairness_verdict"], "FAIRNESS_REJECTED")
        self.assertEqual(res["audit_verdict"], "REJECTED")
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertTrue(any("Gini index violation" in v for v in res["violations"]))

    def test_4_complete_resource_fulfilment(self):
        """4. Verify 100% fulfillment across all resource categories yields RESOURCE_ADEQUATE and FAIRNESS_APPROVED."""
        zones = [
            {
                "zone_id": "Z1",
                "zone_name": "Nagaon",
                "population": 1000,
                "zps": 70.0,
                "demands": {
                    "water_liters": 15000,
                    "food_packs": 200,
                    "medical_kits": 4,
                    "tents": 50,
                },
            }
        ]
        dispatches = [
            {"zone_id": "Z1", "resource_type": "CLEAN_WATER", "allocated_qty": 15000},
            {"zone_id": "Z1", "resource_type": "FOOD_RATIONS", "allocated_qty": 200},
            {"zone_id": "Z1", "resource_type": "MEDICAL_KITS", "allocated_qty": 4},
            {"zone_id": "Z1", "resource_type": "SHELTER_TENTS", "allocated_qty": 50},
        ]
        inv_snapshot = {
            "total_available": {
                "CLEAN_WATER": 20000,
                "FOOD_RATIONS": 500,
                "MEDICAL_KITS": 10,
                "SHELTER_TENTS": 100,
            }
        }
        res = self.agent.audit(allocations=dispatches, zone_demands=zones, inventory_snapshot=inv_snapshot)

        self.assertEqual(res["adequacy_status"], "RESOURCE_ADEQUATE")
        self.assertEqual(res["fairness_verdict"], "FAIRNESS_APPROVED")
        self.assertEqual(res["audit_verdict"], "FAIRNESS_APPROVED")
        self.assertEqual(res["overall_status"], "OVERALL_APPROVED")
        self.assertEqual(len(res["shortage_resources"]), 0)

        # Check calculated fields for each category
        for rtype in ["CLEAN_WATER", "FOOD_RATIONS", "MEDICAL_KITS", "SHELTER_TENTS"]:
            r_info = res["resource_adequacy"][rtype]
            self.assertEqual(r_info["fulfillment_pct"], 100.0)
            self.assertEqual(r_info["shortage_pct"], 0.0)
            self.assertEqual(r_info["unfulfilled_qty"], 0)
            self.assertEqual(r_info["status"], "ADEQUATE")

    def test_5_partial_resource_fulfilment(self):
        """5. Verify partial fulfillment accurately calculates percentages and emits APPROVED_WITH_SHORTAGES."""
        zones = [
            {
                "zone_id": "Z1",
                "zone_name": "Majuli",
                "population": 2000,
                "zps": 85.0,
                "demands": {
                    "water_liters": 30000,
                    "food_packs": 400,
                    "tents": 100,
                    "medical_kits": 8,
                },
            }
        ]
        # Half of water, 25% of tents, full food and medical
        dispatches = [
            {"zone_id": "Z1", "resource_type": "CLEAN_WATER", "allocated_qty": 15000},
            {"zone_id": "Z1", "resource_type": "FOOD_RATIONS", "allocated_qty": 400},
            {"zone_id": "Z1", "resource_type": "SHELTER_TENTS", "allocated_qty": 25},
            {"zone_id": "Z1", "resource_type": "MEDICAL_KITS", "allocated_qty": 8},
        ]
        res = self.agent.audit(allocations=dispatches, zone_demands=zones)

        self.assertEqual(res["adequacy_status"], "RESOURCE_SHORTAGE")
        self.assertEqual(res["audit_verdict"], "APPROVED_WITH_SHORTAGES")
        self.assertIn("CLEAN_WATER", res["shortage_resources"])
        self.assertIn("SHELTER_TENTS", res["shortage_resources"])

        water_info = res["resource_adequacy"]["CLEAN_WATER"]
        self.assertEqual(water_info["demanded"], 30000)
        self.assertEqual(water_info["allocated"], 15000)
        self.assertEqual(water_info["fulfilled_qty"], 15000)
        self.assertEqual(water_info["unfulfilled_qty"], 15000)
        self.assertEqual(water_info["fulfillment_pct"], 50.0)
        self.assertEqual(water_info["shortage_pct"], 50.0)

        tent_info = res["resource_adequacy"]["SHELTER_TENTS"]
        self.assertEqual(tent_info["fulfillment_pct"], 25.0)
        self.assertEqual(tent_info["shortage_pct"], 75.0)
        self.assertEqual(tent_info["status"], "CRITICAL_SHORTAGE")

    def test_6_complete_resource_shortage(self):
        """6. Verify 0 allocation across requested resources triggers RESOURCE_SHORTAGE verdict."""
        zones = [
            {
                "zone_id": "Z1",
                "zone_name": "Morigaon",
                "population": 1000,
                "zps": 65.0,
                "demands": {"water_liters": 15000, "food_packs": 200},
            }
        ]
        # 0 allocated across all items
        dispatches = [
            {"zone_id": "Z1", "resource_type": "CLEAN_WATER", "allocated_qty": 0},
            {"zone_id": "Z1", "resource_type": "FOOD_RATIONS", "allocated_qty": 0},
        ]
        res = self.agent.audit(allocations=dispatches, zone_demands=zones)

        self.assertEqual(res["adequacy_status"], "RESOURCE_SHORTAGE")
        # In a complete shortage state where 0 is allocated for demanded goods:
        self.assertIn(res["audit_verdict"], ["RESOURCE_SHORTAGE", "REJECTED"])
        for rtype in ["CLEAN_WATER", "FOOD_RATIONS"]:
            r_info = res["resource_adequacy"][rtype]
            self.assertEqual(r_info["fulfillment_pct"], 0.0)
            self.assertEqual(r_info["shortage_pct"], 100.0)

    def test_7_vulnerable_population_prioritisation(self):
        """7. Verify vulnerability prioritisation audit flags inversions where high priority zones are deprived."""
        zones = [
            {
                "zone_id": "Z_HIGH",
                "zone_name": "Critical Vulnerability Zone",
                "zps": 90.0,
                "population": 10000,
                "parameters": {
                    "damage_level": 4.8,
                    "vulnerability_index": 0.95,
                    "medical_urgency": 0.90,
                    "access_status": "ACCESSIBLE",
                },
                "demands": {"food_packs": 1000},
            },
            {
                "zone_id": "Z_LOW",
                "zone_name": "Mild Impact Zone",
                "zps": 40.0,
                "population": 1000,
                "parameters": {
                    "damage_level": 1.5,
                    "vulnerability_index": 0.20,
                    "medical_urgency": 0.10,
                    "access_status": "ACCESSIBLE",
                },
                "demands": {"food_packs": 100},
            },
        ]
        # Unfair dispatch: Low priority gets 100%, high priority gets 10%
        dispatches = [
            {"zone_id": "Z_HIGH", "resource_type": "FOOD_RATIONS", "allocated_qty": 100},  # 10%
            {"zone_id": "Z_LOW", "resource_type": "FOOD_RATIONS", "allocated_qty": 100},   # 100%
        ]
        res = self.agent.audit(allocations=dispatches, zone_demands=zones)

        self.assertFalse(res["priority_monotonicity_passed"])
        self.assertTrue(any("Vulnerability prioritization violation" in v for v in res["violations"]))
        # Verify priority explanation is generated for both zones
        for z in res["zone_summaries"]:
            self.assertIn("Priority ZPS", z["priority_explanation"])

    def test_8_dynamic_replanning_audit(self):
        """8. Verify dynamic replanning audit correctly re-evaluates surged demands after an embankment breach."""
        # Initial Plan
        zones_init = [
            {"zone_id": "Z1", "zone_name": "Majuli", "zps": 70.0, "population": 5000, "demands": {"food_packs": 500, "water_liters": 10000}}
        ]
        dispatches_init = [
            {"zone_id": "Z1", "resource_type": "FOOD_RATIONS", "allocated_qty": 500},
            {"zone_id": "Z1", "resource_type": "CLEAN_WATER", "allocated_qty": 10000},
        ]
        res_init = self.agent.audit(allocations=dispatches_init, zone_demands=zones_init)
        self.assertEqual(res_init["audit_verdict"], "FAIRNESS_APPROVED")
        self.assertEqual(res_init["adequacy_status"], "RESOURCE_ADEQUATE")

        # Secondary Embankment Breach Surge: Population displacement doubles, medical emergency spikes
        zones_surged = [
            {
                "zone_id": "Z1",
                "zone_name": "Majuli",
                "zps": 95.0,
                "population": 12000,
                "demands": {"food_packs": 1500, "water_liters": 30000, "medical_kits": 50},
            }
        ]
        # Same dispatches without adaptation -> severe shortage
        res_surged = self.agent.audit(allocations=dispatches_init, zone_demands=zones_surged)
        self.assertEqual(res_surged["adequacy_status"], "RESOURCE_SHORTAGE")
        self.assertEqual(res_surged["audit_verdict"], "APPROVED_WITH_SHORTAGES")
        self.assertIn("MEDICAL_KITS", res_surged["shortage_resources"])

        # Replanned dispatches with emergency water-filling
        dispatches_replanned = [
            {"zone_id": "Z1", "resource_type": "FOOD_RATIONS", "allocated_qty": 1500},
            {"zone_id": "Z1", "resource_type": "CLEAN_WATER", "allocated_qty": 30000},
            {"zone_id": "Z1", "resource_type": "MEDICAL_KITS", "allocated_qty": 50},
        ]
        res_replanned = self.agent.audit(allocations=dispatches_replanned, zone_demands=zones_surged)
        self.assertEqual(res_replanned["audit_verdict"], "FAIRNESS_APPROVED")
        self.assertEqual(res_replanned["adequacy_status"], "RESOURCE_ADEQUATE")

    def test_9_empty_or_invalid_allocation_inputs(self):
        """9. Verify empty, None, or malformed inputs are gracefully rejected without crashing."""
        # Case A: None inputs
        res_none = self.agent.audit(allocations=None, zone_demands=None)
        self.assertFalse(res_none["success"])
        self.assertEqual(res_none["audit_verdict"], "REJECTED")
        self.assertEqual(res_none["verdict"], "REJECTED")
        self.assertGreater(len(res_none["violations"]), 0)

        # Case B: Empty list of zones
        res_empty = self.agent.audit(allocations=[], zone_demands=[])
        self.assertEqual(res_empty["audit_verdict"], "REJECTED")

        # Case C: Agent execute with missing blackboard data
        empty_agent = FairnessAuditorAgent(blackboard=BlackboardManager(), db=self.db)
        res_exec = empty_agent.execute()
        self.assertEqual(res_exec["status"], "SUCCESS")
        self.assertEqual(res_exec["audit_verdict"]["audit_verdict"], "REJECTED")

    def test_10_overall_verdict_correctness(self):
        """10. Verify that each of the 4 verdicts is generated accurately according to policy conditions."""
        # 1. FAIRNESS_APPROVED
        v1 = self.agent.evaluate_verdict(fairness_approved=True, has_shortages=False, is_complete_shortage=False)
        self.assertEqual(v1, "FAIRNESS_APPROVED")

        # 2. APPROVED_WITH_SHORTAGES
        v2 = self.agent.evaluate_verdict(fairness_approved=True, has_shortages=True, is_complete_shortage=False)
        self.assertEqual(v2, "APPROVED_WITH_SHORTAGES")

        # 3. RESOURCE_SHORTAGE
        v3 = self.agent.evaluate_verdict(fairness_approved=True, has_shortages=True, is_complete_shortage=True)
        self.assertEqual(v3, "RESOURCE_SHORTAGE")

        # 4. REJECTED
        v4 = self.agent.evaluate_verdict(fairness_approved=False, has_shortages=False, is_complete_shortage=False)
        self.assertEqual(v4, "REJECTED")

        v5 = self.agent.evaluate_verdict(fairness_approved=False, has_shortages=True, is_complete_shortage=True)
        self.assertEqual(v5, "REJECTED")


if __name__ == "__main__":
    unittest.main()

"""
ReliefOps AI — Integrated Dashboard Stabilization & Regression Test Suite
Covers the 8 critical verification scenarios:
1. Shelter demand aggregation across multiple zones (28,960 tents for SCEN-01).
2. Shelter stock shortage and dispatch (4,500 available/dispatched, 24,460 shortage).
3. Severe clean-water shortage reporting (350,000 L available vs 11,160,000 L demanded).
4. Fairness approval independent of resource adequacy (FAIRNESS_APPROVED vs RESOURCE_SHORTAGE).
5. Overall status when shortages exist (APPROVED_WITH_SHORTAGES vs OVERALL_APPROVED).
6. GIS route coordinate generation (source_lat/lon -> target_lat/lon on dispatches).
7. Severity mapping consistency (SEVERE preserved with SOP-FL-001 Section 2 Level 3 equivalent).
8. Scenario consistency between demo_pipeline.py, app.py, and SQLite database records (SCEN-01 = 248,000 pop).
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.blackboard import BlackboardManager
from backend.database.db_manager import DatabaseManager
from backend.database.seeder import seed_database, build_scenario_context
from backend.agents.relief_coordinator import ReliefCoordinator
from backend.plugins.fairness_plugin import FairnessPlugin


class TestDashboardStabilization(unittest.TestCase):
    """Comprehensive verification of the 8 stabilization & audit fixes."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = os.path.join(cls.temp_dir.name, "test_stabilization.db")
        cls.db = DatabaseManager(cls.db_path)
        seed_database(cls.db)
        cls.bb = BlackboardManager(db=cls.db)
        cls.coordinator = ReliefCoordinator(blackboard=cls.bb, db=cls.db)
        cls.scenario_ctx = build_scenario_context("SCEN-01", planning_days=3, db=cls.db)
        cls.final_plan = cls.coordinator.run_full_coordination_cycle(
            disaster_context=cls.scenario_ctx
        )
        cls.snapshot = cls.bb.get_snapshot()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.temp_dir.cleanup()

    def test_1_shelter_demand_aggregation_across_multiple_zones(self):
        """Verify zone-level shelter demands (7200 + 3360 + 13200 + 5200 = 28960) aggregate properly in InventoryAgent."""
        zone_needs_data = self.snapshot["zone_needs"]
        zone_list = zone_needs_data if isinstance(zone_needs_data, list) else zone_needs_data.get("zones", [])
        zones = {z["zone_id"]: z for z in zone_list}

        self.assertEqual(zones["ZONE-MAJULI-ISLAND"]["demands"]["tents"], 7200)
        self.assertEqual(zones["ZONE-KAZIRANGA-RURAL"]["demands"]["tents"], 3360)
        self.assertEqual(zones["ZONE-DIBRUGARH-URBAN"]["demands"]["tents"], 13200)
        self.assertEqual(zones["ZONE-NAGAON-CENTRAL"]["demands"]["tents"], 5200)

        inv_snapshot = self.snapshot["inventory_snapshot"]
        shelter_inv = inv_snapshot["feasibility"]["SHELTER_TENTS"]
        self.assertEqual(shelter_inv["demanded"], 28960)
        self.assertEqual(inv_snapshot["total_demanded"]["SHELTER_TENTS"], 28960)

    def test_2_shelter_stock_shortage_and_dispatch(self):
        """Verify 4,500 available tents are fully dispatched and 24,460 tent shortage is accurately reported."""
        inv_snapshot = self.snapshot["inventory_snapshot"]
        shelter_inv = inv_snapshot["feasibility"]["SHELTER_TENTS"]
        self.assertEqual(shelter_inv["available"], 4500)
        self.assertEqual(shelter_inv["demanded"], 28960)
        self.assertEqual(shelter_inv["shortage_qty"], 24460)
        self.assertIn("SHORTAGE", shelter_inv["status"])

        # Verify actual dispatches include SHELTER_TENTS totaling 4,500
        dispatches = self.final_plan["dispatches"]
        tent_dispatches = [d for d in dispatches if d["resource_type"] == "SHELTER_TENTS"]
        self.assertGreaterEqual(len(tent_dispatches), 4)
        total_tents_dispatched = sum(d["allocated_qty"] for d in tent_dispatches)
        self.assertEqual(total_tents_dispatched, 4500)

        # Verify resource summary reports unfulfilled tent demand
        res_summary = self.final_plan["resource_summary"]["SHELTER_TENTS"]
        self.assertEqual(res_summary["allocated"], 4500)
        self.assertEqual(res_summary["unfulfilled_qty"], 24460)
        self.assertAlmostEqual(res_summary["fulfillment_pct"], 15.5, places=1)

    def test_3_severe_clean_water_shortage_reporting(self):
        """Verify 350,000 L available water vs 11,160,000 L demanded reports 3.1% coverage and 10,810,000 L shortage."""
        inv_snapshot = self.snapshot["inventory_snapshot"]
        water_inv = inv_snapshot["feasibility"]["CLEAN_WATER"]
        self.assertEqual(water_inv["available"], 350000)
        self.assertEqual(water_inv["demanded"], 11160000)
        self.assertEqual(water_inv["shortage_qty"], 10810000)
        self.assertEqual(water_inv["status"], "CRITICAL_SHORTAGE")

        audit_verdict = self.snapshot["audit_verdict"]
        water_adequacy = audit_verdict["resource_adequacy"]["CLEAN_WATER"]
        self.assertEqual(water_adequacy["available"], 350000)
        self.assertEqual(water_adequacy["demanded"], 11160000)
        self.assertEqual(water_adequacy["allocated"], 350000)
        self.assertEqual(water_adequacy["unfulfilled_qty"], 10810000)
        self.assertAlmostEqual(water_adequacy["fulfillment_pct"], 3.1, places=1)
        self.assertIn("CLEAN_WATER", audit_verdict["shortage_resources"])

    def test_4_fairness_approval_independent_of_resource_adequacy(self):
        """Verify distributive fairness (FAIRNESS_APPROVED, Gini <= 0.35) is evaluated separately from resource adequacy."""
        audit_verdict = self.snapshot["audit_verdict"]
        self.assertEqual(audit_verdict["fairness_verdict"], "FAIRNESS_APPROVED")
        self.assertLessEqual(audit_verdict["gini_coefficient"], 0.35)
        self.assertTrue(audit_verdict["zero_allocation_check_passed"])
        self.assertTrue(audit_verdict["priority_monotonicity_passed"])

        # Resource adequacy must simultaneously report shortage
        self.assertEqual(audit_verdict["adequacy_status"], "RESOURCE_SHORTAGE")
        self.assertIn("CLEAN_WATER", audit_verdict["shortage_resources"])
        self.assertIn("SHELTER_TENTS", audit_verdict["shortage_resources"])
        self.assertGreater(len(audit_verdict["shortage_warnings"]), 0)

    def test_5_overall_status_when_shortages_exist_and_when_adequate(self):
        """Verify overall_status is APPROVED_WITH_SHORTAGES under scarcity and OVERALL_APPROVED when stock is sufficient."""
        # Case A: Baseline SCEN-01 has water and shelter shortages
        self.assertEqual(self.final_plan["overall_status"], "APPROVED_WITH_SHORTAGES")
        self.assertEqual(self.final_plan["fairness_status"], "FAIRNESS_APPROVED")
        self.assertEqual(self.final_plan["adequacy_status"], "RESOURCE_SHORTAGE")

        # Case B: Synthetic scenario where all demands are fully met
        plugin = FairnessPlugin()
        zones_json = json.dumps([
            {"zone_id": "Z1", "population": 1000, "zps": 80.0, "demands": {"water_liters": 15000, "food_packs": 200, "medical_kits": 4, "tents": 200}},
            {"zone_id": "Z2", "population": 1000, "zps": 75.0, "demands": {"water_liters": 15000, "food_packs": 200, "medical_kits": 4, "tents": 200}},
        ])
        draft_json = json.dumps({
            "dispatches": [
                {"zone_id": "Z1", "resource_type": "CLEAN_WATER", "allocated_qty": 15000, "requested_qty": 15000},
                {"zone_id": "Z1", "resource_type": "FOOD_RATIONS", "allocated_qty": 200, "requested_qty": 200},
                {"zone_id": "Z1", "resource_type": "MEDICAL_KITS", "allocated_qty": 4, "requested_qty": 4},
                {"zone_id": "Z1", "resource_type": "SHELTER_TENTS", "allocated_qty": 200, "requested_qty": 200},
                {"zone_id": "Z2", "resource_type": "CLEAN_WATER", "allocated_qty": 15000, "requested_qty": 15000},
                {"zone_id": "Z2", "resource_type": "FOOD_RATIONS", "allocated_qty": 200, "requested_qty": 200},
                {"zone_id": "Z2", "resource_type": "MEDICAL_KITS", "allocated_qty": 4, "requested_qty": 4},
                {"zone_id": "Z2", "resource_type": "SHELTER_TENTS", "allocated_qty": 200, "requested_qty": 200},
            ],
            "resource_summary": {
                "CLEAN_WATER": {"available": 50000, "demanded": 30000, "allocated": 30000},
                "FOOD_RATIONS": {"available": 1000, "demanded": 400, "allocated": 400},
                "MEDICAL_KITS": {"available": 100, "demanded": 8, "allocated": 8},
                "SHELTER_TENTS": {"available": 1000, "demanded": 400, "allocated": 400},
            }
        })
        res = json.loads(plugin.audit_allocation_equity(allocations_json=draft_json, zone_demands_json=zones_json))
        self.assertEqual(res["fairness_verdict"], "FAIRNESS_APPROVED")
        self.assertEqual(res["adequacy_status"], "RESOURCE_ADEQUATE")
        self.assertEqual(res["overall_status"], "OVERALL_APPROVED")
        self.assertEqual(len(res["shortage_resources"]), 0)

    def test_6_gis_route_coordinate_generation(self):
        """Verify dispatches contain authentic warehouse source coordinates and zone target coordinates for GIS routes."""
        dispatches = self.final_plan["dispatches"]
        self.assertGreater(len(dispatches), 0)

        for d in dispatches:
            self.assertIsNotNone(d.get("source_lat"), f"Missing source_lat in dispatch {d}")
            self.assertIsNotNone(d.get("source_lon"), f"Missing source_lon in dispatch {d}")
            self.assertIsNotNone(d.get("target_lat"), f"Missing target_lat in dispatch {d}")
            self.assertIsNotNone(d.get("target_lon"), f"Missing target_lon in dispatch {d}")
            self.assertGreater(float(d["source_lat"]), 20.0)
            self.assertGreater(float(d["source_lon"]), 85.0)
            self.assertGreater(float(d["target_lat"]), 20.0)
            self.assertGreater(float(d["target_lon"]), 85.0)
            self.assertGreater(float(d["distance_km"]), 0.0)
            self.assertGreater(float(d["est_transit_hours"]), 0.0)
            self.assertTrue(bool(d.get("warehouse_name")))
            self.assertTrue(bool(d.get("zone_name")))

    def test_7_severity_mapping_consistency(self):
        """Verify SEVERE severity_level is preserved in sop_context and mapped to SOP-FL-001 Section 2 Level 3 equivalent."""
        sop_ctx = self.snapshot["sop_context"]
        self.assertEqual(sop_ctx["severity"], "SEVERE")
        self.assertEqual(sop_ctx["severity_level"], "SEVERE")
        self.assertEqual(sop_ctx["sop_severity_equivalent"], "Level 3 (Severe Inundation)")
        self.assertIn("SEVERE", sop_ctx["query"])

    def test_8_scenario_consistency_across_execution_paths(self):
        """Verify build_scenario_context('SCEN-01') matches SQLite simulation_scenarios (4 zones, 248,000 affected pop)."""
        scen = build_scenario_context("SCEN-01", planning_days=3, db=self.db)
        self.assertEqual(scen["scenario_id"], "SCEN-01")
        self.assertEqual(scen["severity"], "SEVERE")
        self.assertEqual(scen["severity_level"], "SEVERE")
        self.assertEqual(len(scen["zones"]), 4)

        zone_ids = [z["zone_id"] for z in scen["zones"]]
        self.assertEqual(
            zone_ids,
            [
                "ZONE-MAJULI-ISLAND",
                "ZONE-KAZIRANGA-RURAL",
                "ZONE-DIBRUGARH-URBAN",
                "ZONE-NAGAON-CENTRAL",
            ],
        )
        total_pop = sum(z["population"] for z in scen["zones"])
        self.assertEqual(total_pop, 248000)

    def test_9_evaluate_greedy_baseline_execution(self):
        """Verify that evaluate_greedy_baseline exists on ReliefCoordinator and executes cleanly."""
        from backend.agents.relief_coordinator import ReliefCoordinator as AgentCoordinator
        from backend.orchestrator.relief_coordinator import ReliefCoordinator as OrchestratorCoordinator
        self.assertIs(AgentCoordinator, OrchestratorCoordinator)

        greedy_res = self.coordinator.evaluate_greedy_baseline(disaster_context=self.scenario_ctx)
        self.assertIsNotNone(greedy_res)
        self.assertEqual(greedy_res.get("policy"), "greedy")
        self.assertIn("gini_coefficient", greedy_res)
        self.assertIn("fairness_verdict", greedy_res)
        self.assertEqual(greedy_res["fairness_verdict"], "FAIRNESS_REJECTED")
        self.assertGreater(greedy_res["gini_coefficient"], 0.35)
        self.assertGreater(len(greedy_res.get("dispatches", [])), 0)


if __name__ == "__main__":
    unittest.main()

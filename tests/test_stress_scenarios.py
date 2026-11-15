"""
ReliefOps AI — Phase 1: Multi-Scenario Stress Testing Suite
Executes 12 deterministic synthetic test scenarios spanning all 4 canonical disaster hazards
(FLOOD, EARTHQUAKE, CYCLONE, LANDSLIDE) under moderate, severe, catastrophic, and resource-deficit conditions.

Academic Disclaimer:
Synthetic test suite developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import json
import unittest
from typing import Any, Dict

from tests.stress_fixtures import STRESS_SCENARIOS, IsolatedStressEnvironment


class TestMultiScenarioStress(unittest.TestCase):
    """
    Stress test suite executing the 12 deterministic disaster scenarios end-to-end.
    Validates input schema consistency, authoritative SOP RAG retrieval, ZPS calculations,
    water-filling allocations, and fairness auditing under stress.
    """

    def setUp(self):
        self.env = IsolatedStressEnvironment()

    def tearDown(self):
        self.env.cleanup()

    def test_00_scenario_catalog_integrity(self):
        """Validates that all 12 stress scenarios have complete metadata, valid coordinates, and schema compliance."""
        self.assertGreaterEqual(len(STRESS_SCENARIOS), 12, "Must contain at least 12 stress scenarios.")

        for key, sc in STRESS_SCENARIOS.items():
            self.assertIn("scenario_id", sc, f"{key} missing scenario_id")
            self.assertIn("disaster_type", sc, f"{key} missing disaster_type")
            self.assertIn(sc["disaster_type"], ["FLOOD", "EARTHQUAKE", "CYCLONE", "LANDSLIDE"])
            self.assertIn(sc["severity_level"], ["MODERATE", "SEVERE", "CATASTROPHIC"])
            self.assertIn("expected_sop", sc, f"{key} missing expected_sop")
            self.assertIn("zones", sc, f"{key} missing zones")
            self.assertGreaterEqual(len(sc["zones"]), 3, f"{key} must have at least 3 zones")

            total_pop = 0
            for z in sc["zones"]:
                self.assertTrue(z["zone_id"].startswith("ZONE-"), f"Invalid zone_id {z['zone_id']}")
                self.assertGreater(z["population"], 0, f"Zone population must be > 0 in {key}")
                self.assertTrue(1 <= z["damage_level"] <= 5, f"Damage level out of bounds in {key}")
                self.assertTrue(0.0 <= z["vulnerability_index"] <= 1.0, f"Vulnerability out of bounds in {key}")
                self.assertTrue(0.0 <= z["medical_urgency"] <= 1.0, f"Medical urgency out of bounds in {key}")
                self.assertIn(z["access_status"], ["OPEN", "DEGRADED", "BLOCKED", "AIR_ONLY"])
                self.assertTrue(20.0 <= z["latitude"] <= 30.0, f"Latitude out of bounds in {key}")
                self.assertTrue(88.0 <= z["longitude"] <= 98.0, f"Longitude out of bounds in {key}")
                total_pop += z["population"]

            self.assertGreater(total_pop, 0, f"Total population must be positive in {key}")

    def _execute_and_verify_scenario(self, scenario_key: str) -> Dict[str, Any]:
        """Helper to execute a scenario through ReliefCoordinator and assert core invariants."""
        sc = STRESS_SCENARIOS[scenario_key]

        # Apply inventory overrides if specified
        if "inventory_override" in sc:
            self.env.set_inventory_multipliers(sc["inventory_override"])

        # Execute full coordination cycle
        plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc)

        # 1. Verification of plan structure
        self.assertIsNotNone(plan, f"{scenario_key}: plan must not be None")
        self.assertIn(plan.get("overall_status"), ["OVERALL_APPROVED", "APPROVED_WITH_SHORTAGES", "REJECTED"])
        self.assertEqual(plan.get("event_id"), sc.get("event_id", sc.get("scenario_id")))

        # 2. SOP Retrieval Verification
        sop_context = self.env.blackboard.read("sop_context") or {}
        sop_ids = sop_context.get("sop_ids", [])
        self.assertIn(sc["expected_sop"], sop_ids, f"{scenario_key}: Expected {sc['expected_sop']} in {sop_ids}")

        # 3. Severity mapping check
        if "expected_severity_mapping" in sc:
            self.assertEqual(
                sop_context.get("sop_severity_equivalent"),
                sc["expected_severity_mapping"],
                f"{scenario_key}: Severity mapping mismatch"
            )

        # 4. Zone needs and ZPS verification
        zone_needs = self.env.blackboard.read("zone_needs") or []
        self.assertEqual(len(zone_needs), len(sc["zones"]), f"{scenario_key}: Zone count mismatch in zone_needs")
        for zn in zone_needs:
            zps = zn.get("zps", zn.get("zps_score", 0.0))
            self.assertTrue(0.0 <= zps <= 100.0, f"{scenario_key}: ZPS score {zps} out of bounds")
            demands = zn.get("demands", {})
            self.assertIn("water_liters", demands)
            self.assertIn("food_packs", demands)
            self.assertIn("medical_kits", demands)
            self.assertIn("tents", demands)

        # 5. Allocation & Dispatch Verification
        dispatches = plan.get("dispatches", [])
        self.assertGreater(len(dispatches), 0, f"{scenario_key}: Dispatches must not be empty")

        for d in dispatches:
            self.assertGreaterEqual(d.get("allocated_qty", 0), 0, f"{scenario_key}: Negative allocation detected")
            self.assertGreaterEqual(d.get("unfulfilled_qty", 0), 0, f"{scenario_key}: Negative unfulfilled detected")

        # 6. Fairness Audit Verification
        audit = plan.get("audit_verdict") or {}
        self.assertIn(audit.get("verdict"), ["APPROVED", "REJECTED"])
        self.assertTrue(0.0 <= audit.get("gini_coefficient", 0.0) <= 1.0, f"{scenario_key}: Gini out of bounds")

        return plan

    def test_01_baseline_flood(self):
        """Scenario 1: Baseline Flood — Moderate severity, normal population."""
        plan = self._execute_and_verify_scenario("SCEN_01_BASELINE_FLOOD")
        self.assertEqual(plan["fairness_verdict"], "FAIRNESS_APPROVED")
        # In baseline flood, all resources should be adequate
        self.assertEqual(plan["adequacy_status"], "RESOURCE_ADEQUATE")
        self.assertEqual(plan["overall_status"], "OVERALL_APPROVED")

    def test_02_extreme_flood(self):
        """Scenario 2: Extreme Flood — Catastrophic severity, high displacement."""
        plan = self._execute_and_verify_scenario("SCEN_02_EXTREME_FLOOD")
        self.assertEqual(plan["fairness_verdict"], "FAIRNESS_APPROVED")
        # High population across 5 zones triggers resource shortages
        self.assertIn(plan["overall_status"], ["OVERALL_APPROVED", "APPROVED_WITH_SHORTAGES"])
        res_summary = plan.get("resource_summary", {})
        self.assertIn("CLEAN_WATER", res_summary)
        self.assertIn("SHELTER_TENTS", res_summary)

    def test_03_severe_earthquake(self):
        """Scenario 3: Severe Earthquake — Critical medical requirements."""
        plan = self._execute_and_verify_scenario("SCEN_03_SEVERE_EARTHQUAKE")
        self.assertEqual(plan["fairness_verdict"], "FAIRNESS_APPROVED")
        zone_needs = self.env.blackboard.read("zone_needs") or []
        # Urban zone with medical urgency 0.95 should have highest medical demand
        guwahati_zone = next(z for z in zone_needs if z["zone_id"] == "ZONE-S03-GUWAHATI")
        self.assertGreater(guwahati_zone["demands"]["medical_kits"], 100)

    def test_04_catastrophic_earthquake(self):
        """Scenario 4: Catastrophic Earthquake — Structural collapse and mass casualties."""
        plan = self._execute_and_verify_scenario("SCEN_04_CATASTROPHIC_EARTHQUAKE")
        self.assertEqual(plan["fairness_verdict"], "FAIRNESS_APPROVED")
        sop_ctx = self.env.blackboard.read("sop_context") or {}
        self.assertEqual(sop_ctx.get("sop_severity_equivalent"), "Level 5 (Catastrophic Flattening)")

    def test_05_severe_cyclone(self):
        """Scenario 5: Severe Cyclone — Coastal evacuation and shelter requirements."""
        plan = self._execute_and_verify_scenario("SCEN_05_SEVERE_CYCLONE")
        self.assertEqual(plan["fairness_verdict"], "FAIRNESS_APPROVED")
        sop_ctx = self.env.blackboard.read("sop_context") or {}
        self.assertEqual(sop_ctx.get("sop_severity_equivalent"), "Level 3 (Very Severe Cyclone)")

    def test_06_catastrophic_cyclone(self):
        """Scenario 6: Catastrophic Cyclone — Extreme wind damage and infrastructure disruption."""
        plan = self._execute_and_verify_scenario("SCEN_06_CATASTROPHIC_CYCLONE")
        self.assertEqual(plan["fairness_verdict"], "FAIRNESS_APPROVED")
        # Blocked road zones should have valid transit calculations and dispatches
        blocked_dispatches = [d for d in plan["dispatches"] if d.get("road_status") == "BLOCKED"]
        self.assertGreater(len(blocked_dispatches), 0)

    def test_07_severe_landslide(self):
        """Scenario 7: Severe Landslide — Isolated settlements and blocked roads."""
        plan = self._execute_and_verify_scenario("SCEN_07_SEVERE_LANDSLIDE")
        self.assertEqual(plan["fairness_verdict"], "FAIRNESS_APPROVED")
        sop_ctx = self.env.blackboard.read("sop_context") or {}
        self.assertEqual(sop_ctx.get("sop_severity_equivalent"), "Level 3 (Major Slope Failure)")

    def test_08_catastrophic_landslide(self):
        """Scenario 8: Catastrophic Landslide — Multiple inaccessible zones."""
        plan = self._execute_and_verify_scenario("SCEN_08_CATASTROPHIC_LANDSLIDE")
        self.assertEqual(plan["fairness_verdict"], "FAIRNESS_APPROVED")
        # All 4 mountain zones should receive floor allocation despite blocked status
        allocated_zones = {d["zone_id"] for d in plan["dispatches"] if d.get("allocated_qty", 0) > 0}
        self.assertEqual(len(allocated_zones), 4, "All 4 inaccessible zones must receive non-zero survival dispatches")

    def test_09_extreme_population_surge(self):
        """Scenario 9: Extreme Population Surge — Sudden 3x population increase."""
        plan = self._execute_and_verify_scenario("SCEN_09_POPULATION_SURGE")
        self.assertEqual(plan["fairness_verdict"], "FAIRNESS_APPROVED")
        zone_needs = self.env.blackboard.read("zone_needs") or []
        surge_zone = next(z for z in zone_needs if z["zone_id"] == "ZONE-S09-SURGE-CORE")
        stable_zone = next(z for z in zone_needs if z["zone_id"] == "ZONE-S09-STABLE-A")
        # Surge zone has 45k pop vs 20k pop -> demand should be significantly larger
        self.assertGreater(surge_zone["demands"]["water_liters"], stable_zone["demands"]["water_liters"])

    def test_10_critical_water_shortage(self):
        """Scenario 10: Critical Water Shortage — Inventory insufficient for demand."""
        plan = self._execute_and_verify_scenario("SCEN_10_WATER_SHORTAGE")
        self.assertEqual(plan["fairness_verdict"], "FAIRNESS_APPROVED")
        self.assertEqual(plan["adequacy_status"], "RESOURCE_SHORTAGE")
        self.assertEqual(plan["overall_status"], "APPROVED_WITH_SHORTAGES")
        water_summary = plan["resource_summary"].get("CLEAN_WATER", {})
        self.assertIn(water_summary.get("status"), ["SHORTAGE", "CRITICAL_SHORTAGE"])
        self.assertGreater(water_summary.get("unfulfilled_qty", 0), 0)

    def test_11_critical_medical_shortage(self):
        """Scenario 11: Critical Medical Shortage — High trauma demand with limited kits."""
        plan = self._execute_and_verify_scenario("SCEN_11_MEDICAL_SHORTAGE")
        self.assertEqual(plan["fairness_verdict"], "FAIRNESS_APPROVED")
        self.assertEqual(plan["adequacy_status"], "RESOURCE_SHORTAGE")
        med_summary = plan["resource_summary"].get("MEDICAL_KITS", {})
        self.assertIn(med_summary.get("status"), ["SHORTAGE", "CRITICAL_SHORTAGE"])

    def test_12_combined_resource_crisis(self):
        """Scenario 12: Combined Resource Crisis — Simultaneous food, water, medical and shelter shortages."""
        plan = self._execute_and_verify_scenario("SCEN_12_COMBINED_CRISIS")
        self.assertEqual(plan["fairness_verdict"], "FAIRNESS_APPROVED")
        self.assertEqual(plan["adequacy_status"], "RESOURCE_SHORTAGE")
        self.assertEqual(plan["overall_status"], "APPROVED_WITH_SHORTAGES")
        # All 4 resources must flag shortage
        for rtype in ["FOOD_RATIONS", "CLEAN_WATER", "MEDICAL_KITS", "SHELTER_TENTS"]:
            r_stat = plan["resource_summary"].get(rtype, {}).get("status")
            self.assertIn(r_stat, ["SHORTAGE", "CRITICAL_SHORTAGE"], f"{rtype} should be in shortage")


if __name__ == "__main__":
    unittest.main()

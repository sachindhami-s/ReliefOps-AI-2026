"""
ReliefOps AI — Cross-Hazard Consistency & Multi-Hazard Regression Test Suite
Validates that changing disaster hazards (FLOOD, EARTHQUAKE, CYCLONE, LANDSLIDE) dynamically
and correctly updates SOP RAG retrieval, severity classification mapping, ZPS priority weights,
resource demands calculations, and event metadata.

Academic Disclaimer:
Synthetic test suite developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import json
import os
import tempfile
import unittest

from backend.agents.needs_assessment_agent import NeedsAssessmentAgent
from backend.agents.relief_coordinator import ReliefCoordinator
from backend.blackboard.blackboard_manager import BlackboardManager
from backend.database.db_manager import DatabaseManager
from backend.database.seeder import build_scenario_context, seed_database
from backend.plugins.needs_plugin import NeedsAssessmentPlugin


class TestCrossHazardConsistency(unittest.TestCase):
    """Regression and validation tests for cross-hazard consistency across all 4 canonical disaster types."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_hazard.db")
        self.db = DatabaseManager(self.db_path)
        seed_database(self.db)
        self.bb = BlackboardManager(db=self.db)
        self.plugin = NeedsAssessmentPlugin()

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_1_sop_rag_retrieval_all_four_hazards(self):
        """1. Verify that ChromaDB vector RAG retrieves the authoritative SOP for each of the 4 hazards."""
        hazard_expectations = {
            "FLOOD": "SOP-FL-001",
            "EARTHQUAKE": "SOP-EQ-002",
            "CYCLONE": "SOP-CY-004",
            "LANDSLIDE": "SOP-LS-003",
        }
        for hazard, expected_sop in hazard_expectations.items():
            raw_res = self.plugin.retrieve_sop_guidelines(disaster_type=hazard, severity="SEVERE")
            data = json.loads(raw_res)
            self.assertEqual(data["status"], "SUCCESS")
            self.assertEqual(data["disaster_type"], hazard)
            self.assertIn(expected_sop, data["sop_ids"], f"Expected {expected_sop} in {hazard} retrieval")

    def test_2_severity_mapping_hazard_specific(self):
        """2. Verify that severity mapping accurately reflects each hazard's Section 2 classification."""
        # A. FLOOD
        flood_res = json.loads(self.plugin.retrieve_sop_guidelines(disaster_type="FLOOD", severity="SEVERE"))
        self.assertEqual(flood_res["sop_severity_equivalent"], "Level 3 (Severe Inundation)")

        # B. EARTHQUAKE (Must NOT say Inundation)
        eq_res = json.loads(self.plugin.retrieve_sop_guidelines(disaster_type="EARTHQUAKE", severity="SEVERE"))
        self.assertEqual(eq_res["sop_severity_equivalent"], "Level 3 (Heavy Damage)")
        self.assertNotIn("Inundation", eq_res["sop_severity_equivalent"])

        # C. CYCLONE
        cy_res = json.loads(self.plugin.retrieve_sop_guidelines(disaster_type="CYCLONE", severity="SEVERE"))
        self.assertEqual(cy_res["sop_severity_equivalent"], "Level 3 (Very Severe Cyclone)")

        # D. LANDSLIDE
        ls_res = json.loads(self.plugin.retrieve_sop_guidelines(disaster_type="LANDSLIDE", severity="SEVERE"))
        self.assertEqual(ls_res["sop_severity_equivalent"], "Level 3 (Major Slope Failure)")

        # E. Multi-tier check for Earthquake (Levels 1 to 5)
        eq_l1 = json.loads(self.plugin.retrieve_sop_guidelines(disaster_type="EARTHQUAKE", severity="MODERATE"))
        self.assertEqual(eq_l1["sop_severity_equivalent"], "Level 2 (Moderate Damage)")
        eq_l5 = json.loads(self.plugin.retrieve_sop_guidelines(disaster_type="EARTHQUAKE", severity="CATASTROPHIC"))
        self.assertEqual(eq_l5["sop_severity_equivalent"], "Level 5 (Catastrophic Flattening)")

    def test_3_earthquake_priority_weights_elevation(self):
        """3. Verify earthquake priority scoring elevates medical urgency (0.40) and structural damage (0.30)."""
        # Identical parameters for comparison
        dmg, vuln, med, pop, pop_max = 4.0, 0.50, 0.80, 50000, 100000

        flood_zps_raw = self.plugin.compute_zone_priority(
            damage_lvl=dmg,
            vulnerability_idx=vuln,
            medical_urgency=med,
            population=pop,
            pop_max=pop_max,
            disaster_type="FLOOD",
        )
        flood_zps = json.loads(flood_zps_raw)

        eq_zps_raw = self.plugin.compute_zone_priority(
            damage_lvl=dmg,
            vulnerability_idx=vuln,
            medical_urgency=med,
            population=pop,
            pop_max=pop_max,
            disaster_type="EARTHQUAKE",
        )
        eq_zps = json.loads(eq_zps_raw)

        # In Earthquake: medical weight must be 0.40 (vs 0.25 in Flood)
        self.assertEqual(eq_zps["weights_applied"]["medical_weight"], 0.40)
        self.assertEqual(flood_zps["weights_applied"]["medical_weight"], 0.25)

        # Medical component contribution in Earthquake must be higher
        self.assertGreater(eq_zps["components"]["medical_weight"], flood_zps["components"]["medical_weight"])

    def test_4_hazard_specific_resource_demands(self):
        """4. Verify resource demands follow hazard-specific norms (e.g. seismic trauma kits, water volume)."""
        pop = 10000
        dmg = 3.0
        vuln = 0.60
        med = 0.85
        days = 3

        # Flood Demands (Sphere standard 15L water, 1 kit / 250 people)
        flood_demands = json.loads(
            self.plugin.calculate_zone_demands(
                population=pop,
                vulnerability_idx=vuln,
                damage_lvl=dmg,
                medical_urgency=med,
                days=days,
                disaster_type="FLOOD",
            )
        )
        f_d = flood_demands["demands"]
        self.assertEqual(f_d["water_liters"], 10000 * 15.0 * 3)
        self.assertEqual(f_d["medical_kits"], 40)  # ceil(10000 / 250) = 40

        # Earthquake Demands (SOP-EQ-002: 10L water, aftershock panic >=70% displacement, 1 kit / 100 people)
        eq_demands = json.loads(
            self.plugin.calculate_zone_demands(
                population=pop,
                vulnerability_idx=vuln,
                damage_lvl=dmg,
                medical_urgency=med,
                days=days,
                disaster_type="EARTHQUAKE",
            )
        )
        eq_d = eq_demands["demands"]
        self.assertEqual(eq_d["water_liters"], 10000 * 10.0 * 3)  # 10L vs 15L
        self.assertEqual(eq_d["medical_kits"], 100)  # ceil(10000 / 100) = 100 trauma kits
        self.assertGreaterEqual(eq_demands["displacement_ratio"], 0.70)  # Aftershock panic floor
        self.assertGreater(eq_d["tents"], f_d["tents"])  # Higher shelter demand due to aftershock displacement

    def test_5_event_metadata_consistency_on_hazard_switch(self):
        """5. Verify scenario building and database seeder generate hazard-consistent event IDs and titles."""
        # SCEN-01: Flood
        scen_01 = build_scenario_context("SCEN-01", db=self.db)
        self.assertEqual(scen_01["disaster_type"], "FLOOD")
        self.assertEqual(scen_01["event_id"], "EVT-2026-FL01")
        self.assertIn("Flood", scen_01["name"])

        # SCEN-02: Earthquake
        scen_02 = build_scenario_context("SCEN-02", db=self.db)
        self.assertEqual(scen_02["disaster_type"], "EARTHQUAKE")
        self.assertEqual(scen_02["event_id"], "EVT-2026-EQ01")
        self.assertIn("Earthquake", scen_02["name"])
        self.assertNotIn("Flood", scen_02["name"])

    def test_6_end_to_end_earthquake_coordination_cycle(self):
        """6. Run end-to-end multi-agent coordination under an Earthquake scenario and verify pipeline consistency."""
        coordinator = ReliefCoordinator(blackboard=self.bb, db=self.db)
        scen_02 = build_scenario_context("SCEN-02", db=self.db)

        plan = coordinator.run_full_coordination_cycle(disaster_context=scen_02)
        self.assertIsNotNone(plan)

        # Verify Blackboard sop_context contains earthquake doctrine
        sop_ctx = self.bb.read("sop_context")
        self.assertIsNotNone(sop_ctx)
        self.assertEqual(sop_ctx["disaster_type"], "EARTHQUAKE")
        self.assertIn("SOP-EQ-002", sop_ctx["sop_ids"])
        self.assertEqual(sop_ctx["sop_severity_equivalent"], "Level 3 (Heavy Damage)")
        self.assertNotIn("Inundation", sop_ctx["sop_severity_equivalent"])

        # Verify zone_needs were evaluated with earthquake parameters
        zone_needs = self.bb.read("zone_needs")
        self.assertGreater(len(zone_needs), 0)
        for z in zone_needs:
            self.assertIn("zps_components", z)
            # In earthquake, medical component weight is based on 0.40 multiplier
            self.assertIn("medical_weight", z["zps_components"])


if __name__ == "__main__":
    unittest.main()

"""
ReliefOps AI — Phase 1 Unit Tests: NeedsAssessmentPlugin
Validates mathematical consistency, input clamping, threshold rules,
multi-cycle replenishment, and Semantic Kernel plugin registration.
"""

import json
import math
import os
import sys
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from semantic_kernel import Kernel
from backend.plugins.needs_plugin import NeedsAssessmentPlugin


class TestNeedsAssessmentPluginPhase1(unittest.TestCase):
    """Focused Phase 1 test suite for NeedsAssessmentPlugin."""

    @classmethod
    def setUpClass(cls):
        cls.plugin = NeedsAssessmentPlugin()
        cls.kernel = Kernel()
        cls.kernel.add_plugin(cls.plugin, plugin_name="NeedsAssessment")

    def test_zps_population_normalization_edge_cases(self):
        """Test ZPS population scale normalization and P_max immunity."""
        # Case 1: P_i == P_max (10,000) -> population component = 0.15 * 1.0 = 0.15
        res_equal = json.loads(
            self.plugin.compute_zone_priority(
                damage_lvl=5.0,
                vulnerability_idx=1.0,
                medical_urgency=1.0,
                population=10000,
                pop_max=10000,
            )
        )
        self.assertEqual(res_equal["status"], "SUCCESS")
        self.assertEqual(res_equal["pop_max_effective"], 10000)
        self.assertEqual(res_equal["normalized_scores"]["population_ratio"], 1.0)
        self.assertEqual(res_equal["zps"], 100.0)

        # Case 2: P_i == 1 -> log10(1) = 0.0 -> population component = 0.0
        res_one = json.loads(
            self.plugin.compute_zone_priority(
                damage_lvl=1.0,
                vulnerability_idx=0.0,
                medical_urgency=0.0,
                population=1,
                pop_max=10000,
            )
        )
        self.assertEqual(res_one["normalized_scores"]["population_ratio"], 0.0)
        # ZPS = 100 * (0.35 * 0.2 + 0 + 0 + 0) = 7.0
        self.assertEqual(res_one["zps"], 7.0)

        # Case 3: P_i == 0 -> gracefully handled without division error
        res_zero = json.loads(
            self.plugin.compute_zone_priority(
                damage_lvl=1.0,
                vulnerability_idx=0.0,
                medical_urgency=0.0,
                population=0,
                pop_max=10000,
            )
        )
        self.assertEqual(res_zero["normalized_scores"]["population_ratio"], 0.0)
        self.assertEqual(res_zero["zps"], 7.0)

        # Case 4: Inconsistent input where P_i > P_max (50,000 > 10,000)
        res_inconsistent = json.loads(
            self.plugin.compute_zone_priority(
                damage_lvl=5.0,
                vulnerability_idx=1.0,
                medical_urgency=1.0,
                population=50000,
                pop_max=10000,
            )
        )
        self.assertEqual(res_inconsistent["pop_max_effective"], 50000)
        self.assertEqual(res_inconsistent["normalized_scores"]["population_ratio"], 1.0)
        self.assertLessEqual(res_inconsistent["zps"], 100.0)

        # Case 5: P_max <= 1 edge case -> pop_max_effective must be at least 2
        res_small_max = json.loads(
            self.plugin.compute_zone_priority(
                damage_lvl=3.0,
                vulnerability_idx=0.5,
                medical_urgency=0.5,
                population=0,
                pop_max=0,
            )
        )
        self.assertEqual(res_small_max["pop_max_effective"], 2)

    def test_damage_level_input_validation(self):
        """Test damage level strict clamping to [1.0, 5.0]."""
        # Test lower clamp: damage_lvl <= 0 must clamp to 1.0
        demands_zero = json.loads(
            self.plugin.calculate_zone_demands(
                population=1000,
                vulnerability_idx=0.5,
                damage_lvl=0.0,
                medical_urgency=0.5,
                days=1,
            )
        )
        self.assertEqual(demands_zero["parameters"]["damage_level"], 1.0)
        self.assertEqual(demands_zero["displacement_ratio"], 0.20)

        demands_neg = json.loads(
            self.plugin.calculate_zone_demands(
                population=1000,
                vulnerability_idx=0.5,
                damage_lvl=-2.5,
                medical_urgency=0.5,
                days=1,
            )
        )
        self.assertEqual(demands_neg["parameters"]["damage_level"], 1.0)
        self.assertEqual(demands_neg["displacement_ratio"], 0.20)

        # Test upper clamp: damage_lvl >= 6 must clamp to 5.0
        demands_high = json.loads(
            self.plugin.calculate_zone_demands(
                population=1000,
                vulnerability_idx=0.5,
                damage_lvl=8.0,
                medical_urgency=0.5,
                days=1,
            )
        )
        self.assertEqual(demands_high["parameters"]["damage_level"], 5.0)
        self.assertEqual(demands_high["displacement_ratio"], 1.00)

        # In compute_zone_priority
        zps_zero = json.loads(
            self.plugin.compute_zone_priority(
                damage_lvl=0.0,
                vulnerability_idx=0.5,
                medical_urgency=0.5,
                population=1000,
                pop_max=1000,
            )
        )
        self.assertEqual(zps_zero["normalized_scores"]["damage_ratio"], 0.20)

    def test_food_replenishment_cycles(self):
        """Test food pack allocation across 1, 3, 4, and 7 day planning horizons."""
        # Pop: 1000, Dmg: 3.0 -> Disp: 600 -> Displaced families: ceil(600 / 5) = 120
        # 1 day -> cycles = ceil(1/3) = 1 -> packs = 120 * 1 = 120
        d1 = json.loads(self.plugin.calculate_zone_demands(1000, 0.5, 3.0, 0.5, days=1))
        self.assertEqual(d1["demands"]["food_replenishment_cycles"], 1)
        self.assertEqual(d1["demands"]["food_packs"], 120)

        # 3 days -> cycles = ceil(3/3) = 1 -> packs = 120 * 1 = 120
        d3 = json.loads(self.plugin.calculate_zone_demands(1000, 0.5, 3.0, 0.5, days=3))
        self.assertEqual(d3["demands"]["food_replenishment_cycles"], 1)
        self.assertEqual(d3["demands"]["food_packs"], 120)

        # 4 days -> cycles = ceil(4/3) = 2 -> packs = 120 * 2 = 240
        d4 = json.loads(self.plugin.calculate_zone_demands(1000, 0.5, 3.0, 0.5, days=4))
        self.assertEqual(d4["demands"]["food_replenishment_cycles"], 2)
        self.assertEqual(d4["demands"]["food_packs"], 240)

        # 7 days -> cycles = ceil(7/3) = 3 -> packs = 120 * 3 = 360
        d7 = json.loads(self.plugin.calculate_zone_demands(1000, 0.5, 3.0, 0.5, days=7))
        self.assertEqual(d7["demands"]["food_replenishment_cycles"], 3)
        self.assertEqual(d7["demands"]["food_packs"], 360)

    def test_medical_urgency_exact_thresholds(self):
        """Test medical kit threshold at 0.599 (0 kits), 0.600 (kits), and 1.000 (kits)."""
        pop = 1000  # ceil(1000 / 250) = 4 kits

        # 0.599 -> below 0.60 -> 0 kits
        res_below = json.loads(self.plugin.calculate_zone_demands(pop, 0.5, 3.0, 0.599, days=1))
        self.assertEqual(res_below["demands"]["medical_kits"], 0)

        # 0.600 -> exactly at threshold -> 4 kits
        res_exact = json.loads(self.plugin.calculate_zone_demands(pop, 0.5, 3.0, 0.600, days=1))
        self.assertEqual(res_exact["demands"]["medical_kits"], 4)

        # 1.000 -> maximum urgency -> 4 kits
        res_max = json.loads(self.plugin.calculate_zone_demands(pop, 0.5, 3.0, 1.000, days=1))
        self.assertEqual(res_max["demands"]["medical_kits"], 4)

    def test_shelter_and_water_calculations(self):
        """Test indivisible family tents and water volume calculations."""
        # Tents:
        # P = 21, D = 1.0 -> Disp = 4.2 -> ceil(4.2 / 5) = 1 tent
        t1 = json.loads(self.plugin.calculate_zone_demands(21, 0.5, 1.0, 0.5, days=1))
        self.assertEqual(t1["demands"]["tents"], 1)

        # P = 26, D = 1.0 -> Disp = 5.2 -> ceil(5.2 / 5) = 2 tents
        t2 = json.loads(self.plugin.calculate_zone_demands(26, 0.5, 1.0, 0.5, days=1))
        self.assertEqual(t2["demands"]["tents"], 2)

        # Water:
        # P = 500, days = 1 -> water = 500 * 15 * 1 = 7,500 L -> 750 jerrycans
        w1 = json.loads(self.plugin.calculate_zone_demands(500, 0.5, 2.0, 0.5, days=1))
        self.assertEqual(w1["demands"]["water_liters"], 7500.0)
        self.assertEqual(w1["demands"]["jerrycans_10l"], 750)

        # P = 500, days = 3 -> water = 500 * 15 * 3 = 22,500 L -> 2,250 jerrycans
        w3 = json.loads(self.plugin.calculate_zone_demands(500, 0.5, 2.0, 0.5, days=3))
        self.assertEqual(w3["demands"]["water_liters"], 22500.0)
        self.assertEqual(w3["demands"]["jerrycans_10l"], 2250)

    def test_semantic_kernel_plugin_registration(self):
        """Test that all three plugin functions are registered on the Kernel."""
        sk_plugin = self.kernel.get_plugin("NeedsAssessment")
        function_names = [f.name for f in sk_plugin]
        self.assertIn("retrieve_sop_guidelines", function_names)
        self.assertIn("calculate_zone_demands", function_names)
        self.assertIn("compute_zone_priority", function_names)

    def test_direct_sop_retrieval_multi_hazard(self):
        """Test dynamic SOP retrieval for FLOOD, EARTHQUAKE, and CYCLONE."""
        # FLOOD -> SOP-FL-001
        flood_res = json.loads(self.plugin.retrieve_sop_guidelines(disaster_type="FLOOD", severity="Level 3"))
        self.assertEqual(flood_res["status"], "SUCCESS")
        self.assertIn("SOP-FL-001", flood_res["sop_ids"])

        # EARTHQUAKE -> SOP-EQ-002
        eq_res = json.loads(self.plugin.retrieve_sop_guidelines(disaster_type="EARTHQUAKE", severity="Level 4"))
        self.assertEqual(eq_res["status"], "SUCCESS")
        self.assertIn("SOP-EQ-002", eq_res["sop_ids"])

        # CYCLONE -> SOP-CY-004
        cyc_res = json.loads(self.plugin.retrieve_sop_guidelines(disaster_type="CYCLONE", severity="Category 4"))
        self.assertEqual(cyc_res["status"], "SUCCESS")
        self.assertIn("SOP-CY-004", cyc_res["sop_ids"])


if __name__ == "__main__":
    unittest.main()


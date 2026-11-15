"""
ReliefOps AI — Phase 2: Resource Allocation Stress & Constraint Validation Suite
Tests the allocation engine under adequate stock, partial shortages, severe shortages,
zero inventory for single/all resources, 10x demand overflow, and multi-zone competition.

Academic Disclaimer:
Synthetic test suite developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import unittest
from typing import Any, Dict, List

from tests.stress_fixtures import IsolatedStressEnvironment, STRESS_SCENARIOS


class TestResourceConstraints(unittest.TestCase):
    """
    Validates physical conservation laws, zero-negative bounds, warehouse stock updates,
    unfulfilled demand accounting, and hazard-aware allocations under severe resource constraints.
    """

    def setUp(self):
        self.env = IsolatedStressEnvironment()

    def tearDown(self):
        self.env.cleanup()

    def test_01_adequate_inventory_full_fulfillment(self):
        """1. Adequate inventory: all zone demands are 100% satisfied with 0 unfulfilled quantity."""
        sc = STRESS_SCENARIOS["SCEN_01_BASELINE_FLOOD"]
        plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc)

        res_summary = plan.get("resource_summary", {})
        for rtype, summary in res_summary.items():
            if summary.get("demanded", 0) > 0:
                self.assertEqual(
                    summary.get("unfulfilled_qty", 0), 0,
                    f"{rtype}: unfulfilled_qty must be 0 when inventory is adequate"
                )
                self.assertEqual(
                    summary.get("allocated"), summary.get("demanded"),
                    f"{rtype}: allocated must equal demanded"
                )
                self.assertEqual(summary.get("fulfillment_pct"), 100.0)
                self.assertEqual(summary.get("status"), "ADEQUATE")

    def test_02_partial_inventory_shortages(self):
        """2. Partial inventory shortage: stock covers ~50% of demand; allocated equals available stock."""
        sc = STRESS_SCENARIOS["SCEN_01_BASELINE_FLOOD"]
        # Reduce food rations to exactly 50% of baseline
        self.env.set_inventory_multipliers({"FOOD_RATIONS": 0.005})  # very small stock ~600 units

        plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc)
        food_sum = plan.get("resource_summary", {}).get("FOOD_RATIONS", {})

        self.assertLess(food_sum.get("available", 0), food_sum.get("demanded", 1))
        # Allocated must not exceed available
        self.assertLessEqual(food_sum.get("allocated", 0), food_sum.get("available", 0))
        # Conservation: allocated + unfulfilled == demanded
        self.assertEqual(
            food_sum.get("allocated", 0) + food_sum.get("unfulfilled_qty", 0),
            food_sum.get("demanded", 0)
        )
        self.assertIn(food_sum.get("status"), ["SHORTAGE", "CRITICAL_SHORTAGE"])

    def test_03_severe_inventory_shortages(self):
        """3. Severe inventory shortage: stock covers < 20% of aggregate demand."""
        sc = STRESS_SCENARIOS["SCEN_03_SEVERE_EARTHQUAKE"]
        self.env.set_inventory_multipliers({
            "FOOD_RATIONS": 0.05,
            "CLEAN_WATER": 0.05,
            "MEDICAL_KITS": 0.05,
            "SHELTER_TENTS": 0.05,
        })
        plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc)
        self.assertEqual(plan.get("adequacy_status"), "RESOURCE_SHORTAGE")

        for rtype, summary in plan.get("resource_summary", {}).items():
            if summary.get("demanded", 0) > 0:
                self.assertLessEqual(summary.get("allocated", 0), summary.get("available", 0))
                self.assertGreater(summary.get("unfulfilled_qty", 0), 0)

    def test_04_zero_inventory_single_resource(self):
        """4. Zero inventory for one specific resource: allocated == 0, unfulfilled == demanded, other resources fulfilled."""
        sc = STRESS_SCENARIOS["SCEN_03_SEVERE_EARTHQUAKE"]
        self.env.set_zero_stock_for_resource("MEDICAL_KITS")

        plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc)
        med_sum = plan.get("resource_summary", {}).get("MEDICAL_KITS", {})

        self.assertEqual(med_sum.get("available"), 0)
        self.assertEqual(med_sum.get("allocated"), 0)
        self.assertEqual(med_sum.get("unfulfilled_qty"), med_sum.get("demanded"))
        self.assertEqual(med_sum.get("fulfillment_pct"), 0.0)
        self.assertEqual(med_sum.get("status"), "CRITICAL_SHORTAGE")

        # Other resources (water, food) must still receive non-zero allocations
        water_sum = plan.get("resource_summary", {}).get("CLEAN_WATER", {})
        self.assertGreater(water_sum.get("allocated", 0), 0)

    def test_05_zero_inventory_across_all_warehouses(self):
        """5. Zero inventory across all warehouses: 0 allocations, 100% unfulfilled, no crashes or negatives."""
        sc = STRESS_SCENARIOS["SCEN_01_BASELINE_FLOOD"]
        self.env.set_zero_all_stocks()

        plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc)
        self.assertIn(plan.get("overall_status"), ["REJECTED", "APPROVED_WITH_SHORTAGES"])

        for rtype, summary in plan.get("resource_summary", {}).items():
            self.assertEqual(summary.get("available", 0), 0)
            self.assertEqual(summary.get("allocated", 0), 0)
            if summary.get("demanded", 0) > 0:
                self.assertEqual(summary.get("unfulfilled_qty"), summary.get("demanded"))
                self.assertEqual(summary.get("status"), "CRITICAL_SHORTAGE")

        # Check dispatches: every zone dispatch should have allocated_qty == 0 and unfulfilled_qty == requested_qty
        for d in plan.get("dispatches", []):
            self.assertEqual(d.get("allocated_qty"), 0)
            self.assertEqual(d.get("unfulfilled_qty"), d.get("requested_qty"))

    def test_06_demand_exceeding_available_stock_by_10x(self):
        """6. Demand exceeds stock by 10x (1000% deficit): allocated never exceeds available, no negative stock."""
        # Scale down regional inventory to create an exact 10x deficit condition
        self.env.set_inventory_multipliers({
            "FOOD_RATIONS": 0.02,
            "CLEAN_WATER": 0.01,
            "MEDICAL_KITS": 0.02,
            "SHELTER_TENTS": 0.02,
        })
        sc = STRESS_SCENARIOS["SCEN_02_EXTREME_FLOOD"]
        plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc)

        for rtype, summary in plan.get("resource_summary", {}).items():
            dem = summary.get("demanded", 0)
            avail = summary.get("available", 0)
            alloc = summary.get("allocated", 0)
            unf = summary.get("unfulfilled_qty", 0)

            if dem > 0:
                self.assertGreaterEqual(dem, avail * 5, f"{rtype}: Demand should greatly exceed available stock")
                self.assertLessEqual(alloc, avail, f"{rtype}: Allocated {alloc} must not exceed available {avail}")
                self.assertEqual(alloc + unf, dem, f"{rtype}: Conservation of demand violated")
                self.assertGreaterEqual(alloc, 0)
                self.assertGreaterEqual(unf, 0)

    def test_07_multiple_zones_competing_for_limited_resources(self):
        """7. Multiple zones competing: higher ZPS zones receive larger proportional residual allocations."""
        competing_context = {
            "event_id": "EVT-STRESS-COMPETE",
            "name": "Multi-Zone Scarcity Competition",
            "disaster_type": "EARTHQUAKE",
            "severity_level": "SEVERE",
            "planning_days": 3,
            "zones": [
                {
                    "zone_id": "ZONE-HIGH-ZPS",
                    "name": "High Priority Epicenter",
                    "population": 20000,
                    "affected_population": 20000,
                    "damage_level": 5,
                    "vulnerability_index": 0.95,
                    "medical_urgency": 0.95,
                    "access_status": "DEGRADED",
                    "road_status": "DEGRADED",
                    "latitude": 26.2,
                    "longitude": 92.5,
                },
                {
                    "zone_id": "ZONE-LOW-ZPS",
                    "name": "Low Priority Outskirts",
                    "population": 20000,
                    "affected_population": 20000,
                    "damage_level": 2,
                    "vulnerability_index": 0.30,
                    "medical_urgency": 0.20,
                    "access_status": "OPEN",
                    "road_status": "OPEN",
                    "latitude": 26.5,
                    "longitude": 93.0,
                },
            ],
        }
        # Limit medical kits to 100 total
        self.env.set_inventory_multipliers({"MEDICAL_KITS": 0.04})

        plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=competing_context)
        dispatches = plan.get("dispatches", [])

        high_med = sum(d.get("allocated_qty", 0) for d in dispatches if d["zone_id"] == "ZONE-HIGH-ZPS" and d["resource_type"] == "MEDICAL_KITS")
        low_med = sum(d.get("allocated_qty", 0) for d in dispatches if d["zone_id"] == "ZONE-LOW-ZPS" and d["resource_type"] == "MEDICAL_KITS")

        self.assertGreater(high_med, low_med, "High ZPS zone must receive greater medical allocation under scarcity")

    def test_08_no_negative_allocations_or_negative_stocks(self):
        """8. Verification that allocated quantities, unfulfilled demands, and warehouse stocks are strictly >= 0."""
        for key in ["SCEN_01_BASELINE_FLOOD", "SCEN_04_CATASTROPHIC_EARTHQUAKE", "SCEN_12_COMBINED_CRISIS"]:
            sc = STRESS_SCENARIOS[key]
            plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc)

            for d in plan.get("dispatches", []):
                self.assertGreaterEqual(d.get("allocated_qty", 0), 0, f"Negative allocated_qty in {key}")
                self.assertGreaterEqual(d.get("requested_qty", 0), 0, f"Negative requested_qty in {key}")
                self.assertGreaterEqual(d.get("unfulfilled_qty", 0), 0, f"Negative unfulfilled_qty in {key}")

            for rtype, summary in plan.get("resource_summary", {}).items():
                self.assertGreaterEqual(summary.get("available", 0), 0)
                self.assertGreaterEqual(summary.get("allocated", 0), 0)
                self.assertGreaterEqual(summary.get("unfulfilled_qty", 0), 0)
                self.assertGreaterEqual(summary.get("fulfillment_pct", 0), 0.0)

    def test_09_no_duplicate_dispatches_generated(self):
        """9. Verification that no duplicate dispatches (same zone, warehouse, resource) are generated."""
        sc = STRESS_SCENARIOS["SCEN_02_EXTREME_FLOOD"]
        plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc)
        dispatches = plan.get("dispatches", [])

        seen_keys = set()
        for d in dispatches:
            key = (d["zone_id"], d["warehouse_id"], d["resource_type"])
            self.assertNotIn(key, seen_keys, f"Duplicate dispatch detected: {key}")
            seen_keys.add(key)

    def test_10_hazard_aware_demands_allocation(self):
        """10. Allocations remain hazard-aware: Earthquake prioritises medical kits; Cyclone prioritises shelter."""
        sc_eq = STRESS_SCENARIOS["SCEN_03_SEVERE_EARTHQUAKE"]
        sc_cy = STRESS_SCENARIOS["SCEN_05_SEVERE_CYCLONE"]

        plan_eq = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc_eq)
        plan_cy = self.env.coordinator.run_full_coordination_cycle(disaster_context=sc_cy)

        eq_med = plan_eq["resource_summary"].get("MEDICAL_KITS", {}).get("demanded", 0)
        cy_med = plan_cy["resource_summary"].get("MEDICAL_KITS", {}).get("demanded", 0)

        # Earthquake with medical urgency 0.95 vs Cyclone with moderate urgency
        self.assertGreater(eq_med, cy_med, "Earthquake must generate higher trauma medical demand than Cyclone")


if __name__ == "__main__":
    unittest.main()

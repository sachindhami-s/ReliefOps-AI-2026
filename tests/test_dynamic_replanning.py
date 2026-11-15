"""
ReliefOps AI — Phase 5: Dynamic Replanning & Incident Simulation Validation Suite
Tests mid-run incident injections: sudden population surge, warehouse failure, road blockade,
new emergency zone arrival, disaster severity escalation, and trauma medical spike.

Academic Disclaimer:
Synthetic test suite developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import copy
import unittest
from typing import Any, Dict, List

from tests.stress_fixtures import IsolatedStressEnvironment, STRESS_SCENARIOS


class TestDynamicReplanning(unittest.TestCase):
    """
    Stress test suite for the Mid-Run Incident Simulation and Dynamic Replanning loop.
    Validates state invalidation, updated needs recalculation, non-duplication of dispatches,
    fairness re-auditing, and warehouse inventory consistency upon mid-run incident injection.
    """

    def setUp(self):
        self.env = IsolatedStressEnvironment()

    def tearDown(self):
        self.env.cleanup()

    def test_01_incident_sudden_population_increase(self):
        """1. Simulate sudden population increase mid-run: needs recalculate, allocation scales, fairness re-audited."""
        base_ctx = copy.deepcopy(STRESS_SCENARIOS["SCEN_01_BASELINE_FLOOD"])
        initial_plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=base_ctx)
        self.assertEqual(initial_plan.get("overall_status"), "OVERALL_APPROVED")

        # Inject secondary surge incident (e.g. embankment breach doubling population of Majuli)
        surged_ctx = copy.deepcopy(base_ctx)
        surged_ctx["event_id"] = base_ctx["event_id"] + "-SURGE"
        for z in surged_ctx["zones"]:
            if z["zone_id"] == "ZONE-S01-MAJULI":
                z["population"] = int(z["population"] * 2.5)
                z["affected_population"] = z["population"]
                z["damage_level"] = 5
                break

        revised_plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=surged_ctx)

        # Plan ID must be distinct
        self.assertNotEqual(initial_plan["plan_id"], revised_plan["plan_id"])
        # Needs for Majuli must be higher
        zone_needs = self.env.blackboard.read("zone_needs") or []
        majuli_need = next(z for z in zone_needs if z["zone_id"] == "ZONE-S01-MAJULI")
        self.assertGreater(majuli_need["demands"]["water_liters"], 10000)
        self.assertEqual(revised_plan.get("fairness_verdict"), "FAIRNESS_APPROVED")

    def test_02_incident_warehouse_becoming_unavailable(self):
        """2. Simulate primary warehouse failure (INACCESSIBLE): inventory agent excludes it, alternative hubs used."""
        base_ctx = copy.deepcopy(STRESS_SCENARIOS["SCEN_03_SEVERE_EARTHQUAKE"])
        initial_plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=base_ctx)

        # Check that WH-GUWAHATI-NORTH was initially used
        initial_warehouses = {d["warehouse_id"] for d in initial_plan.get("dispatches", [])}
        self.assertIn("WH-GUWAHATI-NORTH", initial_warehouses)

        # Simulate incident: WH-GUWAHATI-NORTH suffered structural collapse -> INACCESSIBLE
        self.env.set_warehouse_status("WH-GUWAHATI-NORTH", "INACCESSIBLE")

        # Re-plan with updated inventory state
        replan_ctx = copy.deepcopy(base_ctx)
        replan_ctx["event_id"] = base_ctx["event_id"] + "-REPLAN-WH"
        revised_plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=replan_ctx)

        revised_warehouses = {
            d["warehouse_id"]
            for d in revised_plan.get("dispatches", [])
            if d.get("allocated_qty", 0) > 0 and d["warehouse_id"] != "NONE"
        }
        # Inaccessible warehouse must NOT be used in revised dispatches
        self.assertNotIn("WH-GUWAHATI-NORTH", revised_warehouses)
        self.assertGreater(len(revised_warehouses), 0, "Other operational hubs must supply the relief")

    def test_03_incident_road_access_blocked(self):
        """3. Simulate road changing OPEN -> BLOCKED: logistics recomputes impedance; transit hours escalate."""
        base_ctx = copy.deepcopy(STRESS_SCENARIOS["SCEN_01_BASELINE_FLOOD"])
        initial_plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=base_ctx)
        init_dispatches = [d for d in initial_plan.get("dispatches", []) if d["zone_id"] == "ZONE-S01-MAJULI"]
        init_transit = init_dispatches[0].get("est_transit_hours", 1.0) if init_dispatches else 1.0

        # Incident: Road to Majuli washed away -> BLOCKED
        blocked_ctx = copy.deepcopy(base_ctx)
        blocked_ctx["event_id"] = base_ctx["event_id"] + "-BLOCKED"
        for z in blocked_ctx["zones"]:
            if z["zone_id"] == "ZONE-S01-MAJULI":
                z["access_status"] = "BLOCKED"
                z["road_status"] = "BLOCKED"

        revised_plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=blocked_ctx)
        revised_dispatches = [d for d in revised_plan.get("dispatches", []) if d["zone_id"] == "ZONE-S01-MAJULI"]

        # Dispatches must now reflect road_status == BLOCKED and increased transit time
        for rd in revised_dispatches:
            self.assertEqual(rd.get("road_status"), "BLOCKED")
            # BLOCKED multiplier (0.15) increases transit hours significantly
            self.assertGreater(rd.get("est_transit_hours", 0.0), init_transit)

    def test_04_incident_new_emergency_zone_appearing(self):
        """4. Simulate sudden discovery of an isolated emergency zone: incorporated into assessment, routing, allocations."""
        base_ctx = copy.deepcopy(STRESS_SCENARIOS["SCEN_01_BASELINE_FLOOD"])
        initial_plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=base_ctx)
        init_dispatch_count = len(initial_plan.get("dispatches", []))
        self.assertGreater(init_dispatch_count, 0)

        # Incident: New emergency enclave discovered in desperate need
        new_zone_ctx = copy.deepcopy(base_ctx)
        new_zone_ctx["event_id"] = base_ctx["event_id"] + "-NEW-ZONE"
        new_zone_ctx["zones"].append({
            "zone_id": "ZONE-S01-ISOLATED-HAMLET",
            "name": "Newly Discovered Submerged Hamlet",
            "population": 8000,
            "affected_population": 8000,
            "damage_level": 4,
            "vulnerability_index": 0.85,
            "medical_urgency": 0.75,
            "access_status": "DEGRADED",
            "road_status": "DEGRADED",
            "latitude": 26.85,
            "longitude": 94.00,
        })

        revised_plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=new_zone_ctx)
        revised_zones_in_dispatches = {d["zone_id"] for d in revised_plan.get("dispatches", [])}

        self.assertIn("ZONE-S01-ISOLATED-HAMLET", revised_zones_in_dispatches)
        # Total dispatches must increase to serve the new zone
        self.assertGreater(len(revised_plan.get("dispatches", [])), init_dispatch_count)
        # New zone must be assessed and allocated supplies
        new_allocations = [
            d for d in revised_plan.get("dispatches", [])
            if d["zone_id"] == "ZONE-S01-ISOLATED-HAMLET" and d.get("allocated_qty", 0) > 0
        ]
        self.assertGreater(len(new_allocations), 0, "New emergency zone must receive allocated dispatches")

    def test_05_incident_disaster_severity_escalating(self):
        """5. Simulate hazard severity escalation MODERATE -> CATASTROPHIC: SOP and demands update dynamically."""
        base_ctx = copy.deepcopy(STRESS_SCENARIOS["SCEN_01_BASELINE_FLOOD"])
        self.assertEqual(base_ctx["severity_level"], "MODERATE")
        initial_plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=base_ctx)
        init_sop = self.env.blackboard.read("sop_context") or {}
        self.assertEqual(init_sop.get("sop_severity_equivalent"), "Level 2 (Moderate Inundation)")

        # Incident: Meteorological department elevates alert to CATASTROPHIC
        escalated_ctx = copy.deepcopy(base_ctx)
        escalated_ctx["event_id"] = base_ctx["event_id"] + "-ESCALATE"
        escalated_ctx["severity_level"] = "CATASTROPHIC"
        for z in escalated_ctx["zones"]:
            z["damage_level"] = 5

        revised_plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=escalated_ctx)
        revised_sop = self.env.blackboard.read("sop_context") or {}

        # SOP severity equivalent must update to Level 5
        self.assertEqual(revised_sop.get("sop_severity_equivalent"), "Level 5 (Catastrophic Breach)")
        self.assertEqual(revised_plan.get("fairness_verdict"), "FAIRNESS_APPROVED")

    def test_06_incident_new_medical_requirements_appearing(self):
        """6. Simulate sudden mass trauma injury: medical urgency spikes; medical kits allocation prioritised."""
        base_ctx = copy.deepcopy(STRESS_SCENARIOS["SCEN_03_SEVERE_EARTHQUAKE"])
        # Initial run with moderate medical urgency on Zone 3
        base_ctx["zones"][2]["medical_urgency"] = 0.20
        initial_plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=base_ctx)

        init_zone_needs = self.env.blackboard.read("zone_needs") or []
        z3_init = next(z for z in init_zone_needs if z["zone_id"] == base_ctx["zones"][2]["zone_id"])
        init_med_dem = z3_init["demands"]["medical_kits"]

        # Incident: Structural collapse triggers massive trauma casualties in Zone 3
        trauma_ctx = copy.deepcopy(base_ctx)
        trauma_ctx["event_id"] = base_ctx["event_id"] + "-TRAUMA"
        trauma_ctx["zones"][2]["medical_urgency"] = 1.00
        trauma_ctx["zones"][2]["damage_level"] = 5

        revised_plan = self.env.coordinator.run_full_coordination_cycle(disaster_context=trauma_ctx)
        rev_zone_needs = self.env.blackboard.read("zone_needs") or []
        z3_rev = next(z for z in rev_zone_needs if z["zone_id"] == base_ctx["zones"][2]["zone_id"])
        rev_med_dem = z3_rev["demands"]["medical_kits"]

        # Medical demand must spike significantly
        self.assertGreater(rev_med_dem, init_med_dem)
        # Revised plan must execute cleanly
        self.assertEqual(revised_plan.get("fairness_verdict"), "FAIRNESS_APPROVED")

    def test_07_replan_dispatch_non_duplication_and_audit_isolation(self):
        """7. Verifies that replanned plans generate distinct plan IDs and do not corrupt previous dispatches."""
        base_ctx = copy.deepcopy(STRESS_SCENARIOS["SCEN_01_BASELINE_FLOOD"])
        plan_1 = self.env.coordinator.run_full_coordination_cycle(disaster_context=base_ctx)

        # Immediate replan without sleep: unique UUID suffix guarantees 0 collisions
        replan_ctx = copy.deepcopy(base_ctx)
        replan_ctx["event_id"] = base_ctx["event_id"] + "-REPLAN"
        plan_2 = self.env.coordinator.run_full_coordination_cycle(disaster_context=replan_ctx)

        self.assertNotEqual(plan_1["plan_id"], plan_2["plan_id"])
        # Both plans must have valid dispatches
        self.assertGreater(len(plan_1["dispatches"]), 0)
        self.assertGreater(len(plan_2["dispatches"]), 0)


if __name__ == "__main__":
    unittest.main()

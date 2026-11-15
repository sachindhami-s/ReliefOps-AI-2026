"""
Phase 7 Regression Test Suite — Execution Integrity and Telemetry Correction
Tests:
1. Correct hazard propagation for all four hazards (FLOOD, EARTHQUAKE, CYCLONE, LANDSLIDE).
2. Hazard consistency during dynamic replanning (Phase 1 and Phase 2).
3. Unique canonical scenario IDs (SCEN-01..SCEN-04).
4. Correct inventory fulfillment percentages (capped at 100.0%, never > 100%).
5. Zero-demand edge cases.
6. Inventory surplus calculations.
7. Resource shortage detection.
8. Existing fairness and allocation behaviour preservation.
"""

import io
import json
from contextlib import redirect_stdout
import pytest

from backend.database.db_manager import DatabaseManager
from backend.database.seeder import seed_database, build_scenario_context
from backend.blackboard.blackboard_manager import BlackboardManager
from backend.agents.needs_assessment_agent import NeedsAssessmentAgent
from backend.agents.inventory_agent import InventoryAgent
from backend.plugins.inventory_plugin import InventoryPlugin
from backend.agents.relief_coordinator import ReliefCoordinator
from backend.plugins.coordinator_plugin import CoordinatorPlugin
from backend.plugins.fairness_plugin import FairnessPlugin
from demo_pipeline import display_plan_telemetry, run_dynamic_replanning_demo


@pytest.fixture
def isolated_db(tmp_path):
    """Provides an isolated seeded SQLite database for deterministic testing."""
    db_file = tmp_path / "test_phase7_telemetry.db"
    db = DatabaseManager(db_path=str(db_file))
    seed_database(db)
    return db


class TestExecutionIntegrityAndTelemetry:
    """Comprehensive regression tests for Phase 7 Execution Integrity and Telemetry Correction."""

    def test_1_hazard_propagation_all_four_hazards(self, isolated_db):
        """
        Verifies that hazard metadata propagates end-to-end from scenario configuration
        through NeedsAssessmentPlugin, NeedsAssessmentAgent, Blackboard ('sop_context'
        and 'disaster_context'), ReliefCoordinator plan output, and terminal telemetry
        without ever displaying 'UNKNOWN'.
        """
        expected_sop_map = {
            "FLOOD": "SOP-FL-001",
            "EARTHQUAKE": "SOP-EQ-002",
            "CYCLONE": "SOP-CY-004",
            "LANDSLIDE": "SOP-LS-003",
        }
        canonical_scenarios = {
            "FLOOD": "SCEN-01",
            "EARTHQUAKE": "SCEN-02",
            "CYCLONE": "SCEN-03",
            "LANDSLIDE": "SCEN-04",
        }

        for hazard, expected_sop in expected_sop_map.items():
            scen_id = canonical_scenarios[hazard]
            ctx = build_scenario_context(scenario_id=scen_id, planning_days=3, db=isolated_db)
            ctx["hazard"] = hazard
            ctx["disaster_type"] = hazard

            bb = BlackboardManager(db=isolated_db)
            coordinator = ReliefCoordinator(blackboard=bb, db=isolated_db)
            plan = coordinator.run_full_coordination_cycle(disaster_context=ctx)
            snapshot = bb.get_snapshot()

            # Check Blackboard sop_context
            sop_ctx = snapshot.get("sop_context", {})
            assert sop_ctx.get("hazard") == hazard, f"Expected sop_context['hazard']={hazard}, got {sop_ctx.get('hazard')}"
            assert sop_ctx.get("disaster_type") == hazard
            assert expected_sop in sop_ctx.get("sop_ids", []), f"Expected {expected_sop} for {hazard}"

            # Check Blackboard disaster_context
            dis_ctx = snapshot.get("disaster_context", {})
            assert dis_ctx.get("hazard") == hazard
            assert dis_ctx.get("disaster_type") == hazard

            # Check Coordinator final plan
            assert plan.get("hazard") == hazard
            assert plan.get("disaster_type") == hazard

            # Check printed telemetry output does not contain UNKNOWN
            buf = io.StringIO()
            with redirect_stdout(buf):
                display_plan_telemetry(plan=plan, blackboard=bb)
            telemetry_str = buf.getvalue()
            assert f"Disaster Hazard:         {hazard}" in telemetry_str
            assert "Disaster Hazard:         UNKNOWN" not in telemetry_str
            assert expected_sop in telemetry_str

    def test_2_hazard_consistency_during_dynamic_replanning(self, isolated_db):
        """
        Verifies that mid-run dynamic replanning preserves the active hazard context
        across Phase 1 and Phase 2, both via run_dynamic_replanning_demo() and when
        a partial update omits explicit hazard fields on the same Blackboard.
        """
        # Part A: Test run_dynamic_replanning_demo end-to-end
        buf = io.StringIO()
        with redirect_stdout(buf):
            revised_plan = run_dynamic_replanning_demo(planning_days=3, db=isolated_db)
        out = buf.getvalue()

        assert revised_plan.get("hazard") == "LANDSLIDE"
        assert revised_plan.get("disaster_type") == "LANDSLIDE"
        assert "Disaster Hazard:         LANDSLIDE" in out
        assert "Disaster Hazard:         UNKNOWN" not in out
        assert "SOP-LS-003" in out

        # Part B: Test partial replanning context where Phase 2 omits 'hazard'/'disaster_type'
        bb = BlackboardManager(db=isolated_db)
        coordinator = ReliefCoordinator(blackboard=bb, db=isolated_db)

        ctx_phase1 = build_scenario_context(scenario_id="SCEN-02", planning_days=3, db=isolated_db)
        assert ctx_phase1["hazard"] == "EARTHQUAKE"
        plan1 = coordinator.run_full_coordination_cycle(disaster_context=ctx_phase1)
        assert plan1["hazard"] == "EARTHQUAKE"

        # Simulate Phase 2 incident update that only passes updated zones without 'hazard' or 'disaster_type'
        ctx_phase2 = {
            "scenario_id": "SCEN-02",
            "name": "Secondary Aftershock Replanning",
            "severity": "CATASTROPHIC",
            "planning_days": 3,
            "zones": ctx_phase1["zones"],
        }
        plan2 = coordinator.run_full_coordination_cycle(disaster_context=ctx_phase2)
        snap2 = bb.get_snapshot()

        assert plan2["hazard"] == "EARTHQUAKE"
        assert snap2["sop_context"]["hazard"] == "EARTHQUAKE"
        assert "SOP-EQ-002" in snap2["sop_context"]["sop_ids"]

    def test_3_unique_canonical_scenario_ids(self, isolated_db):
        """
        Verifies that each canonical scenario ID maps to its unique canonical hazard:
        - SCEN-01: FLOOD
        - SCEN-02: EARTHQUAKE
        - SCEN-03: CYCLONE
        - SCEN-04: LANDSLIDE
        """
        expected_canonical = {
            "SCEN-01": ("FLOOD", "EVT-2026-FL01"),
            "SCEN-02": ("EARTHQUAKE", "EVT-2026-EQ01"),
            "SCEN-03": ("CYCLONE", "EVT-2026-CY01"),
            "SCEN-04": ("LANDSLIDE", "EVT-2026-LS01"),
        }

        seen_hazards = set()
        for scen_id, (expected_hazard, expected_event_id) in expected_canonical.items():
            ctx = build_scenario_context(scenario_id=scen_id, planning_days=3, db=isolated_db)
            assert ctx["scenario_id"] == scen_id
            assert ctx["hazard"] == expected_hazard
            assert ctx["disaster_type"] == expected_hazard
            assert ctx["event_id"] == expected_event_id
            seen_hazards.add(ctx["hazard"])

        assert len(seen_hazards) == 4, "All 4 canonical scenarios must map to 4 distinct hazards."

    def test_4_inventory_fulfillment_percentage_capped_at_100(self, isolated_db):
        """
        Verifies that Fulfillment Percentage = (Allocated / Demanded) * 100 and is
        capped at 100.0% when Available > Demanded (e.g., Demanded=28,960, Available=120,000
        must report Fulfillment=100.0%, Allocated=28,960, Surplus=91,040, never 414.4%).
        """
        bb = BlackboardManager(db=isolated_db)
        # Seed zone_needs with exact Demanded = 28,960 for food_packs
        bb.update(
            "zone_needs",
            [
                {
                    "zone_id": "ZONE-MAJULI-ISLAND",
                    "zone_name": "Majuli Island Riverine Sector",
                    "affected_population": 14480,
                    "zps": 82.5,
                    "priority_rank": 1,
                    "demands": {
                        "food_packs": 28960,
                        "water_liters": 100000,
                        "medical_kits": 1200,
                        "tents": 2000,
                    },
                }
            ],
            agent_name="TestSetup",
        )

        inv_agent = InventoryAgent(blackboard=bb, plugin=InventoryPlugin(db=isolated_db))
        result = inv_agent.execute()["inventory_snapshot"]
        food_feas = result["feasibility"]["FOOD_RATIONS"]

        assert food_feas["demanded"] == 28960
        assert food_feas["available"] == 120000
        assert food_feas["allocated"] == 28960
        assert food_feas["fulfillment_pct"] == 100.0
        assert food_feas["coverage_pct"] == 100.0
        assert food_feas["unfulfilled_qty"] == 0
        assert food_feas["shortage_qty"] == 0
        assert food_feas["surplus_qty"] == 91040
        assert food_feas["status"] == "ADEQUATE"

        # Verify all resources have fulfillment_pct <= 100.0
        for rtype, metrics in result["feasibility"].items():
            assert 0.0 <= metrics["fulfillment_pct"] <= 100.0, f"{rtype} fulfillment exceeded 100%: {metrics['fulfillment_pct']}"
            assert 0.0 <= metrics["coverage_pct"] <= 100.0

    def test_5_zero_demand_edge_cases(self, isolated_db):
        """
        Verifies zero-demand edge cases across InventoryAgent, CoordinatorPlugin,
        and FairnessAuditorPlugin without division-by-zero errors or >100% ratios.
        """
        bb = BlackboardManager(db=isolated_db)
        bb.update(
            "zone_needs",
            [
                {
                    "zone_id": "ZONE-MAJULI-ISLAND",
                    "zone_name": "Majuli Island",
                    "affected_population": 1000,
                    "zps": 50.0,
                    "priority_rank": 1,
                    "demands": {
                        "food_packs": 0,
                        "water_liters": 0,
                        "medical_kits": 0,
                        "tents": 0,
                    },
                }
            ],
            agent_name="TestSetup",
        )

        inv_agent = InventoryAgent(blackboard=bb, plugin=InventoryPlugin(db=isolated_db))
        res = inv_agent.execute()["inventory_snapshot"]

        for rtype, f in res["feasibility"].items():
            assert f["demanded"] == 0
            assert f["allocated"] == 0
            assert f["fulfillment_pct"] == 100.0
            assert f["unfulfilled_qty"] == 0
            assert f["surplus_qty"] == f["available"]
            assert f["status"] == "ADEQUATE"

    def test_6_inventory_surplus_and_shortage_detection(self, isolated_db):
        """
        Verifies independent reporting of Demanded, Available, Allocated,
        Fulfillment %, Unfulfilled quantity, Surplus inventory, and Shortage status
        when demand exceeds available stock vs. when stock exceeds demand.
        """
        bb = BlackboardManager(db=isolated_db)
        # Available in seeded DB:
        # FOOD_RATIONS: 120,000 (Test Surplus: demand 50,000 -> surplus 70,000)
        # CLEAN_WATER: 350,000 (Test Shortage: demand 500,000 -> allocated 350,000, unfulfilled 150,000, fulfillment 70.0%)
        # MEDICAL_KITS: 2,400 (Test Critical Shortage: demand 10,000 -> allocated 2,400, unfulfilled 7,600, fulfillment 24.0%)
        # SHELTER_TENTS: 4,500 (Test Exact Match: demand 4,500 -> allocated 4,500, surplus 0, unfulfilled 0, fulfillment 100.0%)
        bb.update(
            "zone_needs",
            [
                {
                    "zone_id": "ZONE-MAJULI-ISLAND",
                    "zone_name": "Majuli Island",
                    "affected_population": 50000,
                    "zps": 90.0,
                    "priority_rank": 1,
                    "demands": {
                        "food_packs": 50000,
                        "water_liters": 500000,
                        "medical_kits": 10000,
                        "tents": 4500,
                    },
                }
            ],
            agent_name="TestSetup",
        )

        inv_agent = InventoryAgent(blackboard=bb, plugin=InventoryPlugin(db=isolated_db))
        res = inv_agent.execute()["inventory_snapshot"]
        feas = res["feasibility"]

        # 1. Surplus case (FOOD_RATIONS)
        food = feas["FOOD_RATIONS"]
        assert food["demanded"] == 50000
        assert food["available"] == 120000
        assert food["allocated"] == 50000
        assert food["fulfillment_pct"] == 100.0
        assert food["unfulfilled_qty"] == 0
        assert food["surplus_qty"] == 70000
        assert food["status"] == "ADEQUATE"

        # 2. Moderate Shortage case (CLEAN_WATER)
        water = feas["CLEAN_WATER"]
        assert water["demanded"] == 500000
        assert water["available"] == 350000
        assert water["allocated"] == 350000
        assert water["fulfillment_pct"] == 70.0
        assert water["unfulfilled_qty"] == 150000
        assert water["surplus_qty"] == 0
        assert water["status"] == "SHORTAGE"

        # 3. Critical Shortage case (MEDICAL_KITS)
        med = feas["MEDICAL_KITS"]
        assert med["demanded"] == 10000
        assert med["available"] == 2400
        assert med["allocated"] == 2400
        assert med["fulfillment_pct"] == 24.0
        assert med["unfulfilled_qty"] == 7600
        assert med["surplus_qty"] == 0
        assert med["status"] == "CRITICAL_SHORTAGE"

        # 4. Exact Match case (SHELTER_TENTS)
        tents = feas["SHELTER_TENTS"]
        assert tents["demanded"] == 4500
        assert tents["available"] == 4500
        assert tents["allocated"] == 4500
        assert tents["fulfillment_pct"] == 100.0
        assert tents["unfulfilled_qty"] == 0
        assert tents["surplus_qty"] == 0
        assert tents["status"] == "ADEQUATE"

        assert res["adequacy_status"] == "RESOURCE_SHORTAGE"

    def test_7_fairness_and_allocation_behaviour_preserved(self, isolated_db):
        """
        Verifies that existing fairness auditing (Gini <= 0.35, survival floor)
        and two-phase water-filling allocation remain completely intact across
        all 4 canonical scenarios.
        """
        for scen_id in ["SCEN-01", "SCEN-02", "SCEN-03", "SCEN-04"]:
            ctx = build_scenario_context(scenario_id=scen_id, planning_days=3, db=isolated_db)
            bb = BlackboardManager(db=isolated_db)
            coordinator = ReliefCoordinator(blackboard=bb, db=isolated_db)
            plan = coordinator.run_full_coordination_cycle(disaster_context=ctx)

            audit = plan.get("audit_verdict", {})
            assert audit.get("fairness_verdict") == "FAIRNESS_APPROVED"
            assert audit.get("gini_coefficient", 1.0) <= 0.35
            assert len(plan.get("dispatches", [])) > 0

            # Verify resource_adequacy in final plan also caps fulfillment_pct at 100% and reports surplus_qty
            for rtype, r_metrics in plan.get("resource_adequacy", {}).items():
                assert 0.0 <= r_metrics.get("fulfillment_pct", 0.0) <= 100.0
                assert "surplus_qty" in r_metrics
                assert r_metrics["surplus_qty"] >= 0

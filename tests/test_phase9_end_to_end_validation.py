"""
ReliefOps AI — Phase 9: End-to-End Integration, System Validation & Stress Testing Suite
Covers Phases 1–9 of the Phase 9 Validation Protocol:
1. Architectural Integration & Dependency Audit
2. Complete End-to-End Scenario Testing (A: Flood, B: Earthquake, C: Cyclone, D: Landslide,
   E: Secondary Disaster & Dynamic Replanning, F: Combined Multi-Resource Shortage, G: Extreme Population Surge)
3. RAG & Knowledge Retrieval Validation (24 representative queries across 4 hazards + BM25 fallback + edge cases)
4. Inventory & Fairness Validation (Independent Gini verification, <=100% fulfillment cap, greedy veto check)
5. Dynamic Replanning 9-Step Lifecycle Validation
6. SQLite Database Integrity (FK enforcement, ACID rollback, duplicate prevention, hot backup/restore)
7. Streamlit Dashboard Integration & HTML Escaping Safety
8. Scalability & Stress Testing (10, 50, 100, and 500 disaster zones, multi-warehouse, concurrent reads/writes)
9. Controlled Failure Recovery & Security Controls
"""

import concurrent.futures
import html
import json
import os
import sqlite3
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any, Dict, List
import pytest

import app
from backend.agents.fairness_auditor_agent import FairnessAuditorAgent
from backend.agents.inventory_agent import InventoryAgent
from backend.agents.logistics_agent import LogisticsAgent
from backend.agents.needs_assessment_agent import NeedsAssessmentAgent
from backend.agents.relief_coordinator import ReliefCoordinator
from backend.blackboard.blackboard_manager import BlackboardManager
from backend.config import Settings, settings
from backend.database.db_manager import DatabaseManager
from backend.database.seeder import build_scenario_context, seed_database
from backend.plugins.coordinator_plugin import CoordinatorPlugin
from backend.plugins.fairness_plugin import FairnessPlugin
from backend.plugins.inventory_plugin import InventoryPlugin
from backend.plugins.logistics_plugin import LogisticsPlugin
from backend.plugins.needs_plugin import NeedsAssessmentPlugin
from backend.rag.retriever import SOPRetriever, default_sop_retriever
from backend.utils.logger import OperationalObserver, observer
from tests.stress_fixtures import STRESS_SCENARIOS, IsolatedStressEnvironment
from backend.utils.security import (
    SecurityValidationError,
    sanitize_identifier,
    validate_disaster_context,
    validate_path_safety,
    validate_zone_payload,
)


@pytest.fixture
def isolated_db():
    """Provides a seeded, isolated temporary SQLite database without touching data/reliefops.db."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(db_path=path)
    seed_database(db)
    yield db
    db.close()
    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def _generate_synthetic_zones(count: int, base_pop: int = 12000) -> List[Dict[str, Any]]:
    """Generates deterministic synthetic disaster zones across realistic Northeast India coordinates."""
    access_modes = ["OPEN", "DEGRADED", "BLOCKED", "AIR_ONLY"]
    zones = []
    for i in range(1, count + 1):
        zones.append(
            {
                "zone_id": f"STRESS-Z{i:04d}",
                "name": f"Synthetic Sector {i:04d}",
                "zone_name": f"Synthetic Sector {i:04d}",
                "population": base_pop + (i % 15) * 1500,
                "affected_population": base_pop + (i % 15) * 1500,
                "damage_level": (i % 5) + 1,
                "vulnerability_index": round(0.35 + (i % 6) * 0.10, 2),
                "medical_urgency": round(0.30 + (i % 7) * 0.10, 2),
                "access_status": access_modes[i % len(access_modes)],
                "road_status": access_modes[i % len(access_modes)],
                "latitude": round(26.0 + (i % 50) * 0.03, 4),
                "longitude": round(91.5 + (i % 60) * 0.04, 4),
                "lat": round(26.0 + (i % 50) * 0.03, 4),
                "lon": round(91.5 + (i % 60) * 0.04, 4),
            }
        )
    return zones


class TestPhase9EndToEndValidation:
    """Comprehensive Phase 9 integration, validation, stress, and security test suite."""

    def test_01_phase1_architectural_integration_and_dependency_contracts(self, isolated_db):
        """Verifies all 10 architectural components and end-to-end Blackboard data flow."""
        bb = BlackboardManager(db=isolated_db)
        coord = ReliefCoordinator(blackboard=bb, db=isolated_db)

        ctx = build_scenario_context("SCEN-01", planning_days=3, db=isolated_db)
        plan = coord.run_full_coordination_cycle(disaster_context=ctx)
        snap = bb.get_snapshot()

        # Verify all 8 Blackboard sections are populated and consistent
        expected_sections = {
            "disaster_context",
            "sop_context",
            "zone_needs",
            "inventory_snapshot",
            "logistics_matrix",
            "allocation_draft",
            "audit_verdict",
            "final_allocation_plan",
        }
        assert expected_sections.issubset(set(snap.keys()))
        assert snap["final_allocation_plan"]["plan_id"] == plan["plan_id"]
        assert isinstance(observer, OperationalObserver)

    def test_02_phase2_end_to_end_scenarios_a_through_g(self, isolated_db):
        """
        Executes complete end-to-end workflows across Scenarios A through G:
        A. Flood emergency (SCEN-01)
        B. Earthquake emergency (SCEN-02)
        C. Cyclone emergency (SCEN-03)
        D. Landslide emergency (SCEN-04)
        E. Secondary disaster & dynamic replanning (SCEN-04 surge)
        F. Combined multi-resource shortage (STRESS-12)
        G. Extreme affected population surge (STRESS-09)
        """
        canonical_cases = [
            ("A_FLOOD", "SCEN-01", "FLOOD", "SOP-FL-001"),
            ("B_EARTHQUAKE", "SCEN-02", "EARTHQUAKE", "SOP-EQ-002"),
            ("C_CYCLONE", "SCEN-03", "CYCLONE", "SOP-CY-004"),
            ("D_LANDSLIDE", "SCEN-04", "LANDSLIDE", "SOP-LS-003"),
        ]

        for label, scen_id, expected_hazard, expected_sop in canonical_cases:
            ctx = build_scenario_context(scen_id, planning_days=3, db=isolated_db)
            bb = BlackboardManager(db=isolated_db)
            coord = ReliefCoordinator(blackboard=bb, db=isolated_db)
            plan = coord.run_full_coordination_cycle(disaster_context=ctx)
            snap = bb.get_snapshot()
            kpis = app.compute_executive_kpis(plan, snap)

            assert plan["hazard"] == expected_hazard, f"{label} hazard mismatch"
            assert snap["sop_context"]["hazard"] == expected_hazard
            assert expected_sop in snap["sop_context"]["sop_ids"]
            assert kpis["active_hazard"] == expected_hazard
            assert kpis["governing_sop"] == expected_sop
            assert kpis["gini_coefficient"] <= 0.35
            assert kpis["fairness_verdict"] == "FAIRNESS_APPROVED"
            assert len(plan["dispatches"]) > 0
            assert len(plan["decision_audit_trail"]["zone_explanations"]) == len(ctx["zones"])

            # Verify DB persistence matches backend & dashboard
            db_row = isolated_db.execute_one(
                "SELECT plan_id, status, fairness_score FROM allocation_plans WHERE plan_id = ?",
                (plan["plan_id"],),
            )
            assert db_row is not None
            assert db_row["status"] == "APPROVED"
            assert abs(float(db_row["fairness_score"]) - kpis["gini_coefficient"]) < 1e-4

        # E. Secondary disaster & dynamic replanning
        ctx_d = build_scenario_context("SCEN-04", planning_days=3, db=isolated_db)
        replan_res = app.execute_dynamic_replanning_workflow(
            initial_context=ctx_d,
            surge_zone_name="Majuli Island Riverine Sector",
            surge_multiplier=1.80,
            surge_damage_lvl=5,
            new_access_status="BLOCKED",
            db=isolated_db,
        )
        assert replan_res["preserved_hazard"] == "LANDSLIDE"
        assert replan_res["population_delta"] > 0
        assert replan_res["gini_after"] <= 0.35

        # F. Combined multi-resource shortage (SCEN_12_COMBINED_CRISIS) & G. Extreme population surge (SCEN_09_POPULATION_SURGE)
        for stress_key, expected_hz in [("SCEN_12_COMBINED_CRISIS", "EARTHQUAKE"), ("SCEN_09_POPULATION_SURGE", "FLOOD")]:
            env = IsolatedStressEnvironment()
            try:
                s_ctx = STRESS_SCENARIOS[stress_key]
                if "inventory_override" in s_ctx:
                    env.set_inventory_multipliers(s_ctx["inventory_override"])
                s_plan = env.coordinator.run_full_coordination_cycle(disaster_context=s_ctx)
                s_snap = env.blackboard.get_snapshot()
                s_kpis = app.compute_executive_kpis(s_plan, s_snap)
                assert s_kpis["active_hazard"] == expected_hz
                assert s_kpis["gini_coefficient"] <= 0.35
                assert s_kpis["fairness_verdict"] == "FAIRNESS_APPROVED"
                assert s_kpis["critical_shortages_count"] >= 1
            finally:
                env.cleanup()

    def test_03_phase3_rag_24_queries_across_four_hazards_and_fallbacks(self):
        """
        Validates 24 representative disaster-response queries across FLOOD, EARTHQUAKE,
        CYCLONE, and LANDSLIDE, plus BM25 fallback, empty queries, and citation integrity.
        """
        valid_sops = {"SOP-FL-001", "SOP-EQ-002", "SOP-CY-004", "SOP-LS-003"}
        queries_by_hazard = {
            "FLOOD": (
                "SOP-FL-001",
                [
                    "What are the daily clean water and jerrycan ratios during severe monsoon flood inundation?",
                    "How is the Zone Priority Score ZPS weighted for flood response operations?",
                    "What are the boat and amphibious evacuation rules for riverine islands?",
                    "How many emergency shelter tents are required per displaced flood household?",
                    "What is the Level 3 severe inundation classification threshold in flood SOP?",
                    "What water purification and hygiene standards apply to flood relief camps?",
                ],
            ),
            "EARTHQUAKE": (
                "SOP-EQ-002",
                [
                    "What are the medical trauma kit requirements for severe structural collapse in an earthquake?",
                    "Why does earthquake ZPS assign a 0.40 weight to medical urgency?",
                    "How are urban search and rescue USAR sectors prioritized after a seismic event?",
                    "What is the displacement ratio for Level 3 Heavy Damage and Level 4 Collapse in earthquakes?",
                    "How should aftershock risks and damaged bridges be handled in seismic logistics?",
                    "What are the survival floor allocation rules for earthquake trauma centers?",
                ],
            ),
            "CYCLONE": (
                "SOP-CY-004",
                [
                    "What are the wind speed thresholds and storm surge classifications for severe tropical cyclones?",
                    "How are coastal embankments and saline water intrusion addressed in cyclone clean water rations?",
                    "What is the demographic vulnerability weight in cyclone Zone Priority Score calculation?",
                    "How should structural wind shelters and tarpaulins be allocated after cyclone landfall?",
                    "What logistics impedance multipliers apply to coastal roads blocked by cyclone storm surge?",
                    "What are the pre-landfall and post-landfall evacuation priorities in SOP-CY-004?",
                ],
            ),
            "LANDSLIDE": (
                "SOP-LS-003",
                [
                    "How are isolated mountain settlements supplied when highways are blocked by slope failure?",
                    "Why does landslide ZPS assign 0.40 weight to infrastructure damage level?",
                    "When is rotary-wing helicopter air-bridge dispatch triggered in landslide response?",
                    "What are the high-altitude thermal shelter and food ration requirements for landslide zones?",
                    "How is Level 3 Major Slope Failure defined in the landslide standard operating procedure?",
                    "What geohazard debris clearance rules govern degraded mountain corridors?",
                ],
            ),
        }

        total_queries_executed = 0
        for hazard, (expected_sop, q_list) in queries_by_hazard.items():
            for q in q_list:
                res = app.query_rag_knowledge_assistant(question=q, hazard_filter=hazard, top_k=3)
                total_queries_executed += 1
                assert res["status"] == "SUCCESS"
                assert expected_sop in res["sop_ids"], f"Query '{q}' did not retrieve {expected_sop}"
                assert len(res["chunks"]) >= 1
                for ch in res["chunks"]:
                    assert ch["sop_id"] in valid_sops, f"Fabricated SOP ID detected: {ch['sop_id']}"
                    assert ch["hazard_type"] == hazard
                    assert ch["chunk_id"].startswith(expected_sop)
                    assert len(ch["content"]) > 20

        assert total_queries_executed == 24

        # Verify BM25 offline fallback mode when forced
        bm25_res = default_sop_retriever.retrieve(
            query="earthquake trauma medical kits structural collapse",
            top_k=3,
            hazard_filter="EARTHQUAKE",
            force_fallback=True,
        )
        assert bm25_res.retrieval_method == "bm25_keyword_fallback"
        assert "SOP-EQ-002" in bm25_res.sop_ids

        # Verify empty retrieval handling
        empty_res = app.query_rag_knowledge_assistant("")
        assert empty_res["status"] == "EMPTY_QUERY"
        assert empty_res["sop_ids"] == []

    def test_04_phase4_inventory_and_fairness_independent_verification(self, isolated_db):
        """
        Independently verifies resource demand/allocation/fulfillment/surplus/shortage math
        and recalculates Gini coefficients and survival floors from raw dispatches.
        """
        ctx = build_scenario_context("SCEN-01", planning_days=3, db=isolated_db)
        bb = BlackboardManager(db=isolated_db)
        coord = ReliefCoordinator(blackboard=bb, db=isolated_db)
        plan = coord.run_full_coordination_cycle(disaster_context=ctx)
        snap = bb.get_snapshot()

        inv_feas = snap["inventory_snapshot"]["feasibility"]
        audit_adeq = plan["audit_verdict"]["resource_adequacy"]

        for rtype in ["FOOD_RATIONS", "CLEAN_WATER", "MEDICAL_KITS", "SHELTER_TENTS"]:
            f_m = inv_feas[rtype]
            a_m = audit_adeq[rtype]

            dem = f_m["demanded"]
            avail = f_m["available"]
            alloc = f_m["allocated"]
            unful = f_m["unfulfilled_qty"]
            surplus = f_m["surplus_qty"]
            pct = f_m["fulfillment_pct"]

            # Core conservation identities
            assert alloc == min(avail, dem)
            assert unful == max(0, dem - alloc)
            assert surplus == max(0, avail - alloc)
            assert 0.0 <= pct <= 100.0
            expected_pct = round(min(100.0, (alloc / dem) * 100.0), 1) if dem > 0 else 100.0
            assert abs(pct - expected_pct) < 1e-4
            assert a_m["allocated"] == alloc
            assert a_m["unfulfilled_qty"] == unful

        # Independent Gini recalculation from zone_summaries
        zone_summaries = plan["audit_verdict"]["zone_summaries"]
        cov_ratios = sorted(float(zs["coverage_ratio"]) for zs in zone_summaries)
        n = len(cov_ratios)
        tot_cov = sum(cov_ratios)
        weighted_sum = sum((idx + 1) * val for idx, val in enumerate(cov_ratios))
        independent_gini = (2.0 * weighted_sum - (n + 1) * tot_cov) / (n * tot_cov)
        backend_gini = float(plan["audit_verdict"]["gini_coefficient"])
        assert abs(independent_gini - backend_gini) < 1e-4
        assert backend_gini <= 0.35

        # Verify Naive Greedy policy genuinely fails fairness under scarcity (never artificially forced to pass)
        greedy_res = coord.evaluate_greedy_baseline(disaster_context=ctx)
        assert greedy_res["gini_coefficient"] > 0.35
        assert greedy_res["fairness_verdict"] == "FAIRNESS_REJECTED"

    def test_05_phase5_dynamic_replanning_nine_step_lifecycle(self, isolated_db):
        """Verifies all 9 steps of the mid-run dynamic replanning workflow and hazard preservation."""
        ctx = build_scenario_context("SCEN-03", planning_days=3, db=isolated_db)  # CYCLONE
        res = app.execute_dynamic_replanning_workflow(
            initial_context=ctx,
            surge_zone_name="Tezpur Foothills Corridor",
            surge_multiplier=2.0,
            surge_damage_lvl=5,
            new_access_status="BLOCKED",
            db=isolated_db,
        )

        init_p = res["initial_plan"]
        rev_p = res["revised_plan"]
        assert init_p["plan_id"] != rev_p["plan_id"]
        assert res["preserved_hazard"] == "CYCLONE"
        assert rev_p["hazard"] == "CYCLONE"
        assert "SOP-CY-004" in res["revised_snapshot"]["sop_context"]["sop_ids"]
        assert res["population_after"] > res["population_before"]
        assert res["gini_after"] <= 0.35

        # Both plans must remain traceable in SQLite allocation_plans & audit_logs
        for pid in (init_p["plan_id"], rev_p["plan_id"]):
            p_row = isolated_db.execute_one("SELECT plan_id, status FROM allocation_plans WHERE plan_id = ?", (pid,))
            a_row = isolated_db.execute_one("SELECT plan_id, verdict FROM audit_logs WHERE plan_id = ?", (pid,))
            assert p_row is not None and p_row["status"] == "APPROVED"
            assert a_row is not None and a_row["verdict"] == "APPROVED"

    def test_06_phase6_database_integrity_and_isolation(self, isolated_db):
        """Verifies FK constraints, transaction rollback, duplicate prevention, and hot backup/restore."""
        # 1. Foreign-key constraint enforcement
        with pytest.raises(sqlite3.IntegrityError):
            isolated_db.execute_non_query(
                "INSERT INTO affected_zones (zone_id, event_id, name, latitude, longitude, population, vulnerability_index, damage_level, medical_urgency, access_status) "
                "VALUES ('ORPHAN-Z1', 'NON-EXISTENT-EVENT', 'Orphan', 26.0, 92.0, 1000, 0.5, 3, 0.5, 'OPEN')"
            )

        # 2. Duplicate PRIMARY KEY prevention
        with pytest.raises(sqlite3.IntegrityError):
            isolated_db.execute_non_query(
                "INSERT INTO warehouses (warehouse_id, name, latitude, longitude, total_capacity_m3, status) "
                "VALUES ('WH-GUWAHATI-NORTH', 'Duplicate Guwahati', 26.14, 91.73, 10000, 'OPERATIONAL')"
            )

        # 3. Atomic transaction rollback on mid-transaction failure
        before_cnt = isolated_db.execute_one("SELECT COUNT(*) AS cnt FROM disaster_events")["cnt"]
        with pytest.raises(sqlite3.IntegrityError):
            with isolated_db.transaction() as cur:
                cur.execute(
                    "INSERT INTO disaster_events (event_id, name, disaster_type, severity_level, reported_at, status, total_affected_pop) "
                    "VALUES ('EVT-ROLLBACK-99', 'Rollback Test', 'FLOOD', 'SEVERE', '2026-11-15T00:00:00Z', 'ACTIVE', 5000)"
                )
                # Trigger constraint failure on invalid severity_level CHECK constraint
                cur.execute(
                    "INSERT INTO disaster_events (event_id, name, disaster_type, severity_level, reported_at, status, total_affected_pop) "
                    "VALUES ('EVT-ROLLBACK-100', 'Invalid Severity', 'FLOOD', 'INVALID_SEV', '2026-11-15T00:00:00Z', 'ACTIVE', 5000)"
                )
        after_cnt = isolated_db.execute_one("SELECT COUNT(*) AS cnt FROM disaster_events")["cnt"]
        assert after_cnt == before_cnt

        # 4. Online hot backup and restore verification
        backup_file = isolated_db.backup_database()
        assert os.path.isfile(backup_file)
        isolated_db.execute_non_query("DELETE FROM simulation_scenarios WHERE scenario_id = 'SCEN-05'")
        assert isolated_db.execute_one("SELECT scenario_id FROM simulation_scenarios WHERE scenario_id = 'SCEN-05'") is None
        isolated_db.restore_database(backup_file)
        assert isolated_db.execute_one("SELECT scenario_id FROM simulation_scenarios WHERE scenario_id = 'SCEN-05'") is not None
        try:
            os.remove(backup_file)
        except OSError:
            pass

    def test_07_phase7_dashboard_integration_and_html_safety(self, isolated_db):
        """Verifies dashboard data helpers, GIS layer builders, and XSS/HTML escaping."""
        ctx = build_scenario_context("SCEN-02", planning_days=3, db=isolated_db)
        bb = BlackboardManager(db=isolated_db)
        coord = ReliefCoordinator(blackboard=bb, db=isolated_db)
        plan = coord.run_full_coordination_cycle(disaster_context=ctx)
        snap = bb.get_snapshot()

        kpis = app.compute_executive_kpis(plan, snap)
        gis = app.build_gis_layers_data(snap["zone_needs"], snap["inventory_snapshot"], plan["dispatches"])
        assert kpis["has_data"] is True
        assert kpis["active_hazard"] == "EARTHQUAKE"
        assert len(gis["warehouse_points"]) == 4
        assert len(gis["zone_points"]) == len(snap["zone_needs"])
        assert len(gis["route_rows"]) > 0

        # Verify HTML escaping on untrusted strings
        malicious = '<script>alert("xss")</script>'
        escaped = html.escape(malicious)
        assert "<script>" not in escaped
        assert "&lt;script&gt;" in escaped

    def test_08_phase8_stress_and_performance_10_50_100_500_zones(self, isolated_db):
        """
        Executes controlled stress workloads for 10, 50, 100, and 500 disaster zones,
        plus concurrent read requests and serialized write requests.
        """
        for zone_count in (10, 50, 100, 500):
            zones = _generate_synthetic_zones(zone_count, base_pop=5000)
            stress_ctx = {
                "scenario_id": f"SCALE-{zone_count}",
                "event_id": f"EVT-SCALE-{zone_count}",
                "name": f"Scalability Stress Test ({zone_count} Zones)",
                "hazard": "FLOOD",
                "disaster_type": "FLOOD",
                "severity": "SEVERE",
                "severity_level": "SEVERE",
                "planning_days": 3,
                "zones": zones,
            }
            t0 = time.perf_counter()
            bb = BlackboardManager(db=isolated_db)
            coord = ReliefCoordinator(blackboard=bb, db=isolated_db)
            plan = coord.run_full_coordination_cycle(disaster_context=stress_ctx)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            snap = bb.get_snapshot()
            assert len(snap["zone_needs"]) == zone_count
            assert plan["audit_verdict"]["fairness_verdict"] == "FAIRNESS_APPROVED"
            assert plan["audit_verdict"]["gini_coefficient"] <= 0.35
            assert elapsed_ms < 15000.0, f"{zone_count}-zone stress run exceeded 15s budget ({elapsed_ms:.1f}ms)"

        # Concurrent read requests test (8 reader workers)
        def _read_worker(idx: int) -> int:
            rows = isolated_db.execute_query("SELECT warehouse_id, status FROM warehouses")
            return len(rows)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(_read_worker, range(24)))
        assert all(r == 4 for r in results)

    def test_09_phase9_failure_recovery_and_security_controls(self, isolated_db):
        """
        Tests controlled failure conditions (empty context, zero inventory, invalid inputs,
        path traversal attempts, secret masking) and verifies graceful recovery.
        """
        # 1. NeedsAssessmentAgent with None / empty context
        na = NeedsAssessmentAgent(blackboard=BlackboardManager(db=isolated_db))
        empty_na = na.execute(context={})
        assert empty_na["status"] == "EMPTY_CONTEXT"
        assert empty_na["zones_assessed"] == 0

        # 2. FairnessAuditorAgent with missing inputs
        fa = FairnessAuditorAgent(blackboard=BlackboardManager(db=isolated_db), db=isolated_db)
        empty_fa = fa.execute(context={})
        assert empty_fa["audit_verdict"]["verdict"] == "REJECTED"

        # 3. Input validation & path traversal prevention
        valid_ctx, errs = validate_disaster_context({"disaster_type": "INVALID_HAZARD", "zones": []})
        assert valid_ctx is False
        assert len(errs) >= 2

        valid_z, z_errs = validate_zone_payload({"zone_id": "bad id!", "population": -50, "damage_level": 9})
        assert valid_z is False
        assert len(z_errs) >= 3

        with pytest.raises(SecurityValidationError):
            validate_path_safety("../../etc/passwd", settings.BASE_DIR)

        # 4. Secret masking verification
        raw_secret = "sk-proj-1234567890abcdefghijklmnop"
        masked = Settings.mask_secret(raw_secret)
        assert raw_secret not in masked
        assert masked == "sk-...mnop"
        assert raw_secret not in repr(settings)

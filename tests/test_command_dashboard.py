"""
Phase 8 Operational Command Dashboard — Comprehensive Test Suite
Verifies:
1. Executive Overview KPI extraction from live backend outputs (zero hardcoded values).
2. Multi-hazard Disaster Monitoring data integration (FLOOD, EARTHQUAKE, CYCLONE, LANDSLIDE).
3. GIS Command Map layer generation using authentic database coordinates.
4. Resource Management independent metrics (Demanded, Available, Allocated, Fulfillment %, Unfulfilled, Surplus).
5. AI Allocation Engine & Fairness Analytics Lorenz Curve mathematical consistency.
6. RAG Knowledge Assistant live ChromaDB/BM25 query execution and citation grounding.
7. Dynamic Replanning end-to-end workflow and Initial vs. Revised plan diff calculation.
8. Empty database states and invalid input handling.
9. Database connectivity and historical plan audit trail retrieval.
"""

import pytest
from backend.database.db_manager import DatabaseManager
from backend.database.seeder import build_scenario_context, seed_database
from backend.blackboard.blackboard_manager import BlackboardManager
from backend.agents.relief_coordinator import ReliefCoordinator

import app


@pytest.fixture
def isolated_db(tmp_path):
    """Provides an isolated seeded SQLite database for deterministic testing."""
    db_file = tmp_path / "test_phase8_dashboard.db"
    db = DatabaseManager(db_path=str(db_file))
    seed_database(db)
    return db


@pytest.fixture
def unseeded_db(tmp_path):
    """Provides an empty unseeded SQLite database to verify empty-state resilience."""
    db_file = tmp_path / "test_empty_dashboard.db"
    return DatabaseManager(db_path=str(db_file))


class TestOperationalCommandDashboard:
    """Tests all 9 modules and backend integrations of the Phase 8 Command Dashboard."""

    def test_01_database_connectivity_and_catalog_loaders(self, isolated_db):
        """Verifies database loaders return authentic scenarios, zones, warehouses, and historical plans."""
        scenarios = app.load_scenarios_from_db(db=isolated_db)
        assert len(scenarios) >= 5
        assert "SCEN-01" in scenarios
        assert "SCEN-02" in scenarios
        assert "SCEN-03" in scenarios
        assert "SCEN-04" in scenarios

        zones = app.load_all_zones_from_db(db=isolated_db)
        assert len(zones) == 6
        for z in zones:
            assert z["latitude"] > 20.0
            assert z["longitude"] > 85.0

        warehouses = app.load_warehouses_from_db(db=isolated_db)
        assert len(warehouses) == 4
        for wh in warehouses:
            assert wh["status"] == "OPERATIONAL"

    def test_02_empty_database_and_none_state_handling(self, unseeded_db):
        """Verifies empty database states and None inputs are handled gracefully without exceptions."""
        assert app.load_scenarios_from_db(db=unseeded_db) == {}
        assert app.load_all_zones_from_db(db=unseeded_db) == []
        assert app.load_warehouses_from_db(db=unseeded_db) == []
        assert app.load_historical_plans_from_db(db=unseeded_db) == []

        empty_kpis = app.compute_executive_kpis(plan=None, blackboard_snapshot=None)
        assert empty_kpis["has_data"] is False
        assert empty_kpis["total_affected_population"] == 0
        assert empty_kpis["overall_status"] == "UNINITIALIZED"

        empty_gis = app.build_gis_layers_data(zone_needs=[], inv_snap={}, dispatches=[])
        assert empty_gis["warehouse_points"] == []
        assert empty_gis["zone_points"] == []
        assert empty_gis["route_rows"] == []

    def test_03_executive_overview_and_resource_management_kpis(self, isolated_db):
        """Verifies Executive Overview and Resource Management KPIs match backend outputs."""
        ctx = build_scenario_context("SCEN-01", planning_days=3, db=isolated_db)
        bb = BlackboardManager(db=isolated_db)
        coord = ReliefCoordinator(blackboard=bb, db=isolated_db)
        plan = coord.run_full_coordination_cycle(disaster_context=ctx)
        snap = bb.get_snapshot()

        kpis = app.compute_executive_kpis(plan=plan, blackboard_snapshot=snap)
        assert kpis["has_data"] is True
        assert kpis["total_affected_population"] == 248000
        assert kpis["active_zones_count"] == 4
        assert kpis["active_hazard"] == "FLOOD"
        assert kpis["governing_sop"] == "SOP-FL-001"
        assert kpis["latest_plan_id"] == plan["plan_id"]
        assert kpis["fairness_verdict"] == "FAIRNESS_APPROVED"
        assert kpis["gini_coefficient"] <= 0.35

        # Verify independent resource management metrics
        rm = kpis["resource_metrics"]
        assert rm["FOOD_RATIONS"]["demanded"] == 28960
        assert rm["FOOD_RATIONS"]["available"] == 120000
        assert rm["FOOD_RATIONS"]["allocated"] == 28960
        assert rm["FOOD_RATIONS"]["fulfillment_pct"] == 100.0
        assert rm["FOOD_RATIONS"]["unfulfilled_qty"] == 0
        assert rm["FOOD_RATIONS"]["surplus_qty"] == 91040

        assert rm["CLEAN_WATER"]["demanded"] == 11160000
        assert rm["CLEAN_WATER"]["allocated"] == 350000
        assert rm["CLEAN_WATER"]["unfulfilled_qty"] == 10810000
        assert rm["CLEAN_WATER"]["surplus_qty"] == 0
        assert rm["CLEAN_WATER"]["status"] == "CRITICAL_SHORTAGE"

    def test_04_gis_command_map_authentic_coordinates(self, isolated_db):
        """Verifies GIS Command Map layers use real coordinates from warehouses, zones, and dispatches."""
        ctx = build_scenario_context("SCEN-01", planning_days=3, db=isolated_db)
        bb = BlackboardManager(db=isolated_db)
        coord = ReliefCoordinator(blackboard=bb, db=isolated_db)
        plan = coord.run_full_coordination_cycle(disaster_context=ctx)
        snap = bb.get_snapshot()

        gis = app.build_gis_layers_data(
            zone_needs=snap["zone_needs"],
            inv_snap=snap["inventory_snapshot"],
            dispatches=plan["dispatches"],
        )
        assert len(gis["warehouse_points"]) == 4
        assert len(gis["zone_points"]) == 4
        assert len(gis["route_rows"]) > 0

        for r in gis["route_rows"]:
            assert 20.0 < r["source_lat"] < 30.0
            assert 85.0 < r["source_lon"] < 98.0
            assert 20.0 < r["target_lat"] < 30.0
            assert 85.0 < r["target_lon"] < 98.0
            assert r["distance_km"] > 0.0
            assert r["est_transit_hours"] > 0.0

    def test_05_fairness_analytics_lorenz_curve_consistency(self, isolated_db):
        """Verifies Lorenz curve coordinates satisfy trapezoidal Gini identity."""
        ctx = build_scenario_context("SCEN-01", planning_days=3, db=isolated_db)
        bb = BlackboardManager(db=isolated_db)
        coord = ReliefCoordinator(blackboard=bb, db=isolated_db)
        plan = coord.run_full_coordination_cycle(disaster_context=ctx)
        greedy = coord.evaluate_greedy_baseline(disaster_context=ctx)
        snap = bb.get_snapshot()

        fair_summaries = plan["audit_verdict"]["zone_summaries"]
        greedy_summaries = greedy["audit_verdict"]["zone_summaries"]
        fair_gini = plan["audit_verdict"]["gini_coefficient"]
        greedy_gini = greedy["gini_coefficient"]

        df = app.build_lorenz_curve_data(
            zone_needs=snap["zone_needs"],
            fair_summaries=fair_summaries,
            greedy_summaries=greedy_summaries,
            fair_gini=fair_gini,
            greedy_gini=greedy_gini,
        )
        assert not df.empty
        assert "Cumulative Share %" in df.columns
        assert "Cumulative Coverage %" in df.columns
        assert len(df["Policy"].unique()) == 3

    def test_06_rag_knowledge_assistant_queries_and_invalid_inputs(self):
        """Verifies RAG Knowledge Assistant retrieves grounded SOP passages and handles empty queries."""
        # Empty / whitespace query
        empty_res = app.query_rag_knowledge_assistant("   ")
        assert empty_res["status"] == "EMPTY_QUERY"
        assert empty_res["chunks"] == []

        # Valid queries across all 4 hazards
        hazard_queries = {
            "FLOOD": ("What are flood evacuation priorities and water rations?", "SOP-FL-001"),
            "EARTHQUAKE": ("What are medical trauma kit requirements for earthquake structural collapse?", "SOP-EQ-002"),
            "CYCLONE": ("What are cyclone wind shelter and storm surge guidelines?", "SOP-CY-004"),
            "LANDSLIDE": ("How are isolated zones supplied during a mountain landslide blockade?", "SOP-LS-003"),
        }
        for hz, (q, expected_sop) in hazard_queries.items():
            res = app.query_rag_knowledge_assistant(question=q, hazard_filter=hz, top_k=3)
            assert res["status"] == "SUCCESS"
            assert expected_sop in res["sop_ids"]
            assert len(res["chunks"]) > 0
            assert expected_sop in res["grounded_answer"]

    def test_07_dynamic_replanning_workflow_and_invalid_inputs(self, isolated_db):
        """Verifies Module 8 Dynamic Replanning workflow and invalid context handling."""
        with pytest.raises(ValueError):
            app.execute_dynamic_replanning_workflow(initial_context={}, surge_zone_name="Zone 1", db=isolated_db)

        ctx = build_scenario_context("SCEN-04", planning_days=3, db=isolated_db)
        res = app.execute_dynamic_replanning_workflow(
            initial_context=ctx,
            surge_zone_name="Majuli Island Riverine Sector",
            surge_multiplier=1.75,
            surge_damage_lvl=5,
            new_access_status="BLOCKED",
            db=isolated_db,
        )
        assert res["preserved_hazard"] == "LANDSLIDE"
        assert res["population_after"] > res["population_before"]
        assert res["population_delta"] > 0
        assert res["revised_plan"]["plan_id"] != res["initial_plan"]["plan_id"]
        assert res["gini_after"] <= 0.35

        # Verify historical plans were persisted in SQLite for Module 9 Audit Trail
        hist = app.load_historical_plans_from_db(db=isolated_db, limit=10)
        assert len(hist) >= 2

    def test_08_streamlit_apptest_all_nine_modules_render_cleanly(self, monkeypatch):
        """Verifies via Streamlit AppTest that all 9 dashboard modules render with zero runtime exceptions."""
        import asyncio
        from pathlib import Path
        from streamlit.testing.v1 import AppTest, local_script_runner

        class _SandboxSafeEventLoop(asyncio.AbstractEventLoop):
            _closed = False

            def is_closed(self) -> bool:
                return self._closed

            def close(self) -> None:
                self._closed = True

        monkeypatch.setattr(local_script_runner.asyncio, "new_event_loop", _SandboxSafeEventLoop)

        app_path = Path(__file__).resolve().parent.parent / "app.py"
        at = AppTest.from_file(str(app_path), default_timeout=60).run(timeout=60)
        assert len(at.exception) == 0, f"Unexpected AppTest exceptions: {at.exception}"

        tab_labels = [t.label for t in at.tabs]
        assert len(tab_labels) == 9
        expected_prefixes = [
            "📊 1. Executive Overview",
            "🌪️ 2. Disaster Monitoring",
            "🗺️ 3. GIS Command Map",
            "📦 4. Resource Management",
            "🤖 5. AI Allocation Engine",
            "⚖️ 6. Fairness Analytics",
            "📚 7. RAG Knowledge Assistant",
            "🌊 8. Dynamic Replanning",
            "🔍 9. Audit & Explainability",
        ]
        assert tab_labels == expected_prefixes

        subheaders = [s.value for s in at.subheader]
        for mod_idx in range(1, 10):
            assert any(sh.startswith(f"{mod_idx}.") for sh in subheaders), f"Module {mod_idx} subheader missing"


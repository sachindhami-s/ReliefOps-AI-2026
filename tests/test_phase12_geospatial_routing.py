"""
ReliefOps AI — Phase 12: Real-World Geospatial Routing & Logistics Intelligence Test Suite
Covers:
  1. Valid OSRM ROAD_NETWORK route retrieval (distance, duration, GeoJSON geometry, caching)
  2. Invalid coordinates handling (out-of-range, non-numeric, NaN/Inf)
  3. Routing API timeout -> automatic HAVERSINE_FALLBACK
  4. Service unavailable (URLError, HTTP 503, malformed JSON) -> automatic HAVERSINE_FALLBACK
  5. Explicit HAVERSINE_FALLBACK mode (offline, zero HTTP calls, backward compatibility)
  6. Road status handling (OPEN, DEGRADED, BLOCKED, AIR_ONLY) on top of road-network & fallback routes
  7. Multiple warehouse-to-zone routes (4x4 matrix, caching, route plan sequencing)
  8. Dynamic replanning with changed route conditions (OPEN -> BLOCKED) preserving routing mode & fairness
  9. Streamlit GIS Command Map layer metadata (PathLayer geometry, blocked indicators, routing method)
  10. Configuration & environment variable handling (ROUTING_MODE, OSRM_BASE_URL, ROUTING_TIMEOUT_SECONDS)
"""

import io
import json
import os
import socket
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

import app as reliefops_app
from backend.agents.logistics_agent import LogisticsAgent
from backend.agents.relief_coordinator import ReliefCoordinator
from backend.blackboard.blackboard_manager import BlackboardManager
from backend.config import Settings
from backend.database.db_manager import DatabaseManager
from backend.database.seeder import seed_database
from backend.plugins.logistics_plugin import LogisticsPlugin
from demo_pipeline import build_scenario_context


class _FakeHTTPResponse:
    """Minimal context-manager mock for urllib.request.urlopen responses."""

    def __init__(self, payload_bytes: bytes):
        self._buf = io.BytesIO(payload_bytes)

    def read(self) -> bytes:
        return self._buf.read()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def _make_osrm_payload(distance_m: float = 155220.0, duration_s: float = 7308.0, coords=None) -> bytes:
    if coords is None:
        coords = [
            [91.73, 26.18],
            [92.05, 26.32],
            [92.42, 26.48],
            [92.79, 26.63],
        ]
    return json.dumps(
        {
            "code": "Ok",
            "routes": [
                {
                    "distance": distance_m,
                    "duration": duration_s,
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coords,
                    },
                }
            ],
        }
    ).encode("utf-8")


SAMPLE_WAREHOUSES = [
    {"warehouse_id": "WH-GUWAHATI-NORTH", "name": "Guwahati Central Depot", "latitude": 26.18, "longitude": 91.73},
    {"warehouse_id": "WH-TEZPUR-CENTRAL", "name": "Tezpur Quick-Response Base", "latitude": 26.63, "longitude": 92.79},
    {"warehouse_id": "WH-JORHAT-EAST", "name": "Jorhat Forward Hub", "latitude": 26.75, "longitude": 94.22},
    {"warehouse_id": "WH-SILIGURI-WEST", "name": "Siliguri Depot", "latitude": 26.72, "longitude": 88.42},
]

SAMPLE_ZONES = [
    {"zone_id": "ZONE-KAZIRANGA-RURAL", "name": "Kaziranga Rural Belt", "latitude": 26.58, "longitude": 93.17, "access_status": "OPEN"},
    {"zone_id": "ZONE-MAJULI-ISLAND", "name": "Majuli Island Sector", "latitude": 26.96, "longitude": 94.22, "access_status": "DEGRADED"},
    {"zone_id": "ZONE-DHEMAJI-PERIPHERY", "name": "Dhemaji Submerged Sector", "latitude": 27.48, "longitude": 94.58, "access_status": "BLOCKED"},
    {"zone_id": "ZONE-NAGAON-CENTRAL", "name": "Nagaon Plains Area", "latitude": 26.35, "longitude": 92.68, "access_status": "OPEN"},
]


class TestPhase12GeospatialRouting(unittest.TestCase):
    """Comprehensive verification suite for Phase 12 OSRM & Haversine Fallback routing."""

    def test_01_valid_road_network_route_retrieval_and_caching(self):
        """1. Valid OSRM route returns real road distance, travel time, GeoJSON geometry, and caches repeat calls."""
        calls = []

        def fake_opener(req, timeout=5.0):
            calls.append((req.full_url, timeout))
            return _FakeHTTPResponse(_make_osrm_payload(distance_m=155220.0, duration_s=7308.0))

        plugin = LogisticsPlugin(
            routing_mode="ROAD_NETWORK",
            osrm_base_url="https://router.project-osrm.org",
            timeout_seconds=4.0,
            http_opener=fake_opener,
        )
        res = json.loads(plugin.calculate_distance_matrix([SAMPLE_WAREHOUSES[0]], [SAMPLE_ZONES[0]]))
        self.assertTrue(res["success"])
        self.assertEqual(res["active_routing_method"], "ROAD_NETWORK")
        self.assertFalse(res["fallback_used"])
        self.assertEqual(len(calls), 1)
        # Verify OSRM lon,lat coordinate order
        self.assertIn("/route/v1/driving/91.730000,26.180000;93.170000,26.580000", calls[0][0])

        row = res["matrix"][0]
        self.assertEqual(row["routing_method"], "ROAD_NETWORK")
        self.assertFalse(row["fallback_used"])
        self.assertIsNone(row["fallback_reason"])
        self.assertEqual(row["road_distance_km"], 155.22)
        self.assertEqual(row["effective_km"], 155.22)
        self.assertNotEqual(row["road_distance_km"], row["haversine_km"])
        self.assertEqual(row["estimated_transit_hours"], 2.03)
        self.assertTrue(row["route_available"])
        self.assertEqual(len(row["route_geometry"]), 4)
        self.assertIn("OSRM", row["routing_source"])

        # Second identical call hits route cache without another HTTP request
        res2 = json.loads(plugin.calculate_distance_matrix([SAMPLE_WAREHOUSES[0]], [SAMPLE_ZONES[0]]))
        self.assertTrue(res2["success"])
        self.assertEqual(len(calls), 1)

    def test_02_invalid_coordinates_handled_gracefully(self):
        """2. Invalid/out-of-range/non-numeric coordinates never crash and mark route unavailable."""
        bad_zones = [
            {"zone_id": "Z-LAT", "name": "Bad Lat", "latitude": 125.0, "longitude": 92.0, "access_status": "OPEN"},
            {"zone_id": "Z-LON", "name": "Bad Lon", "latitude": 26.5, "longitude": -210.0, "access_status": "OPEN"},
            {"zone_id": "Z-NAN", "name": "NaN Coord", "latitude": float("nan"), "longitude": 92.0, "access_status": "OPEN"},
            {"zone_id": "Z-STR", "name": "Bad String", "latitude": "invalid", "longitude": 92.0, "access_status": "OPEN"},
        ]
        plugin = LogisticsPlugin(routing_mode="ROAD_NETWORK")
        res = json.loads(plugin.calculate_distance_matrix([SAMPLE_WAREHOUSES[0]], bad_zones))
        self.assertTrue(res["success"])
        self.assertEqual(res["total_connections"], 4)
        self.assertEqual(res["routing_summary"]["invalid_routes"], 4)
        for row in res["matrix"]:
            self.assertEqual(row["routing_method"], "INVALID_COORDINATES")
            self.assertFalse(row["route_available"])
            self.assertTrue(row["fallback_used"])
            self.assertIn("invalid_coordinates", row["fallback_reason"])
            self.assertEqual(row["route_geometry"], [])

    def test_03_routing_api_timeout_falls_back_to_haversine(self):
        """3. Socket/HTTP timeout triggers transparent HAVERSINE_FALLBACK with fallback_reason='timeout'."""

        def timeout_opener(req, timeout=5.0):
            raise socket.timeout("timed out")

        plugin = LogisticsPlugin(routing_mode="ROAD_NETWORK", timeout_seconds=1.0, http_opener=timeout_opener)
        res = json.loads(plugin.calculate_distance_matrix([SAMPLE_WAREHOUSES[0]], [SAMPLE_ZONES[0]]))
        self.assertTrue(res["success"])
        self.assertTrue(res["fallback_used"])
        self.assertEqual(res["active_routing_method"], "HAVERSINE_FALLBACK")

        row = res["matrix"][0]
        self.assertEqual(row["routing_method"], "HAVERSINE_FALLBACK")
        self.assertTrue(row["fallback_used"])
        self.assertEqual(row["fallback_reason"], "timeout")
        self.assertGreater(row["effective_km"], 0.0)
        self.assertEqual(len(row["route_geometry"]), 2)

    def test_04_service_unavailable_and_http_errors_fall_back(self):
        """4. URLError, HTTP 503, and malformed JSON gracefully degrade to HAVERSINE_FALLBACK."""

        def url_err_opener(req, timeout=5.0):
            raise urllib.error.URLError("Connection refused")

        p1 = LogisticsPlugin(routing_mode="ROAD_NETWORK", http_opener=url_err_opener)
        r1 = json.loads(p1.calculate_distance_matrix([SAMPLE_WAREHOUSES[0]], [SAMPLE_ZONES[0]]))
        self.assertTrue(r1["matrix"][0]["fallback_used"])
        self.assertEqual(r1["matrix"][0]["fallback_reason"], "service_unavailable")

        def http_503_opener(req, timeout=5.0):
            raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {}, None)

        p2 = LogisticsPlugin(routing_mode="ROAD_NETWORK", http_opener=http_503_opener)
        r2 = json.loads(p2.calculate_distance_matrix([SAMPLE_WAREHOUSES[0]], [SAMPLE_ZONES[0]]))
        self.assertTrue(r2["matrix"][0]["fallback_used"])
        self.assertEqual(r2["matrix"][0]["fallback_reason"], "http_error_503")

        def bad_json_opener(req, timeout=5.0):
            return _FakeHTTPResponse(b"{not-valid-json")

        p3 = LogisticsPlugin(routing_mode="ROAD_NETWORK", http_opener=bad_json_opener)
        r3 = json.loads(p3.calculate_distance_matrix([SAMPLE_WAREHOUSES[0]], [SAMPLE_ZONES[0]]))
        self.assertTrue(r3["matrix"][0]["fallback_used"])
        self.assertEqual(r3["matrix"][0]["fallback_reason"], "invalid_response")

    def test_05_haversine_fallback_mode_makes_zero_http_calls(self):
        """5. Explicit HAVERSINE_FALLBACK mode runs 100% offline with Wt=1.35 and zero HTTP calls."""

        def fail_if_called(req, timeout=5.0):
            raise AssertionError("HTTP opener must NOT be called in HAVERSINE_FALLBACK mode!")

        plugin = LogisticsPlugin(routing_mode="HAVERSINE_FALLBACK", http_opener=fail_if_called)
        res = json.loads(plugin.calculate_distance_matrix([SAMPLE_WAREHOUSES[0]], [SAMPLE_ZONES[0]]))
        self.assertTrue(res["success"])
        self.assertFalse(res["fallback_used"])
        self.assertEqual(res["active_routing_method"], "HAVERSINE_FALLBACK")
        row = res["matrix"][0]
        self.assertEqual(row["routing_method"], "HAVERSINE_FALLBACK")
        expected_eff = round(plugin._haversine_km(26.18, 91.73, 26.58, 93.17) * 1.35, 2)
        self.assertEqual(row["effective_km"], expected_eff)
        self.assertFalse(row["fallback_used"])

    def test_06_road_status_open_degraded_blocked_and_air_only(self):
        """6. Preserves OPEN, DEGRADED (2x duration), BLOCKED (unavailable + aerial flag), and AIR_ONLY."""

        def fake_opener(req, timeout=5.0):
            return _FakeHTTPResponse(_make_osrm_payload(distance_m=100000.0, duration_s=7200.0))  # 100 km, 2.0 hrs

        zones = [
            {"zone_id": "Z-OPEN", "name": "Open", "latitude": 26.50, "longitude": 92.50, "access_status": "OPEN"},
            {"zone_id": "Z-DEG", "name": "Degraded", "latitude": 26.60, "longitude": 92.60, "access_status": "DEGRADED"},
            {"zone_id": "Z-BLK", "name": "Blocked", "latitude": 26.70, "longitude": 92.70, "access_status": "BLOCKED"},
            {"zone_id": "Z-AIR", "name": "Air Only", "latitude": 26.80, "longitude": 92.80, "access_status": "AIR_ONLY"},
        ]
        plugin = LogisticsPlugin(routing_mode="ROAD_NETWORK", http_opener=fake_opener)
        res = json.loads(plugin.calculate_distance_matrix([SAMPLE_WAREHOUSES[0]], zones))
        by_id = {r["zone_id"]: r for r in res["matrix"]}

        # OPEN: nominal OSRM 2.0 hrs, available
        self.assertTrue(by_id["Z-OPEN"]["route_available"])
        self.assertFalse(by_id["Z-OPEN"]["blocked_indicator"])
        self.assertEqual(by_id["Z-OPEN"]["estimated_transit_hours"], 2.0)

        # DEGRADED: 2.0 / 0.5 = 4.0 hrs, still available
        self.assertTrue(by_id["Z-DEG"]["route_available"])
        self.assertEqual(by_id["Z-DEG"]["estimated_transit_hours"], 4.0)

        # BLOCKED: unavailable, blocked indicator + aerial delivery flag, penalized transit
        self.assertFalse(by_id["Z-BLK"]["route_available"])
        self.assertTrue(by_id["Z-BLK"]["blocked_indicator"])
        self.assertTrue(by_id["Z-BLK"]["aerial_delivery_required"])
        self.assertGreater(by_id["Z-BLK"]["estimated_transit_hours"], 10.0)

        # AIR_ONLY: bypasses road network, available via aerial corridor
        self.assertTrue(by_id["Z-AIR"]["route_available"])
        self.assertTrue(by_id["Z-AIR"]["aerial_delivery_required"])
        self.assertEqual(by_id["Z-AIR"]["routing_method"], "HAVERSINE_FALLBACK")

    def test_07_multiple_warehouse_to_zone_routes_and_route_plan(self):
        """7. Evaluates full 4x4 warehouse-to-zone matrix and generates sequenced route plan with metadata."""

        def fake_opener(req, timeout=5.0):
            return _FakeHTTPResponse(_make_osrm_payload(distance_m=120000.0, duration_s=9000.0))

        plugin = LogisticsPlugin(routing_mode="ROAD_NETWORK", http_opener=fake_opener)
        mat_raw = plugin.calculate_distance_matrix(SAMPLE_WAREHOUSES, SAMPLE_ZONES)
        mat = json.loads(mat_raw)
        self.assertEqual(mat["total_connections"], 16)
        self.assertEqual(mat["routing_summary"]["road_network_routes"], 16)
        self.assertEqual(mat["routing_summary"]["blocked_routes"], 4)  # 4 warehouses x 1 BLOCKED zone

        allocs = [
            {"zone_id": "ZONE-KAZIRANGA-RURAL", "warehouse_id": "WH-TEZPUR-CENTRAL", "resource_type": "FOOD_RATIONS", "allocated_qty": 1000},
            {"zone_id": "ZONE-DHEMAJI-PERIPHERY", "warehouse_id": "WH-JORHAT-EAST", "resource_type": "MEDICAL_KITS", "allocated_qty": 50},
        ]
        plan = json.loads(plugin.generate_route_plan(allocs, mat))
        self.assertTrue(plan["success"])
        self.assertEqual(plan["total_routes"], 2)
        # OPEN zone must be sequenced before BLOCKED zone
        self.assertEqual(plan["routes"][0]["zone_id"], "ZONE-KAZIRANGA-RURAL")
        self.assertEqual(plan["routes"][0]["routing_method"], "ROAD_NETWORK")
        self.assertEqual(len(plan["routes"][0]["route_geometry"]), 4)
        self.assertFalse(plan["routes"][1]["route_available"])

    def test_08_dynamic_replanning_with_changed_route_conditions(self):
        """8. Dynamic replanning preserves ROAD_NETWORK mode and adapts when corridor shifts OPEN -> BLOCKED."""

        def fake_opener(req, timeout=5.0):
            return _FakeHTTPResponse(_make_osrm_payload(distance_m=142500.0, duration_s=8100.0))

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db = DatabaseManager(db_path=os.path.join(tmpdir, "replan_route.db"))
            try:
                seed_database(db)
                bb = BlackboardManager(db=db)
                log_plugin = LogisticsPlugin(routing_mode="ROAD_NETWORK", http_opener=fake_opener)
                rc = ReliefCoordinator(blackboard=bb, db=db, logistics_plugin=log_plugin)

                ctx = build_scenario_context("SCEN-01", planning_days=3, db=db)
                ctx["routing_mode"] = "ROAD_NETWORK"
                init_plan = rc.run_full_coordination_cycle(disaster_context=ctx)
                self.assertEqual(init_plan["routing_summary"]["active_routing_method"], "ROAD_NETWORK")
                self.assertEqual(init_plan["fairness_verdict"], "FAIRNESS_APPROVED")

                # Trigger mid-run road collapse: shift a previously OPEN zone to BLOCKED
                revised_ctx = dict(ctx)
                revised_zones = []
                for z in ctx["zones"]:
                    zc = dict(z)
                    if zc["zone_id"] == "ZONE-KAZIRANGA-RURAL":
                        zc["access_status"] = "BLOCKED"
                        zc["road_status"] = "BLOCKED"
                        zc["damage_level"] = 5
                    revised_zones.append(zc)
                revised_ctx["zones"] = revised_zones

                rev_plan = rc.run_full_coordination_cycle(disaster_context=revised_ctx)
                self.assertNotEqual(init_plan["plan_id"], rev_plan["plan_id"])
                self.assertEqual(rev_plan["routing_summary"]["active_routing_method"], "ROAD_NETWORK")
                self.assertGreater(rev_plan["routing_summary"]["blocked_routes"], init_plan["routing_summary"]["blocked_routes"])
                self.assertEqual(rev_plan["fairness_verdict"], "FAIRNESS_APPROVED")

                # Verify Kaziranga dispatches carry blocked_indicator & ROAD_NETWORK geometry
                kaz_dispatches = [d for d in rev_plan["dispatches"] if d["zone_id"] == "ZONE-KAZIRANGA-RURAL" and d["allocated_qty"] > 0]
                self.assertGreater(len(kaz_dispatches), 0)
                self.assertTrue(kaz_dispatches[0]["blocked_indicator"])
                self.assertFalse(kaz_dispatches[0]["route_available"])
                self.assertEqual(kaz_dispatches[0]["routing_method"], "ROAD_NETWORK")
            finally:
                db.close()

    def test_09_dashboard_gis_layers_expose_routing_method_and_geometry(self):
        """9. Streamlit GIS layer builder exposes PathLayer road geometry, blocked indicator, and routing method."""
        dispatches = [
            {
                "zone_id": "Z1",
                "zone_name": "Kaziranga",
                "warehouse_id": "W1",
                "warehouse_name": "Guwahati",
                "resource_type": "FOOD_RATIONS",
                "allocated_qty": 500,
                "distance_km": 155.22,
                "road_distance_km": 155.22,
                "est_transit_hours": 2.03,
                "road_status": "OPEN",
                "route_available": True,
                "blocked_indicator": False,
                "routing_method": "ROAD_NETWORK",
                "routing_source": "OSRM (https://router.project-osrm.org)",
                "fallback_used": False,
                "route_geometry": [[91.73, 26.18], [92.10, 26.35], [93.17, 26.58]],
                "source_lat": 26.18,
                "source_lon": 91.73,
                "target_lat": 26.58,
                "target_lon": 93.17,
            }
        ]
        gis = reliefops_app.build_gis_layers_data(zone_needs=[], inv_snap={}, dispatches=dispatches)
        self.assertEqual(len(gis["route_rows"]), 1)
        row = gis["route_rows"][0]
        self.assertEqual(row["routing_method"], "ROAD_NETWORK")
        self.assertTrue(row["has_road_geometry"])
        self.assertEqual(len(row["path"]), 3)
        self.assertEqual(row["route_availability_label"], "AVAILABLE")
        self.assertIn("ROAD_NETWORK", row["details"])

    def test_10_settings_and_env_configuration(self):
        """10. Settings parses ROUTING_MODE, OSRM_BASE_URL, and ROUTING_TIMEOUT_SECONDS safely."""
        with patch.dict(
            os.environ,
            {
                "ROUTING_MODE": "ROAD_NETWORK",
                "OSRM_BASE_URL": "http://localhost:5000/",
                "ROUTING_TIMEOUT_SECONDS": "3.5",
            },
            clear=False,
        ):
            cfg = Settings()
            self.assertEqual(cfg.ROUTING_MODE, "ROAD_NETWORK")
            self.assertEqual(cfg.OSRM_BASE_URL, "http://localhost:5000")
            self.assertEqual(cfg.ROUTING_TIMEOUT_SECONDS, 3.5)
            d = cfg.to_dict()
            self.assertEqual(d["ROUTING_MODE"], "ROAD_NETWORK")


if __name__ == "__main__":
    unittest.main()

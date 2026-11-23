# ReliefOps AI — Phase 12 Geospatial Routing Testing & Docker Validation Report

**Project:** ReliefOps AI — Intelligent Disaster Relief Resource Allocation Coordinator  
**Course:** CSE476 — Agentic AI and Intelligent Automation  
**Date:** 2026-11-24  
**Local Full Regression Suite:** **`149 / 149` PASSED (`147.43 s`, `0` failures)**  
**In-Container Verification Suite:** **`24 / 24` PASSED (`61.19 s`, `0` failures)**  
**Live OSRM Verification:** **PASSED (`6 / 6` routes on host; `4 / 4` routes inside Linux Docker container)**

---

## 1. New Phase 12 Test Suite Breakdown (`tests/test_phase12_geospatial_routing.py`)

| Test Case | Requirement Covered | Verification Assertions | Result |
| :--- | :--- | :--- | :---: |
| `test_01_valid_road_network_route_retrieval_and_caching` | Valid OSRM route retrieval & caching | Verifies `lon,lat` URL ordering, `road_distance_km` (`155.22 km`) ≠ `haversine_km`, `estimated_transit_hours` (`2.03 hrs`), 4-point GeoJSON `route_geometry`, `fallback_used == False`, and 2nd identical query served from cache (`1` HTTP call total). | **PASSED** |
| `test_02_invalid_coordinates_handled_gracefully` | Invalid coordinates | Tests out-of-range lat (`125.0`), out-of-range lon (`-210.0`), `NaN`, and non-numeric strings; verifies zero crashes, `routing_method == "INVALID_COORDINATES"`, `route_available == False`, `route_geometry == []`. | **PASSED** |
| `test_03_routing_api_timeout_falls_back_to_haversine` | Routing API timeout | Simulates `socket.timeout`; verifies automatic `HAVERSINE_FALLBACK`, `fallback_used == True`, `fallback_reason == "timeout"`, positive fallback distance & 2-point geometry. | **PASSED** |
| `test_04_service_unavailable_and_http_errors_fall_back` | Service unavailable / HTTP 503 / malformed JSON | Simulates `URLError`, `HTTPError(503)`, and invalid JSON payload; verifies graceful fallback with exact `fallback_reason` (`service_unavailable`, `http_error_503`, `invalid_response`). | **PASSED** |
| `test_05_haversine_fallback_mode_makes_zero_http_calls` | Explicit `HAVERSINE_FALLBACK` mode | Injects failing HTTP opener to guarantee zero outbound network calls; verifies `Wt = 1.35` effective distance and `fallback_used == False`. | **PASSED** |
| `test_06_road_status_open_degraded_blocked_and_air_only` | Blocked & degraded road handling | Verifies `OPEN` (`2.0 hrs`, available), `DEGRADED` (`4.0 hrs`, available), `BLOCKED` (`route_available == False`, `blocked_indicator == True`, `aerial_delivery_required == True`), and `AIR_ONLY` (aerial corridor). | **PASSED** |
| `test_07_multiple_warehouse_to_zone_routes_and_route_plan` | Multiple warehouse-to-zone routes | Evaluates full 4×4 matrix (`16` corridors, `4` blocked routes) and verifies `generate_route_plan` sequences `OPEN` before `BLOCKED` while preserving `route_geometry` and `routing_method`. | **PASSED** |
| `test_08_dynamic_replanning_with_changed_route_conditions` | Dynamic replanning on route change | Runs full `ReliefCoordinator` cycle in `ROAD_NETWORK` mode, shifts `ZONE-KAZIRANGA-RURAL` from `OPEN` to `BLOCKED`, re-runs coordination, and verifies `ROAD_NETWORK` preservation, increased `blocked_routes`, `blocked_indicator == True`, and `FAIRNESS_APPROVED`. | **PASSED** |
| `test_09_dashboard_gis_layers_expose_routing_method_and_geometry` | Dashboard GIS layer integration | Verifies `app.build_gis_layers_data` exposes `path`, `has_road_geometry == True`, `routing_method`, `route_availability_label`, and `ROAD_NETWORK` tooltip details. | **PASSED** |
| `test_10_settings_and_env_configuration` | Environment configuration | Verifies `Settings` reads `ROUTING_MODE`, `OSRM_BASE_URL`, and `ROUTING_TIMEOUT_SECONDS` cleanly. | **PASSED** |

---

## 2. Full Regression & Container Verification Matrix

| Execution Environment | Test Command | Result | Duration |
| :--- | :--- | :---: | :---: |
| **Local Host (Windows 11, Python 3.12.1)** | `.\.venv\Scripts\python.exe -m compileall -q backend app.py tests/test_phase12_geospatial_routing.py` | **PASSED (`exit code 0`)** | `< 2 s` |
| **Local Host (Windows 11, Python 3.12.1)** | `.\.venv\Scripts\python.exe -m pytest -q tests` | **`149 passed, 0 failed`** | `147.43 s` |
| **Local Host — Live OSRM Probe** | `LogisticsPlugin(routing_mode='ROAD_NETWORK')` on 6 real DB warehouse-zone pairs | **`6 / 6 ROAD_NETWORK`** (`fallback_used=False`) | `< 6 s` |
| **Docker Image Build (`reliefops-ai:phase12`)** | `docker build -t reliefops-ai:phase12 -t reliefops-ai:latest .` | **PASSED (`exit code 0`)** | `~4 min` |
| **Docker Compose Non-Destructive Recreate** | `docker compose up -d --build` | **PASSED (`Up (healthy)`, `HTTP 200` on `/_stcore/health`)** | `< 20 s` |
| **Inside Container — Live OSRM Probe** | `docker exec reliefops-ai-service python -c "...LogisticsPlugin(routing_mode='ROAD_NETWORK')..."` | **`4 / 4 ROAD_NETWORK`** (`fallback_used=False`, 19–62 waypoints) | `< 5 s` |
| **Inside Container — Phase 12 + Dashboard + Phase 10 Pytest** | `docker exec reliefops-ai-service pytest -q tests/test_phase12_geospatial_routing.py tests/test_command_dashboard.py tests/test_phase10_deployment_dockerization.py` | **`24 passed, 0 failed`** | `61.19 s` |

---

## 3. Non-Destructive Storage Preservation Confirmed (Task 8)

During the Phase 12 Docker image rebuild and container recreation (`docker compose up -d --build`, no destructive volume flags used):
- Entrypoint confirmed:
  - `[ENTRYPOINT] Existing SQLite database detected at '/app/data/reliefops.db' (7278592 bytes). Preserving untouched without reseeding.`
  - `[ENTRYPOINT] Existing ChromaDB collection 'disaster_sops' detected (64 indexed chunks at '/app/data/chromadb'). Preserving untouched.`
- Container healthcheck verified: `reliefops-ai-service | Up (healthy)` with `ok | HTTP=200` on `http://localhost:8501/_stcore/health`.

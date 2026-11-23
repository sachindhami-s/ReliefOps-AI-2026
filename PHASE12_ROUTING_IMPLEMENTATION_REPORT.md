# ReliefOps AI — Phase 12: Real-World Geospatial Routing & Logistics Intelligence Implementation Report

**Project:** ReliefOps AI — Intelligent Disaster Relief Resource Allocation Coordinator  
**Course:** CSE476 — Agentic AI and Intelligent Automation  
**Repository:** `https://github.com/sachindhami-s/ReliefOps-AI-2026`  
**Date:** 2026-11-24  
**Status:** **COMPLETE & VERIFIED (LOCAL PYTHON + LIVE OSRM + DOCKER CONTAINER)**

---

## 1. Task 1 — Pre-Modification Project Audit (Baseline Routing Architecture)

Before modifying the routing subsystem, the existing geospatial implementation was audited across all layers:

| Layer / File | Pre-Phase 12 Baseline Implementation | Identified Gaps Addressed in Phase 12 |
| :--- | :--- | :--- |
| **`backend/plugins/logistics_plugin.py`** | Computed great-circle Haversine distance scaled by a fixed terrain winding factor (`WINDING_FACTOR = 1.35`), ground speed (`45 km/h`), air speed (`90 km/h`), and multipliers (`OPEN: 1.0`, `DEGRADED: 0.5`, `BLOCKED: 0.15`, `AIR_ONLY: 1.0`). | No road-network routing, no GeoJSON route polyline geometry, no coordinate bounds validation, no configurable routing mode or fallback metadata. |
| **`backend/agents/logistics_agent.py`** | Read `zone_needs` and `inventory_snapshot` from Blackboard and invoked `calculate_distance_matrix(warehouses, zones)`. | Did not pass configurable `routing_mode` or `osrm_base_url` from scenario/Blackboard context or log routing mode / fallback counts. |
| **`backend/plugins/coordinator_plugin.py`** & **`relief_coordinator.py`** | Passed `distance_km`, `est_transit_hours`, `road_status`, and endpoint `source_lat/lon`, `target_lat/lon` onto `dispatches`. | Did not carry road geometry, `road_distance_km`, `route_available`, `blocked_indicator`, `routing_method`, or `fallback_used` into dispatches or plan summaries. |
| **`app.py` (Module 3 — GIS Command Map)** | Rendered PyDeck `ScatterplotLayer` (warehouses/zones) and straight `LineLayer`/`ArcLayer` corridors. | No PyDeck `PathLayer` road geometry rendering, no routing mode selector, no blocked-route alert ring, and no routing method/source transparency in corridor tables. |
| **`backend/config.py`, `.env.example`, `Dockerfile`, `docker-compose.yml`** | Managed DB, ChromaDB, SOP, Gini, and survival floor variables. | Lacked `ROUTING_MODE`, `OSRM_BASE_URL`, and `ROUTING_TIMEOUT_SECONDS`. |

---

## 2. Tasks 2–4 — OpenStreetMap / OSRM Integration, Road-Status Preservation & Backward Compatibility

### 2.1 Configurable Routing Modes (`backend/config.py`, `.env.example`, `Dockerfile`, `docker-compose.yml`)
Added three optional environment variables with safe offline-first defaults:
- **`ROUTING_MODE`**: `HAVERSINE_FALLBACK` (default, 100% offline deterministic) or `ROAD_NETWORK` (OpenStreetMap/OSRM with automatic graceful fallback).
- **`OSRM_BASE_URL`**: `https://router.project-osrm.org` (supports self-hosted or public OSRM v1 instances).
- **`ROUTING_TIMEOUT_SECONDS`**: `5.0` (prevents hung requests when external endpoints are unreachable).

### 2.2 OSRM Client & Extended `LogisticsPlugin` (`backend/plugins/logistics_plugin.py`)
- **Zero New Pip Dependencies:** Implemented via Python stdlib `urllib.request`, `socket`, and `json`, preserving lean Docker images and fast builds.
- **OSRM v1 Query Format:** `{OSRM_BASE_URL}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=simplified&geometries=geojson` (strictly honoring OSRM `longitude,latitude` order) with a thread-safe in-memory route cache.
- **Coordinate Validation:** Rejects non-numeric, non-finite (`NaN`/`Inf`), or out-of-range coordinates (`lat ∉ [-90, 90]`, `lon ∉ [-180, 180]`) without crashing, marking `route_available = False` and `routing_method = "INVALID_COORDINATES"`.
- **Automatic Graceful Fallback:** On `socket.timeout` / `TimeoutError` (`timeout`), `urllib.error.URLError` (`service_unavailable`), `HTTPError` (`http_error_<code>`), malformed JSON (`invalid_response`), or missing OSRM routes (`no_route_found`), `LogisticsPlugin` seamlessly falls back to `HAVERSINE_FALLBACK` (`Wt = 1.35`) and records `fallback_used = True`, `fallback_reason`, and `routing_source`.
- **Preserved Road-Status Semantics (Honest Field vs. OSM Distinction):**
  - `OPEN`: `route_available = True`, `1.0×` OSRM nominal duration (or `45 km/h` Haversine).
  - `DEGRADED`: `route_available = True`, `2.0×` OSRM nominal duration (`duration / 0.5`; `22.5 km/h` Haversine).
  - `BLOCKED`: `route_available = False`, `blocked_indicator = True`, `aerial_delivery_required = True`, heavily penalized ground transit (`duration / 0.15`).
  - `AIR_ONLY`: Direct aerial corridor (`90 km/h`, `route_available = True`, `aerial_delivery_required = True`), bypassing road network.
- **Extended Blackboard & Dispatch Metadata:** Every corridor and dispatch now carries `road_distance_km`, `estimated_duration_minutes`, `route_available`, `blocked_indicator`, `aerial_delivery_required`, `route_geometry`, `routing_mode_requested`, `routing_method`, `fallback_used`, `fallback_reason`, and `routing_source`, while preserving every legacy field (`haversine_km`, `effective_km`, `estimated_transit_hours`, `road_status`).
- **Allocation, Fairness & Replanning Preserved:** Two-Phase Water-Filling (`30%` scaled survival floor + ZPS residual), Gini $\le 0.35$ auditing, and dynamic replanning (`routing_mode` preserved across mid-run surges) continue to operate seamlessly.

---

## 3. Task 5 — Streamlit GIS Command Map Upgrade (`app.py`)

- **Sidebar Controls:** Added a **Logistics Routing Engine** selector (`HAVERSINE_FALLBACK` vs. `ROAD_NETWORK`) and configurable **OSRM Routing Service URL** input when `ROAD_NETWORK` is selected.
- **Module 3 — Spatial GIS Command Map:**
  - Added a 4-card **Routing Telemetry Strip** showing Requested Routing Mode, Active Routing Method, Road-Network vs. Fallback route counts, and Blocked Corridor count.
  - Added PyDeck **`PathLayer`** rendering actual multi-point OSRM GeoJSON polylines (`route_geometry`) when `ROAD_NETWORK` routes are retrieved, retaining `LineLayer` + `ArcLayer` for `HAVERSINE_FALLBACK` corridors.
  - Added high-visibility red outer alert rings (`ScatterplotLayer`) around destinations with `BLOCKED` corridors.
  - Upgraded the **Active Logistics Dispatch Corridors** table to display `Road Condition`, `Route Availability`, `Distance (km)`, `Est. Travel Time (hrs)`, `Routing Method`, `Routing Source`, `Fallback Used`, and `Dispatched Cargo Manifest`.
  - Added an explicit operational disclaimer stating that OpenStreetMap/OSRM provides baseline road geometry and nominal travel times, not verified live disaster road closures.

---

## 4. Verified Live OSRM Road-Network Results (Host & Inside Docker)

Actual live HTTP requests to `https://router.project-osrm.org` were executed against authentic Assam warehouse and zone coordinates from `data/reliefops.db` on both the local Windows host (`6/6` routes) and inside the running Linux Docker container (`4/4` routes):

| Corridor (Warehouse → Zone) | Road Status | Straight Haversine (km) | Verified OSRM Road Distance (km) | Adjusted ETA (hrs) | GeoJSON Waypoints | Routing Method |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `WH-GUWAHATI-NORTH` → `ZONE-MAJULI-ISLAND` | `DEGRADED` | `262.38` | **`340.46`** | `10.86` | `62` | `ROAD_NETWORK` |
| `WH-GUWAHATI-NORTH` → `ZONE-KAZIRANGA-RURAL` | `OPEN` | `150.18` | **`192.10`** | `2.34` | `39` | `ROAD_NETWORK` |
| `WH-GUWAHATI-NORTH` → `ZONE-DIBRUGARH-URBAN` | `OPEN` | `346.60` | **`441.34`** | `5.31` | `46` | `ROAD_NETWORK` |
| `WH-JORHAT-EAST` → `ZONE-MAJULI-ISLAND` | `DEGRADED` | `23.35` | **`36.59`** | `3.61` | `19` | `ROAD_NETWORK` |
| `WH-JORHAT-EAST` → `ZONE-KAZIRANGA-RURAL` | `OPEN` | `106.04` | **`113.59`** | `1.35` | `26` | `ROAD_NETWORK` |
| `WH-JORHAT-EAST` → `ZONE-DIBRUGARH-URBAN` | `OPEN` | `105.23` | **`136.95`** | `1.68` | `35` | `ROAD_NETWORK` |

---

## 5. Honest Limitations & Operational Boundaries

1. **No Live Disaster Road Closures from OSM:** Public OpenStreetMap/OSRM servers compute nominal driving routes on static map graphs; they do **not** report real-time flood inundations, bridge washouts, or landslide blockages. `OPEN`, `DEGRADED`, and `BLOCKED` flags remain operator/scenario inputs applied on top of OSRM duration estimates.
2. **Public OSRM Demo Server Rate Limits:** `https://router.project-osrm.org` is a public demo server unsuitable for high-frequency production dispatch; production deployments should point `OSRM_BASE_URL` to a self-hosted OSRM instance.
3. **Synthetic Academic Disaster Data:** Warehouse inventories, zone populations, and disaster events remain synthetic CSE476 evaluation models.

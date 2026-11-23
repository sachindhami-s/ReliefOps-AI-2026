"""
ReliefOps AI — Logistics and Transport Routing Plugin (Phase 12 Upgraded)
Provides Semantic Kernel plugin functions for:
  - Optional real-world OpenStreetMap/OSRM road-network routing (geometry, road distance, duration)
  - Deterministic Haversine great-circle fallback (winding factor Wt = 1.35)
  - Road impedance modeling for scenario/field-reported OPEN, DEGRADED, BLOCKED, and AIR_ONLY corridors
  - Route availability flags, fallback transparency metadata, and prioritized route planning

Academic & Geospatial Disclaimer:
OpenStreetMap/OSRM supplies baseline road-network geometry and nominal free-flow travel times.
It does NOT automatically provide verified live disaster road closures; OPEN/DEGRADED/BLOCKED
statuses reflect scenario or operator-reported field conditions.
"""

import json
import logging
import math
import os
import socket
import threading
import urllib.error
import urllib.request
from typing import Annotated, Any, Callable, Dict, List, Optional, Tuple
from semantic_kernel.functions import kernel_function

logger = logging.getLogger("reliefops.logistics")


class LogisticsPlugin:
    """Semantic Kernel plugin for humanitarian logistics and geospatial transport routing."""

    ROUTING_MODE_ROAD_NETWORK: str = "ROAD_NETWORK"
    ROUTING_MODE_HAVERSINE: str = "HAVERSINE_FALLBACK"
    VALID_ROUTING_MODES = {ROUTING_MODE_ROAD_NETWORK, ROUTING_MODE_HAVERSINE}

    DEFAULT_OSRM_BASE_URL: str = "https://router.project-osrm.org"
    DEFAULT_TIMEOUT_SECONDS: float = 5.0

    WINDING_FACTOR: float = 1.35
    BASE_SPEED_GROUND: float = 45.0  # km/h
    BASE_SPEED_AIR: float = 90.0     # km/h

    ETA_MULTIPLIERS: Dict[str, float] = {
        "OPEN": 1.0,
        "DEGRADED": 0.5,
        "BLOCKED": 0.15,
        "AIR_ONLY": 1.0,
    }

    def __init__(
        self,
        routing_mode: Optional[str] = None,
        osrm_base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        http_opener: Optional[Callable[..., Any]] = None,
    ) -> None:
        raw_mode = (routing_mode or os.getenv("ROUTING_MODE", self.ROUTING_MODE_HAVERSINE)).strip().upper()
        self.routing_mode: str = (
            raw_mode if raw_mode in self.VALID_ROUTING_MODES else self.ROUTING_MODE_HAVERSINE
        )
        self.osrm_base_url: str = (
            (osrm_base_url or os.getenv("OSRM_BASE_URL", self.DEFAULT_OSRM_BASE_URL)).strip().rstrip("/")
        )
        try:
            raw_timeout = (
                timeout_seconds
                if timeout_seconds is not None
                else float(os.getenv("ROUTING_TIMEOUT_SECONDS", str(self.DEFAULT_TIMEOUT_SECONDS)))
            )
            self.timeout_seconds: float = max(0.1, float(raw_timeout))
        except (TypeError, ValueError):
            self.timeout_seconds = self.DEFAULT_TIMEOUT_SECONDS

        # Optional callable matching urllib.request.urlopen(req, timeout=...) for deterministic testing
        self._http_opener = http_opener
        self._route_cache: Dict[Tuple[float, float, float, float, str], Dict[str, Any]] = {}
        self._cache_lock = threading.Lock()

    @staticmethod
    def _validate_coordinates(lat: Any, lon: Any) -> Tuple[bool, Optional[float], Optional[float], Optional[str]]:
        """Validates latitude/longitude bounds and finiteness."""
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            return False, None, None, "non_numeric_coordinates"

        if not (math.isfinite(lat_f) and math.isfinite(lon_f)):
            return False, None, None, "non_finite_coordinates"
        if lat_f < -90.0 or lat_f > 90.0:
            return False, None, None, f"latitude_out_of_range:{lat_f}"
        if lon_f < -180.0 or lon_f > 180.0:
            return False, None, None, f"longitude_out_of_range:{lon_f}"
        return True, lat_f, lon_f, None

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculates great-circle distance in kilometers using the Haversine formula."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        lat1_r = math.radians(lat1)
        lat2_r = math.radians(lat2)
        a = (
            math.sin(dlat / 2.0) ** 2
            + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
        return R * c

    def _transit_hours_for(self, distance_km: float, road_status: str) -> float:
        """Calculates Haversine fallback transit hours based on access status."""
        status = str(road_status).upper().strip()
        if status == "AIR_ONLY":
            base_speed = self.BASE_SPEED_AIR
            eta_mult = 1.0
        else:
            base_speed = self.BASE_SPEED_GROUND
            eta_mult = self.ETA_MULTIPLIERS.get(status, 1.0)

        effective_speed = base_speed * eta_mult
        if effective_speed <= 0:
            return float("inf")
        return distance_km / effective_speed

    def _fetch_osrm_route(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Queries an OpenStreetMap-compatible OSRM v1 routing endpoint for driving route geometry,
        road distance (meters), and nominal free-flow duration (seconds).
        Never raises; returns structured success/error dict for safe fallback handling.
        """
        service_url = (base_url or self.osrm_base_url).strip().rstrip("/")
        timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        cache_key = (round(lat1, 5), round(lon1, 5), round(lat2, 5), round(lon2, 5), service_url)

        with self._cache_lock:
            cached = self._route_cache.get(cache_key)
            if cached is not None:
                return dict(cached)

        if not service_url.startswith(("http://", "https://")):
            return {"ok": False, "reason": "invalid_routing_service_url", "source": service_url}

        # OSRM v1 strictly expects longitude,latitude order
        endpoint = (
            f"{service_url}/route/v1/driving/"
            f"{lon1:.6f},{lat1:.6f};{lon2:.6f},{lat2:.6f}"
            f"?overview=simplified&geometries=geojson"
        )
        req = urllib.request.Request(
            endpoint,
            headers={"User-Agent": "ReliefOps-AI/1.2 (CSE476 Academic Disaster Logistics)"},
        )
        opener = self._http_opener or urllib.request.urlopen

        try:
            with opener(req, timeout=timeout) as resp:
                raw_bytes = resp.read()
                payload = json.loads(raw_bytes.decode("utf-8"))
        except (socket.timeout, TimeoutError):
            logger.warning("OSRM routing request timed out after %.1fs for %s", timeout, endpoint)
            return {"ok": False, "reason": "timeout", "source": service_url}
        except urllib.error.HTTPError as exc:
            logger.warning("OSRM HTTP error %s for %s", exc.code, endpoint)
            return {"ok": False, "reason": f"http_error_{exc.code}", "source": service_url}
        except urllib.error.URLError as exc:
            if isinstance(getattr(exc, "reason", None), (socket.timeout, TimeoutError)):
                return {"ok": False, "reason": "timeout", "source": service_url}
            logger.warning("OSRM service unavailable (%s) for %s", exc.reason, endpoint)
            return {"ok": False, "reason": "service_unavailable", "source": service_url}
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("OSRM routing parse/IO error: %s", exc)
            return {"ok": False, "reason": "invalid_response", "source": service_url}

        if not isinstance(payload, dict) or payload.get("code") != "Ok":
            return {
                "ok": False,
                "reason": f"osrm_status_{payload.get('code', 'unknown') if isinstance(payload, dict) else 'invalid'}",
                "source": service_url,
            }

        routes = payload.get("routes") or []
        if not routes or not isinstance(routes[0], dict):
            return {"ok": False, "reason": "no_route_found", "source": service_url}

        best = routes[0]
        dist_m = best.get("distance")
        dur_s = best.get("duration")
        geom = best.get("geometry") or {}
        coords = geom.get("coordinates") if isinstance(geom, dict) else None

        try:
            road_km = round(max(0.0, float(dist_m) / 1000.0), 2)
            base_dur_hrs = max(0.0, float(dur_s) / 3600.0)
        except (TypeError, ValueError):
            return {"ok": False, "reason": "malformed_route_metrics", "source": service_url}

        valid_geometry: List[List[float]] = []
        if isinstance(coords, list) and len(coords) >= 2:
            for pt in coords:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    try:
                        valid_geometry.append([float(pt[0]), float(pt[1])])
                    except (TypeError, ValueError):
                        continue

        if len(valid_geometry) < 2:
            valid_geometry = [[lon1, lat1], [lon2, lat2]]

        result = {
            "ok": True,
            "road_distance_km": road_km,
            "base_duration_hours": base_dur_hrs,
            "route_geometry": valid_geometry,
            "source": f"OSRM ({service_url})",
        }
        with self._cache_lock:
            self._route_cache[cache_key] = dict(result)
        return result

    def _compute_single_route(
        self,
        wh: Dict[str, Any],
        zone: Dict[str, Any],
        requested_mode: str,
        service_url: str,
    ) -> Dict[str, Any]:
        """Evaluates one warehouse-to-zone corridor with validation, OSRM routing, and safe Haversine fallback."""
        wid = wh.get("warehouse_id", "UNKNOWN_WH")
        w_name = wh.get("name") or wh.get("warehouse_name", wid)
        zid = zone.get("zone_id", "UNKNOWN_ZONE")
        z_name = zone.get("name") or zone.get("zone_name", zid)
        status = str(zone.get("access_status") or zone.get("road_status") or "OPEN").upper().strip()
        if status not in self.ETA_MULTIPLIERS:
            status = "OPEN"

        raw_w_lat = wh.get("latitude") if "latitude" in wh else wh.get("lat")
        raw_w_lon = wh.get("longitude") if "longitude" in wh else wh.get("lon")
        raw_z_lat = zone.get("latitude") if "latitude" in zone else zone.get("lat")
        raw_z_lon = zone.get("longitude") if "longitude" in zone else zone.get("lon")

        w_ok, w_lat, w_lon, w_err = self._validate_coordinates(raw_w_lat, raw_w_lon)
        z_ok, z_lat, z_lon, z_err = self._validate_coordinates(raw_z_lat, raw_z_lon)

        if not (w_ok and z_ok):
            err_reason = f"invalid_coordinates:{w_err or z_err}"
            return {
                "warehouse_id": wid,
                "warehouse_name": w_name,
                "zone_id": zid,
                "zone_name": z_name,
                "haversine_km": 0.0,
                "effective_km": 9999.0,
                "road_distance_km": 9999.0,
                "road_status": status,
                "estimated_transit_hours": 999.0,
                "estimated_duration_minutes": 59940.0,
                "route_available": False,
                "blocked_indicator": status == "BLOCKED",
                "aerial_delivery_required": status in ("BLOCKED", "AIR_ONLY"),
                "route_geometry": [],
                "routing_mode_requested": requested_mode,
                "routing_method": "INVALID_COORDINATES",
                "fallback_used": True,
                "fallback_reason": err_reason,
                "routing_source": "Coordinate Validation Error",
                "source_lat": w_lat,
                "source_lon": w_lon,
                "target_lat": z_lat,
                "target_lon": z_lon,
            }

        hav_km = self._haversine_km(w_lat, w_lon, z_lat, z_lon)
        fallback_eff_km = round(hav_km * self.WINDING_FACTOR, 2)
        fallback_hours = round(self._transit_hours_for(fallback_eff_km, status), 2)
        straight_geom = [[w_lon, w_lat], [z_lon, z_lat]]

        is_blocked = status == "BLOCKED"
        is_air_only = status == "AIR_ONLY"
        route_available = not is_blocked
        aerial_required = is_blocked or is_air_only

        # AIR_ONLY bypasses road network directly (aerial corridor)
        if requested_mode == self.ROUTING_MODE_ROAD_NETWORK and not is_air_only:
            osrm = self._fetch_osrm_route(w_lat, w_lon, z_lat, z_lon, base_url=service_url)
            if osrm.get("ok"):
                road_km = float(osrm["road_distance_km"])
                base_dur_hrs = float(osrm["base_duration_hours"])
                if base_dur_hrs <= 0.0 and road_km > 0.0:
                    base_dur_hrs = road_km / self.BASE_SPEED_GROUND

                # Apply scenario/field-reported road condition multiplier on top of OSRM free-flow time
                eta_mult = self.ETA_MULTIPLIERS.get(status, 1.0)
                adjusted_hours = round(base_dur_hrs / eta_mult, 2) if eta_mult > 0 else fallback_hours

                return {
                    "warehouse_id": wid,
                    "warehouse_name": w_name,
                    "zone_id": zid,
                    "zone_name": z_name,
                    "haversine_km": round(hav_km, 2),
                    "effective_km": road_km,
                    "road_distance_km": road_km,
                    "road_status": status,
                    "estimated_transit_hours": adjusted_hours,
                    "estimated_duration_minutes": round(adjusted_hours * 60.0, 1),
                    "route_available": route_available,
                    "blocked_indicator": is_blocked,
                    "aerial_delivery_required": aerial_required,
                    "route_geometry": osrm["route_geometry"],
                    "routing_mode_requested": requested_mode,
                    "routing_method": self.ROUTING_MODE_ROAD_NETWORK,
                    "fallback_used": False,
                    "fallback_reason": None,
                    "routing_source": osrm["source"],
                    "source_lat": w_lat,
                    "source_lon": w_lon,
                    "target_lat": z_lat,
                    "target_lon": z_lon,
                }

            # Graceful fallback when OSRM fails or times out
            return {
                "warehouse_id": wid,
                "warehouse_name": w_name,
                "zone_id": zid,
                "zone_name": z_name,
                "haversine_km": round(hav_km, 2),
                "effective_km": fallback_eff_km,
                "road_distance_km": fallback_eff_km,
                "road_status": status,
                "estimated_transit_hours": fallback_hours,
                "estimated_duration_minutes": round(fallback_hours * 60.0, 1),
                "route_available": route_available,
                "blocked_indicator": is_blocked,
                "aerial_delivery_required": aerial_required,
                "route_geometry": straight_geom,
                "routing_mode_requested": requested_mode,
                "routing_method": self.ROUTING_MODE_HAVERSINE,
                "fallback_used": True,
                "fallback_reason": osrm.get("reason", "routing_service_error"),
                "routing_source": f"Haversine Fallback (Wt={self.WINDING_FACTOR}; reason={osrm.get('reason', 'error')})",
                "source_lat": w_lat,
                "source_lon": w_lon,
                "target_lat": z_lat,
                "target_lon": z_lon,
            }

        # Standard HAVERSINE_FALLBACK mode (or AIR_ONLY corridor)
        return {
            "warehouse_id": wid,
            "warehouse_name": w_name,
            "zone_id": zid,
            "zone_name": z_name,
            "haversine_km": round(hav_km, 2),
            "effective_km": fallback_eff_km,
            "road_distance_km": fallback_eff_km,
            "road_status": status,
            "estimated_transit_hours": fallback_hours,
            "estimated_duration_minutes": round(fallback_hours * 60.0, 1),
            "route_available": route_available,
            "blocked_indicator": is_blocked,
            "aerial_delivery_required": aerial_required,
            "route_geometry": straight_geom,
            "routing_mode_requested": requested_mode,
            "routing_method": self.ROUTING_MODE_HAVERSINE,
            "fallback_used": is_air_only and requested_mode == self.ROUTING_MODE_ROAD_NETWORK,
            "fallback_reason": "air_only_corridor" if (is_air_only and requested_mode == self.ROUTING_MODE_ROAD_NETWORK) else None,
            "routing_source": (
                "Aerial Great-Circle Corridor (90 km/h)"
                if is_air_only
                else f"Haversine Formula (Wt={self.WINDING_FACTOR})"
            ),
            "source_lat": w_lat,
            "source_lon": w_lon,
            "target_lat": z_lat,
            "target_lon": z_lon,
        }

    @kernel_function(
        name="calculate_distance_matrix",
        description=(
            "Compute warehouse-to-zone distance matrix using either OpenStreetMap/OSRM ROAD_NETWORK routing "
            "or HAVERSINE_FALLBACK with automatic graceful fallback and road-status impedance."
        ),
    )
    def calculate_distance_matrix(
        self,
        warehouses_json: Annotated[Any, "JSON list of warehouses: [{warehouse_id, lat/latitude, lon/longitude, name}]"],
        zones_json: Annotated[Any, "JSON list of zones: [{zone_id, lat/latitude, lon/longitude, name, road_status/access_status}]"],
        routing_mode: Annotated[Optional[str], "Optional routing mode override: ROAD_NETWORK or HAVERSINE_FALLBACK"] = None,
        osrm_base_url: Annotated[Optional[str], "Optional OSRM routing service base URL override"] = None,
    ) -> str:
        """Returns distance matrix with road-network geometry/metrics or Haversine fallback."""
        try:
            warehouses = json.loads(warehouses_json) if isinstance(warehouses_json, str) else warehouses_json
            zones = json.loads(zones_json) if isinstance(zones_json, str) else zones_json

            raw_mode = (routing_mode or self.routing_mode).strip().upper()
            effective_mode = (
                raw_mode if raw_mode in self.VALID_ROUTING_MODES else self.ROUTING_MODE_HAVERSINE
            )
            service_url = (osrm_base_url or self.osrm_base_url).strip().rstrip("/")

            matrix: List[Dict[str, Any]] = []
            road_network_count = 0
            fallback_count = 0
            blocked_count = 0
            invalid_count = 0

            for wh in warehouses or []:
                for zone in zones or []:
                    row = self._compute_single_route(wh, zone, effective_mode, service_url)
                    matrix.append(row)
                    if row["routing_method"] == self.ROUTING_MODE_ROAD_NETWORK:
                        road_network_count += 1
                    elif row["routing_method"] == "INVALID_COORDINATES":
                        invalid_count += 1
                    if row["fallback_used"]:
                        fallback_count += 1
                    if row["blocked_indicator"]:
                        blocked_count += 1

            overall_method = (
                self.ROUTING_MODE_ROAD_NETWORK
                if road_network_count > 0 and fallback_count == 0
                else (
                    "MIXED_ROAD_AND_FALLBACK"
                    if road_network_count > 0 and fallback_count > 0
                    else self.ROUTING_MODE_HAVERSINE
                )
            )

            routing_summary = {
                "routing_mode_requested": effective_mode,
                "active_routing_method": overall_method,
                "routing_service_url": service_url if effective_mode == self.ROUTING_MODE_ROAD_NETWORK else None,
                "total_routes": len(matrix),
                "road_network_routes": road_network_count,
                "haversine_routes": len(matrix) - road_network_count - invalid_count,
                "fallback_routes": fallback_count,
                "blocked_routes": blocked_count,
                "invalid_routes": invalid_count,
                "fallback_used": fallback_count > 0,
            }

            return json.dumps(
                {
                    "success": True,
                    "winding_factor": self.WINDING_FACTOR,
                    "routing_mode_requested": effective_mode,
                    "active_routing_method": overall_method,
                    "fallback_used": fallback_count > 0,
                    "routing_summary": routing_summary,
                    "matrix": matrix,
                    "total_connections": len(matrix),
                }
            )
        except Exception as exc:
            return json.dumps(
                {
                    "success": False,
                    "error": str(exc),
                    "matrix": [],
                    "total_connections": 0,
                    "routing_summary": {"error": str(exc)},
                }
            )

    @kernel_function(
        name="estimate_transit_metrics",
        description="Estimate transit hours and feasibility for a distance and road access status.",
    )
    def estimate_transit_metrics(
        self,
        distance_km: Annotated[float, "Effective road distance in kilometers"],
        road_status: Annotated[str, "Road access status: OPEN | DEGRADED | BLOCKED | AIR_ONLY"],
    ) -> str:
        """Returns speed, transit hours, and a 48-hour feasibility indicator."""
        try:
            dist = float(distance_km)
            status = str(road_status).upper().strip()

            if status == "AIR_ONLY":
                base_speed = self.BASE_SPEED_AIR
                eta_mult = 1.0
            else:
                base_speed = self.BASE_SPEED_GROUND
                eta_mult = self.ETA_MULTIPLIERS.get(status, 1.0)

            effective_speed = base_speed * eta_mult
            transit_hours = dist / effective_speed if effective_speed > 0 else float("inf")

            return json.dumps(
                {
                    "distance_km": round(dist, 2),
                    "road_status": status,
                    "effective_speed_kmh": round(effective_speed, 2),
                    "transit_hours": round(transit_hours, 2),
                    "route_available": status != "BLOCKED",
                    "feasible_48h": transit_hours <= 48.0 and status != "BLOCKED",
                }
            )
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @kernel_function(
        name="generate_route_plan",
        description="Generate prioritized dispatch routes sorted by transit time.",
    )
    def generate_route_plan(
        self,
        allocation_draft_json: Annotated[Any, "JSON list of allocations: [{zone_id, warehouse_id, resource_type, quantity}]"],
        distance_matrix_json: Annotated[Any, "JSON distance matrix returned by calculate_distance_matrix"],
    ) -> str:
        """Sorts planned dispatches by transit time and assigns priority dispatch sequencing."""
        try:
            allocations = json.loads(allocation_draft_json) if isinstance(allocation_draft_json, str) else allocation_draft_json
            matrix_data = json.loads(distance_matrix_json) if isinstance(distance_matrix_json, str) else distance_matrix_json
            matrix_rows = matrix_data.get("matrix", [])

            lookup: Dict[tuple, Dict[str, Any]] = {
                (row["warehouse_id"], row["zone_id"]): row for row in matrix_rows
            }

            routes: List[Dict[str, Any]] = []
            for alloc in allocations:
                wid = alloc.get("warehouse_id")
                zid = alloc.get("zone_id")
                matched = lookup.get((wid, zid), {})

                effective_km = matched.get("effective_km", 50.0)
                status = matched.get("road_status", "OPEN")
                transit_hours = matched.get(
                    "estimated_transit_hours",
                    round(self._transit_hours_for(effective_km, status), 2),
                )

                routes.append(
                    {
                        "zone_id": zid,
                        "warehouse_id": wid,
                        "resource_type": alloc.get("resource_type"),
                        "allocated_qty": alloc.get("allocated_qty") or alloc.get("quantity", 0),
                        "effective_km": effective_km,
                        "road_distance_km": matched.get("road_distance_km", effective_km),
                        "transit_hours": transit_hours,
                        "road_status": status,
                        "route_available": matched.get("route_available", status != "BLOCKED"),
                        "aerial_delivery_required": matched.get("aerial_delivery_required", status in ("BLOCKED", "AIR_ONLY")),
                        "route_geometry": matched.get("route_geometry", []),
                        "routing_method": matched.get("routing_method", self.ROUTING_MODE_HAVERSINE),
                        "routing_source": matched.get("routing_source", f"Haversine Formula (Wt={self.WINDING_FACTOR})"),
                        "fallback_used": matched.get("fallback_used", False),
                        "fallback_reason": matched.get("fallback_reason"),
                    }
                )

            routes.sort(key=lambda r: r["transit_hours"])
            for idx, r in enumerate(routes, start=1):
                r["route_id"] = f"DISPATCH-ROUTE-{idx:03d}"
                r["dispatch_sequence"] = idx

            return json.dumps(
                {
                    "success": True,
                    "routes": routes,
                    "total_routes": len(routes),
                }
            )
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc), "routes": [], "total_routes": 0})

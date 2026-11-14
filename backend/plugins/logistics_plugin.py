"""
ReliefOps AI — Logistics and Transport Routing Plugin
Provides Semantic Kernel plugin functions for Haversine distance matrix computation,
road network impedance evaluation, transit time estimation, and route planning.

Academic Disclaimer:
Synthetic demonstration platform developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import json
import math
from typing import Annotated, Any, Dict, List, Union
from semantic_kernel.functions import kernel_function


class LogisticsPlugin:
    """Semantic Kernel plugin for humanitarian logistics and transport routing."""

    WINDING_FACTOR: float = 1.35
    BASE_SPEED_GROUND: float = 45.0  # km/h
    BASE_SPEED_AIR: float = 90.0     # km/h

    ETA_MULTIPLIERS: Dict[str, float] = {
        "OPEN": 1.0,
        "DEGRADED": 0.5,
        "BLOCKED": 0.15,
        "AIR_ONLY": 1.0,
    }

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
        """Calculates transit hours based on access status."""
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

    @kernel_function(
        name="calculate_distance_matrix",
        description="Compute effective road/air distance matrix between warehouses and zones.",
    )
    def calculate_distance_matrix(
        self,
        warehouses_json: Annotated[str, "JSON list of warehouses: [{warehouse_id, lat/latitude, lon/longitude, name}]"],
        zones_json: Annotated[str, "JSON list of zones: [{zone_id, lat/latitude, lon/longitude, name, road_status/access_status}]"],
    ) -> str:
        """Returns distance matrix with haversine and effective km adjusted by winding factor."""
        try:
            warehouses = json.loads(warehouses_json) if isinstance(warehouses_json, str) else warehouses_json
            zones = json.loads(zones_json) if isinstance(zones_json, str) else zones_json

            matrix: List[Dict[str, Any]] = []
            for wh in warehouses:
                w_lat = float(wh.get("latitude") if "latitude" in wh else wh.get("lat", 0.0))
                w_lon = float(wh.get("longitude") if "longitude" in wh else wh.get("lon", 0.0))
                wid = wh.get("warehouse_id", "UNKNOWN_WH")
                w_name = wh.get("name") or wh.get("warehouse_name", wid)

                for zone in zones:
                    z_lat = float(zone.get("latitude") if "latitude" in zone else zone.get("lat", 0.0))
                    z_lon = float(zone.get("longitude") if "longitude" in zone else zone.get("lon", 0.0))
                    zid = zone.get("zone_id", "UNKNOWN_ZONE")
                    z_name = zone.get("name") or zone.get("zone_name", zid)
                    status = (zone.get("access_status") or zone.get("road_status") or "OPEN").upper().strip()

                    hav_km = self._haversine_km(w_lat, w_lon, z_lat, z_lon)
                    effective_km = round(hav_km * self.WINDING_FACTOR, 2)
                    transit_hrs = round(self._transit_hours_for(effective_km, status), 2)

                    matrix.append(
                        {
                            "warehouse_id": wid,
                            "warehouse_name": w_name,
                            "zone_id": zid,
                            "zone_name": z_name,
                            "haversine_km": round(hav_km, 2),
                            "effective_km": effective_km,
                            "road_status": status,
                            "estimated_transit_hours": transit_hrs,
                        }
                    )

            return json.dumps(
                {
                    "success": True,
                    "winding_factor": self.WINDING_FACTOR,
                    "matrix": matrix,
                    "total_connections": len(matrix),
                }
            )
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc), "matrix": [], "total_connections": 0})

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
                    "feasible_48h": transit_hours <= 48.0,
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
        allocation_draft_json: Annotated[str, "JSON list of allocations: [{zone_id, warehouse_id, resource_type, quantity}]"],
        distance_matrix_json: Annotated[str, "JSON distance matrix returned by calculate_distance_matrix"],
    ) -> str:
        """Sorts planned dispatches by transit time and assigns priority dispatch sequencing."""
        try:
            allocations = json.loads(allocation_draft_json) if isinstance(allocation_draft_json, str) else allocation_draft_json
            matrix_data = json.loads(distance_matrix_json) if isinstance(distance_matrix_json, str) else distance_matrix_json
            matrix_rows = matrix_data.get("matrix", [])

            lookup: Dict[tuple, Dict] = {
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
                        "transit_hours": transit_hours,
                        "road_status": status,
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

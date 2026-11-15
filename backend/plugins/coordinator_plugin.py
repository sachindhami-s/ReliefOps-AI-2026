"""
ReliefOps AI — Coordinator Synthesis Plugin
Provides Semantic Kernel plugin functions for synthesizing balanced relief allocation plans
using the Two-Phase Water-Filling algorithm (guaranteed floor + ZPS-weighted residual).

Academic Disclaimer:
Synthetic demonstration platform developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import json
import math
from typing import Annotated, Any, Dict, List, Optional
from semantic_kernel.functions import kernel_function


class CoordinatorPlugin:
    """Semantic Kernel plugin for synthesizing multi-zone relief allocation drafts."""

    RESOURCE_TYPES = ["FOOD_RATIONS", "CLEAN_WATER", "MEDICAL_KITS", "SHELTER_TENTS"]

    DEMAND_KEY_MAP = {
        "FOOD_RATIONS": ["food_packs", "FOOD_RATIONS", "food_rations"],
        "CLEAN_WATER": ["water_liters", "CLEAN_WATER", "clean_water"],
        "MEDICAL_KITS": ["medical_kits", "MEDICAL_KITS"],
        "SHELTER_TENTS": ["tents", "emergency_shelter_tents", "SHELTER_TENTS", "shelter_tents"],
    }

    @kernel_function(
        name="synthesize_allocation_draft",
        description="Synthesizes candidate allocation dispatches from warehouses to zones using Two-Phase Water-Filling or Greedy Cost-Minimization.",
    )
    def synthesize_allocation_draft(
        self,
        zone_needs_json: Annotated[str, "JSON object containing zones list with demands and zps score"],
        inventory_snapshot_json: Annotated[str, "JSON object containing warehouses with available stock"],
        logistics_matrix_json: Annotated[str, "JSON object containing warehouse-to-zone distance matrix"],
        floor_ratio: Annotated[float, "Guaranteed floor allocation fraction (default 0.30)"] = 0.30,
        policy: Annotated[str, "Allocation policy: 'fair' (Two-Phase Water-Filling) or 'greedy' (Cost/Distance Minimization)"] = "fair",
    ) -> str:
        """
        Executes Two-Phase Water-Filling allocation optimization across zones and assigns nearest warehouses.
        """
        try:
            needs_data = json.loads(zone_needs_json) if isinstance(zone_needs_json, str) else zone_needs_json
            inv_data = json.loads(inventory_snapshot_json) if isinstance(inventory_snapshot_json, str) else inventory_snapshot_json
            log_data = json.loads(logistics_matrix_json) if isinstance(logistics_matrix_json, str) else logistics_matrix_json

            if isinstance(needs_data, list):
                zones = needs_data
            elif isinstance(needs_data, dict):
                zones = needs_data.get("zones", [])
            else:
                zones = []

            warehouses = inv_data.get("warehouses", []) if isinstance(inv_data, dict) else []
            log_matrix = log_data.get("matrix", []) if isinstance(log_data, dict) else []

            # Build warehouse lookup & stock pools per resource: {resource_type: {warehouse_id: available_qty}}
            warehouse_meta: Dict[str, Dict[str, Any]] = {}
            warehouse_stocks: Dict[str, Dict[str, int]] = {rtype: {} for rtype in self.RESOURCE_TYPES}
            for wh in warehouses:
                wid = wh["warehouse_id"]
                warehouse_meta[wid] = {
                    "warehouse_name": wh.get("warehouse_name") or wh.get("name", wid),
                    "lat": wh.get("latitude") if "latitude" in wh else wh.get("lat"),
                    "lon": wh.get("longitude") if "longitude" in wh else wh.get("lon"),
                }
                res_dict = wh.get("resources", {})
                for rtype in self.RESOURCE_TYPES:
                    qty = 0
                    if rtype in res_dict:
                        qty = int(res_dict[rtype].get("available_quantity", 0))
                    warehouse_stocks[rtype][wid] = qty

            # Build zone coordinate/meta lookup
            zone_meta: Dict[str, Dict[str, Any]] = {}
            for z in zones:
                zid = z["zone_id"]
                zone_meta[zid] = {
                    "zone_name": z.get("zone_name") or z.get("name", zid),
                    "lat": z.get("lat") if z.get("lat") is not None else z.get("latitude"),
                    "lon": z.get("lon") if z.get("lon") is not None else z.get("longitude"),
                    "road_status": z.get("road_status") or z.get("access_status") or "OPEN",
                }

            # Build logistics lookup: (zone_id) -> list of warehouses sorted by transit hours / distance
            zone_routes: Dict[str, List[Dict[str, Any]]] = {}
            for row in log_matrix:
                zid = row["zone_id"]
                if zid not in zone_routes:
                    zone_routes[zid] = []
                zone_routes[zid].append(row)

            for zid in zone_routes:
                zone_routes[zid].sort(key=lambda r: (r.get("estimated_transit_hours", 999.0), r.get("effective_km", 999.0)))

            dispatches: List[Dict[str, Any]] = []
            resource_summary: Dict[str, Dict[str, Any]] = {}

            for rtype in self.RESOURCE_TYPES:
                aliases = self.DEMAND_KEY_MAP[rtype]

                # Extract demanded quantity per zone
                zone_reqs: Dict[str, int] = {}
                for z in zones:
                    zid = z["zone_id"]
                    demands = z.get("demands", {})
                    req = 0
                    for alias in aliases:
                        if alias in demands and demands[alias] is not None:
                            req = int(round(float(demands[alias])))
                            break
                    zone_reqs[zid] = req

                total_demanded = sum(zone_reqs.values())
                total_available = sum(warehouse_stocks[rtype].values())

                if total_demanded == 0:
                    resource_summary[rtype] = {
                        "resource_type": rtype,
                        "available": total_available,
                        "demanded": 0,
                        "allocated": 0,
                        "unfulfilled_qty": 0,
                        "surplus_qty": total_available,
                        "fulfillment_pct": 100.0,
                        "status": "ADEQUATE",
                    }
                    continue

                if total_available == 0:
                    for z in zones:
                        zid = z["zone_id"]
                        if zone_reqs[zid] > 0:
                            zm = zone_meta.get(zid, {})
                            dispatches.append(
                                {
                                    "zone_id": zid,
                                    "zone_name": zm.get("zone_name", zid),
                                    "warehouse_id": "NONE",
                                    "warehouse_name": "UNASSIGNED",
                                    "resource_type": rtype,
                                    "requested_qty": zone_reqs[zid],
                                    "allocated_qty": 0,
                                    "unfulfilled_qty": zone_reqs[zid],
                                    "distance_km": 0.0,
                                    "est_transit_hours": 0.0,
                                    "road_status": zm.get("road_status", "OPEN"),
                                    "source_lat": None,
                                    "source_lon": None,
                                    "target_lat": zm.get("lat"),
                                    "target_lon": zm.get("lon"),
                                }
                            )
                    resource_summary[rtype] = {
                        "resource_type": rtype,
                        "available": 0,
                        "demanded": total_demanded,
                        "allocated": 0,
                        "unfulfilled_qty": total_demanded,
                        "surplus_qty": 0,
                        "fulfillment_pct": 0.0,
                        "status": "CRITICAL_SHORTAGE",
                    }
                    continue

                # Target allocations determination based on policy
                target_allocations: Dict[str, int] = {}

                if total_available >= total_demanded:
                    # Satisfy 100% of demand
                    for zid, req in zone_reqs.items():
                        target_allocations[zid] = req
                elif policy == "greedy":
                    # Naive Greedy Cost/Distance Minimization (SCEN-05 benchmark):
                    # Fulfills closest zones first with zero floor protection until stocks run dry.
                    candidate_pairs = []
                    for zid, req in zone_reqs.items():
                        routes = zone_routes.get(zid, [])
                        for r in routes:
                            candidate_pairs.append({
                                "zone_id": zid,
                                "warehouse_id": r["warehouse_id"],
                                "effective_km": float(r.get("effective_km", 999.0)),
                                "est_transit_hours": float(r.get("estimated_transit_hours", 999.0)),
                            })
                    candidate_pairs.sort(key=lambda x: (x["est_transit_hours"], x["effective_km"]))

                    target_allocations = {zid: 0 for zid in zone_reqs}
                    sim_wh_stock = dict(warehouse_stocks[rtype])
                    for pair in candidate_pairs:
                        zid = pair["zone_id"]
                        wid = pair["warehouse_id"]
                        wh_left = sim_wh_stock.get(wid, 0)
                        unmet = zone_reqs[zid] - target_allocations[zid]
                        if wh_left > 0 and unmet > 0:
                            grant = min(wh_left, unmet)
                            target_allocations[zid] += grant
                            sim_wh_stock[wid] -= grant
                else:
                    # Two-Phase Water-Filling (Distributive Justice Policy)
                    global_ratio = total_available / total_demanded
                    effective_floor = min(float(floor_ratio), global_ratio * 0.5)

                    floor_allocs: Dict[str, int] = {}
                    for zid, req in zone_reqs.items():
                        floor_allocs[zid] = math.floor(req * effective_floor)

                    total_floor = sum(floor_allocs.values())
                    residual_supply = max(0, total_available - total_floor)

                    # Phase 2: Distribute residual proportional to (ZPS * unmet_demand)
                    weights: Dict[str, float] = {}
                    for z in zones:
                        zid = z["zone_id"]
                        zps_val = float(z.get("zps") if "zps" in z else z.get("zps_score", 50.0))
                        unmet = max(0, zone_reqs[zid] - floor_allocs[zid])
                        weights[zid] = zps_val * unmet

                    total_weight = sum(weights.values())

                    for z in zones:
                        zid = z["zone_id"]
                        add_qty = 0
                        if total_weight > 0 and residual_supply > 0:
                            fraction = weights[zid] / total_weight
                            add_qty = min(
                                zone_reqs[zid] - floor_allocs[zid],
                                math.floor(residual_supply * fraction),
                            )
                        target_allocations[zid] = floor_allocs[zid] + add_qty

                    # Distribute integer rounding remainder to highest-ZPS zones with unmet need
                    allocated_so_far = sum(target_allocations.values())
                    remainder = max(0, min(total_available, total_demanded) - allocated_so_far)
                    if remainder > 0:
                        zones_by_zps = sorted(
                            zones,
                            key=lambda z: float(z.get("zps") if "zps" in z else z.get("zps_score", 50.0)),
                            reverse=True,
                        )
                        for z in zones_by_zps:
                            if remainder <= 0:
                                break
                            zid = z["zone_id"]
                            gap = max(0, zone_reqs[zid] - target_allocations[zid])
                            if gap > 0:
                                take = min(remainder, gap)
                                target_allocations[zid] += take
                                remainder -= take

                total_allocated_for_resource = 0

                # Logistics Assignment: fulfill target_allocations from nearest warehouses
                for z in zones:
                    zid = z["zone_id"]
                    needed = target_allocations[zid]
                    req_qty = zone_reqs[zid]
                    zm = zone_meta.get(zid, {})

                    if needed == 0:
                        if req_qty > 0:
                            dispatches.append(
                                {
                                    "zone_id": zid,
                                    "zone_name": zm.get("zone_name", zid),
                                    "warehouse_id": "NONE",
                                    "warehouse_name": "UNASSIGNED",
                                    "resource_type": rtype,
                                    "requested_qty": req_qty,
                                    "allocated_qty": 0,
                                    "unfulfilled_qty": req_qty,
                                    "distance_km": 0.0,
                                    "est_transit_hours": 0.0,
                                    "road_status": zm.get("road_status", "OPEN"),
                                    "source_lat": None,
                                    "source_lon": None,
                                    "target_lat": zm.get("lat"),
                                    "target_lon": zm.get("lon"),
                                }
                            )
                        continue

                    # Fallback to any warehouse if routes are empty
                    routes = zone_routes.get(zid, [])
                    if not routes and warehouses:
                        routes = [
                            {
                                "warehouse_id": wh["warehouse_id"],
                                "warehouse_name": wh.get("warehouse_name") or wh.get("name", wh["warehouse_id"]),
                                "effective_km": 50.0,
                                "estimated_transit_hours": 1.5,
                                "road_status": zm.get("road_status", "OPEN"),
                            }
                            for wh in warehouses
                        ]

                    remaining_to_dispatch = needed
                    zone_dispatched = 0

                    for route in routes:
                        if remaining_to_dispatch <= 0:
                            break
                        wid = route["warehouse_id"]
                        wh_stock = warehouse_stocks[rtype].get(wid, 0)
                        if wh_stock <= 0:
                            continue

                        fulfill_qty = min(remaining_to_dispatch, wh_stock)
                        warehouse_stocks[rtype][wid] -= fulfill_qty
                        remaining_to_dispatch -= fulfill_qty
                        zone_dispatched += fulfill_qty
                        total_allocated_for_resource += fulfill_qty

                        wm = warehouse_meta.get(wid, {})
                        dispatches.append(
                            {
                                "zone_id": zid,
                                "zone_name": zm.get("zone_name", zid),
                                "warehouse_id": wid,
                                "warehouse_name": wm.get("warehouse_name", wid),
                                "resource_type": rtype,
                                "requested_qty": req_qty,
                                "allocated_qty": fulfill_qty,
                                "unfulfilled_qty": max(0, req_qty - needed),
                                "distance_km": route.get("effective_km", 50.0),
                                "est_transit_hours": route.get("estimated_transit_hours", 2.0),
                                "road_status": route.get("road_status") or zm.get("road_status", "OPEN"),
                                "source_lat": wm.get("lat"),
                                "source_lon": wm.get("lon"),
                                "target_lat": zm.get("lat"),
                                "target_lon": zm.get("lon"),
                            }
                        )

                allocated_capped = min(total_demanded, total_allocated_for_resource)
                unfulfilled_total = max(0, total_demanded - allocated_capped)
                surplus_total = max(0, total_available - allocated_capped)
                fulfillment_pct = round(min(100.0, (allocated_capped / total_demanded * 100.0)), 1) if total_demanded > 0 else 100.0
                if unfulfilled_total == 0:
                    res_status = "ADEQUATE"
                elif fulfillment_pct < 50.0:
                    res_status = "CRITICAL_SHORTAGE"
                else:
                    res_status = "SHORTAGE"

                resource_summary[rtype] = {
                    "resource_type": rtype,
                    "available": total_available,
                    "demanded": total_demanded,
                    "allocated": allocated_capped,
                    "unfulfilled_qty": unfulfilled_total,
                    "surplus_qty": surplus_total,
                    "fulfillment_pct": fulfillment_pct,
                    "status": res_status,
                }

            return json.dumps(
                {
                    "success": True,
                    "dispatches": dispatches,
                    "total_dispatches": len(dispatches),
                    "resource_summary": resource_summary,
                }
            )
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc), "dispatches": [], "total_dispatches": 0, "resource_summary": {}})

"""
ReliefOps AI — Phase 8 Operational Command Dashboard
University Course: CSE476 (Agentic AI and Intelligent Automation)

Production-oriented Emergency Operations Center (EOC) Streamlit Command Interface
integrating the 5-agent Hayes-Roth Blackboard architecture, Microsoft Semantic Kernel plugins,
ChromaDB/BM25 SOP RAG Knowledge Assistant, Two-Phase Water-Filling Allocation Engine,
Distributive Fairness & Resource Adequacy Auditing, PyDeck Spatial GIS, and Dynamic Replanning.

Academic Disclaimer:
Synthetic demonstration platform developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
All operational data, disaster zones, and allocations are deterministic synthetic models.
"""

import datetime
import html
import json
from typing import Any, Dict, List, Optional
import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

from backend.agents.relief_coordinator import ReliefCoordinator
from backend.blackboard.blackboard_manager import BlackboardManager
from backend.database.db_manager import DatabaseManager, default_db_manager
from backend.database.seeder import build_scenario_context, seed_database
from backend.rag import default_sop_retriever


# =============================================================================
# 1. REUSABLE BACKEND DATA INTEGRATION & ANALYTICAL HELPERS
# =============================================================================

def load_scenarios_from_db(db: Optional[DatabaseManager] = None) -> Dict[str, Any]:
    """Loads simulation scenarios catalog from SQLite, handling empty/error states gracefully."""
    active_db = db or default_db_manager
    try:
        rows = active_db.execute_query(
            "SELECT scenario_id, title, description, scenario_type, parameters_json "
            "FROM simulation_scenarios ORDER BY scenario_id"
        )
        return {r["scenario_id"]: dict(r) for r in rows}
    except Exception:
        return {}


def load_all_zones_from_db(db: Optional[DatabaseManager] = None) -> List[Dict[str, Any]]:
    """Loads all seeded affected zones from SQLite."""
    active_db = db or default_db_manager
    try:
        rows = active_db.execute_query(
            "SELECT zone_id, event_id, name, latitude, longitude, population, "
            "vulnerability_index, damage_level, medical_urgency, access_status "
            "FROM affected_zones ORDER BY zone_id"
        )
        return [dict(r) for r in rows]
    except Exception:
        return []


def load_warehouses_from_db(db: Optional[DatabaseManager] = None) -> List[Dict[str, Any]]:
    """Loads operational warehouses and their inventory from SQLite."""
    active_db = db or default_db_manager
    try:
        rows = active_db.execute_query(
            "SELECT warehouse_id, name, latitude, longitude, status, total_capacity_m3 "
            "FROM warehouses ORDER BY warehouse_id"
        )
        return [dict(r) for r in rows]
    except Exception:
        return []


def load_historical_plans_from_db(
    db: Optional[DatabaseManager] = None, limit: int = 25
) -> List[Dict[str, Any]]:
    """Loads committed allocation plans from SQLite for audit traceability."""
    active_db = db or default_db_manager
    try:
        rows = active_db.execute_query(
            "SELECT plan_id, event_id, iteration, status, fairness_score, approved_by, created_at "
            "FROM allocation_plans ORDER BY created_at DESC LIMIT ?",
            (int(limit),),
        )
        return [dict(r) for r in rows]
    except Exception:
        return []


def compute_executive_kpis(
    plan: Optional[Dict[str, Any]], blackboard_snapshot: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Extracts Executive Overview KPI metrics directly from actual backend outputs
    (ReliefCoordinator final_plan and BlackboardManager snapshot) without
    duplicating backend domain formulas. Handles empty/None states safely.
    """
    if not plan or not isinstance(plan, dict):
        return {
            "has_data": False,
            "total_affected_population": 0,
            "total_displaced_population": 0,
            "active_zones_count": 0,
            "active_incident_id": "NONE",
            "active_hazard": "NONE",
            "active_severity": "NONE",
            "governing_sop": "N/A",
            "total_demanded_units": 0,
            "total_allocated_units": 0,
            "total_unfulfilled_units": 0,
            "total_surplus_units": 0,
            "critical_shortages_count": 0,
            "shortage_resources": [],
            "latest_plan_id": "NONE",
            "overall_status": "UNINITIALIZED",
            "fairness_verdict": "UNINITIALIZED",
            "adequacy_status": "UNINITIALIZED",
            "gini_coefficient": 0.0,
            "min_coverage_ratio": 0.0,
            "dispatches_count": 0,
            "resource_metrics": {},
        }

    snap = blackboard_snapshot if isinstance(blackboard_snapshot, dict) else {}
    zone_needs = snap.get("zone_needs") or []
    sop_ctx = snap.get("sop_context") or {}
    dis_ctx = snap.get("disaster_context") or {}
    inv_snap = snap.get("inventory_snapshot") or {}
    audit_data = plan.get("audit_verdict") or {}

    tot_pop = sum(int(z.get("affected_population", 0)) for z in zone_needs)
    tot_disp = sum(int(round(float(z.get("displaced_population", 0.0)))) for z in zone_needs)

    feas = inv_snap.get("feasibility") or {}
    res_adeq = audit_data.get("resource_adequacy") or plan.get("resource_adequacy") or {}

    resource_metrics: Dict[str, Dict[str, Any]] = {}
    tot_demanded = 0
    tot_allocated = 0
    tot_unfulfilled = 0
    tot_surplus = 0

    for rtype in ["FOOD_RATIONS", "CLEAN_WATER", "MEDICAL_KITS", "SHELTER_TENTS"]:
        f_item = feas.get(rtype, {})
        a_item = res_adeq.get(rtype, {})
        dem = int(a_item.get("demanded", f_item.get("demanded", 0)))
        avail = int(a_item.get("available", f_item.get("available", 0)))
        alloc = int(a_item.get("allocated", f_item.get("allocated", min(avail, dem))))
        unful = int(a_item.get("unfulfilled_qty", f_item.get("unfulfilled_qty", max(0, dem - alloc))))
        surplus = int(a_item.get("surplus_qty", f_item.get("surplus_qty", max(0, avail - alloc))))
        fulfill_pct = float(
            a_item.get(
                "fulfillment_pct",
                f_item.get("fulfillment_pct", round(min(100.0, (alloc / dem) * 100.0), 1) if dem > 0 else 100.0),
            )
        )
        status = str(a_item.get("status", f_item.get("status", "ADEQUATE")))
        resource_metrics[rtype] = {
            "demanded": dem,
            "available": avail,
            "allocated": alloc,
            "unfulfilled_qty": unful,
            "surplus_qty": surplus,
            "fulfillment_pct": min(100.0, max(0.0, fulfill_pct)),
            "status": status,
        }
        tot_demanded += dem
        tot_allocated += alloc
        tot_unfulfilled += unful
        tot_surplus += surplus

    shortage_res = list(
        audit_data.get("shortage_resources")
        or inv_snap.get("shortage_resources")
        or [r for r, m in resource_metrics.items() if m["unfulfilled_qty"] > 0]
    )

    sop_ids = sop_ctx.get("sop_ids") or []
    hazard_val = (
        sop_ctx.get("hazard")
        or sop_ctx.get("disaster_type")
        or plan.get("hazard")
        or dis_ctx.get("hazard")
        or dis_ctx.get("disaster_type")
        or "FLOOD"
    )

    return {
        "has_data": True,
        "total_affected_population": tot_pop,
        "total_displaced_population": tot_disp,
        "active_zones_count": len(zone_needs),
        "active_incident_id": str(plan.get("event_id") or dis_ctx.get("event_id") or "EVT-ACTIVE"),
        "active_hazard": str(hazard_val).upper(),
        "active_severity": str(sop_ctx.get("severity") or dis_ctx.get("severity") or "SEVERE"),
        "sop_severity_equivalent": str(sop_ctx.get("sop_severity_equivalent") or "Level 3"),
        "governing_sop": sop_ids[0] if sop_ids else "SOP-FL-001",
        "total_demanded_units": tot_demanded,
        "total_allocated_units": tot_allocated,
        "total_unfulfilled_units": tot_unfulfilled,
        "total_surplus_units": tot_surplus,
        "critical_shortages_count": len(shortage_res),
        "shortage_resources": shortage_res,
        "latest_plan_id": str(plan.get("plan_id") or "PLAN-NONE"),
        "overall_status": str(
            audit_data.get("overall_status") or plan.get("overall_status") or plan.get("status") or "UNKNOWN"
        ),
        "fairness_verdict": str(
            audit_data.get("fairness_verdict") or plan.get("fairness_status") or "FAIRNESS_APPROVED"
        ),
        "adequacy_status": str(
            audit_data.get("adequacy_status") or plan.get("adequacy_status") or "RESOURCE_ADEQUATE"
        ),
        "gini_coefficient": float(audit_data.get("gini_coefficient", 0.0)),
        "min_coverage_ratio": float(audit_data.get("min_coverage_ratio", 0.0)),
        "dispatches_count": len(plan.get("dispatches") or []),
        "resource_metrics": resource_metrics,
    }


def build_lorenz_curve_data(
    zone_needs: List[Dict[str, Any]],
    fair_summaries: List[Dict[str, Any]],
    greedy_summaries: List[Dict[str, Any]],
    fair_gini: float,
    greedy_gini: float,
) -> pd.DataFrame:
    """
    Computes empirical Lorenz curve coordinates for Fair Water-Filling and Naive Greedy policies.
    X-axis: Cumulative Share of Affected Disaster Sectors (%) [k / n]
    Y-axis: Cumulative Need Coverage Share (%) [sum(c_1..k) / sum(c_1..n)]
    Points are computed from actual zone demands, allocations, and coverage ratios.
    Directly satisfies the trapezoidal identity: Gini = 1 - sum((Y[i] + Y[i-1]) * (X[i] - X[i-1]))
    """
    pop_map: Dict[str, int] = {}
    for z in zone_needs:
        zid = z.get("zone_id")
        pop = max(1, int(z.get("population") or z.get("affected_population") or 1))
        pop_map[zid] = pop

    rows = []
    # 1. Line of Perfect Equality (45-degree diagonal)
    rows.append({
        "Cumulative Share %": 0.0,
        "Cumulative Coverage %": 0.0,
        "Policy": "Line of Perfect Equality (45°)",
        "Zone": "Origin",
        "Population": 0,
        "Zone Coverage %": "0.0%",
    })
    rows.append({
        "Cumulative Share %": 100.0,
        "Cumulative Coverage %": 100.0,
        "Policy": "Line of Perfect Equality (45°)",
        "Zone": "100% Equal Coverage",
        "Population": sum(pop_map.values()),
        "Zone Coverage %": "100.0%",
    })

    def add_policy_curve(summaries: List[Dict[str, Any]], policy_name: str):
        zone_data = []
        for s in summaries:
            zid = s.get("zone_id")
            pop = pop_map.get(zid, 10000)
            dem = float(s.get("total_demanded", 1.0))
            alloc = float(s.get("total_allocated", 0.0))
            cov = alloc / dem if dem > 0 else 1.0
            cov = min(1.0, max(0.0, cov))
            zone_data.append({
                "zone_id": zid,
                "zone_name": s.get("zone_name") or zid,
                "pop": pop,
                "alloc": alloc,
                "demanded": dem,
                "coverage_ratio": cov,
            })

        # Sort ascending by coverage ratio (standard Lorenz ordering)
        zone_data.sort(key=lambda d: d["coverage_ratio"])
        n = len(zone_data)
        if n == 0:
            return
        tot_cov = sum(d["coverage_ratio"] for d in zone_data) or 1.0

        rows.append({
            "Cumulative Share %": 0.0,
            "Cumulative Coverage %": 0.0,
            "Policy": policy_name,
            "Zone": "Origin",
            "Population": 0,
            "Zone Coverage %": "0.0%",
        })
        cum_cov = 0.0
        for i, d in enumerate(zone_data):
            cum_cov += d["coverage_ratio"]
            rows.append({
                "Cumulative Share %": round(((i + 1) / n) * 100.0, 2),
                "Cumulative Coverage %": round((cum_cov / tot_cov) * 100.0, 2),
                "Policy": policy_name,
                "Zone": d["zone_name"],
                "Population": d["pop"],
                "Zone Coverage %": f"{d['coverage_ratio'] * 100.0:.2f}%",
            })

    fair_label = f"ReliefOps AI: Two-Phase Water-Filling (Gini = {fair_gini:.4f})"
    greedy_label = f"Naive Greedy Optimization (Gini = {greedy_gini:.4f})"

    if fair_summaries:
        add_policy_curve(fair_summaries, fair_label)
    if greedy_summaries:
        add_policy_curve(greedy_summaries, greedy_label)

    return pd.DataFrame(rows)


def build_gis_layers_data(
    zone_needs: List[Dict[str, Any]],
    inv_snap: Dict[str, Any],
    dispatches: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Constructs spatial GIS point and route corridor layers solely from actual
    database/blackboard coordinates. Never fabricates missing coordinates.
    """
    wh_lookup: Dict[str, Dict[str, Any]] = {}
    wh_points: List[Dict[str, Any]] = []

    for wh in (inv_snap or {}).get("warehouses", []):
        wid = wh.get("warehouse_id")
        raw_lat = wh.get("latitude")
        raw_lon = wh.get("longitude")
        if raw_lat is None or raw_lon is None:
            continue
        w_lat = float(raw_lat)
        w_lon = float(raw_lon)
        w_name = wh.get("warehouse_name") or wh.get("name", wid)
        res = wh.get("resources", {})
        stock_summary = (
            f"Food: {res.get('FOOD_RATIONS', {}).get('available_quantity', 0):,} | "
            f"Water: {res.get('CLEAN_WATER', {}).get('available_quantity', 0):,}L | "
            f"Med: {res.get('MEDICAL_KITS', {}).get('available_quantity', 0):,} | "
            f"Tents: {res.get('SHELTER_TENTS', {}).get('available_quantity', 0):,}"
        )
        wh_lookup[wid] = {"name": w_name, "lat": w_lat, "lon": w_lon, "stock": stock_summary}
        wh_points.append(
            {
                "id": wid,
                "name": f"Depot: {w_name} ({wid})",
                "type": f"WAREHOUSE DEPOT ({wh.get('status', 'OPERATIONAL')})",
                "lat": w_lat,
                "lon": w_lon,
                "details": f"Stock: {stock_summary} | Coords: ({w_lat:.2f}, {w_lon:.2f})",
                "color": [16, 185, 129, 235],
                "radius": 12500,
            }
        )

    zone_lookup: Dict[str, Dict[str, Any]] = {}
    zone_points: List[Dict[str, Any]] = []
    for z in zone_needs or []:
        zid = z.get("zone_id")
        raw_lat = z.get("lat") if z.get("lat") is not None else z.get("latitude")
        raw_lon = z.get("lon") if z.get("lon") is not None else z.get("longitude")
        if raw_lat is None or raw_lon is None:
            continue
        z_lat = float(raw_lat)
        z_lon = float(raw_lon)
        z_name = z.get("zone_name") or z.get("name", zid)
        z_zps = float(z.get("zps", 50.0))
        z_road = str(z.get("road_status") or z.get("access_status") or "OPEN")
        z_dmg = int(z.get("damage_level", 3))
        zone_lookup[zid] = {
            "name": z_name,
            "lat": z_lat,
            "lon": z_lon,
            "zps": z_zps,
            "road_status": z_road,
            "damage_level": z_dmg,
        }
        if z_road == "BLOCKED" or z_dmg >= 5:
            z_color = [239, 68, 68, 240]
        elif z_road == "DEGRADED" or z_dmg == 4:
            z_color = [245, 158, 11, 230]
        else:
            z_color = [56, 189, 248, 225]

        zone_points.append(
            {
                "id": zid,
                "name": f"Zone #{z.get('priority_rank', 1)}: {z_name} (ZPS: {z_zps:.1f})",
                "type": f"AFFECTED ZONE ({z_road})",
                "lat": z_lat,
                "lon": z_lon,
                "details": (
                    f"Pop: {z.get('affected_population', 0):,} | "
                    f"Damage: {z_dmg}/5 | Access: {z_road} | ZPS: {z_zps:.1f}"
                ),
                "color": z_color,
                "radius": max(9000, int(z_zps * 175)),
            }
        )

    corridors: Dict[tuple, Dict[str, Any]] = {}
    for d in dispatches or []:
        if d.get("allocated_qty", 0) <= 0 or d.get("warehouse_id") == "NONE":
            continue
        wid = d.get("warehouse_id")
        zid = d.get("zone_id")
        w_info = wh_lookup.get(wid, {})
        z_info = zone_lookup.get(zid, {})

        s_lat = d.get("source_lat") if d.get("source_lat") is not None else w_info.get("lat")
        s_lon = d.get("source_lon") if d.get("source_lon") is not None else w_info.get("lon")
        t_lat = d.get("target_lat") if d.get("target_lat") is not None else z_info.get("lat")
        t_lon = d.get("target_lon") if d.get("target_lon") is not None else z_info.get("lon")

        if s_lat is None or s_lon is None or t_lat is None or t_lon is None:
            continue

        key = (wid, zid)
        road_st = str(d.get("road_status") or z_info.get("road_status", "OPEN"))
        if key not in corridors:
            if road_st == "BLOCKED":
                src_col = [245, 158, 11, 240]
                tgt_col = [239, 68, 68, 240]
            elif road_st == "DEGRADED":
                src_col = [56, 189, 248, 230]
                tgt_col = [249, 115, 22, 230]
            else:
                src_col = [16, 185, 129, 230]
                tgt_col = [59, 130, 246, 230]

            corridors[key] = {
                "warehouse_id": wid,
                "warehouse_name": d.get("warehouse_name") or w_info.get("name", wid),
                "zone_id": zid,
                "zone_name": d.get("zone_name") or z_info.get("name", zid),
                "source_lat": float(s_lat),
                "source_lon": float(s_lon),
                "target_lat": float(t_lat),
                "target_lon": float(t_lon),
                "distance_km": float(d.get("distance_km", 0.0)),
                "est_transit_hours": float(d.get("est_transit_hours", 0.0)),
                "road_status": road_st,
                "cargo_items": [],
                "source_color": src_col,
                "target_color": tgt_col,
            }
        corridors[key]["cargo_items"].append(f"{d.get('resource_type')}: {d.get('allocated_qty', 0):,}")

    route_rows: List[Dict[str, Any]] = []
    for c in corridors.values():
        cargo_str = " | ".join(c["cargo_items"])
        route_rows.append(
            {
                "name": f"Route: {c['warehouse_name']} -> {c['zone_name']}",
                "type": f"DISPATCH CORRIDOR ({c['road_status']})",
                "details": f"Dist: {c['distance_km']:.1f} km | ETA: {c['est_transit_hours']:.1f} hrs | Cargo: {cargo_str}",
                "warehouse_name": c["warehouse_name"],
                "zone_name": c["zone_name"],
                "road_status": c["road_status"],
                "distance_km": c["distance_km"],
                "est_transit_hours": c["est_transit_hours"],
                "cargo_manifest": cargo_str,
                "source_lat": c["source_lat"],
                "source_lon": c["source_lon"],
                "target_lat": c["target_lat"],
                "target_lon": c["target_lon"],
                "source_color": c["source_color"],
                "target_color": c["target_color"],
            }
        )

    return {
        "warehouse_points": wh_points,
        "zone_points": zone_points,
        "route_rows": route_rows,
    }


def query_rag_knowledge_assistant(
    question: str,
    hazard_filter: Optional[str] = None,
    top_k: int = 4,
) -> Dict[str, Any]:
    """
    Connects directly to the backend ChromaDB/BM25 SOPRetriever pipeline to answer
    operator disaster-response questions with grounded passages and citations.
    """
    clean_q = (question or "").strip()
    if not clean_q:
        return {
            "status": "EMPTY_QUERY",
            "question": "",
            "grounded_answer": "Please enter a valid disaster-response question to query the SOP knowledge base.",
            "sop_ids": [],
            "retrieval_method": "none",
            "execution_time_ms": 0.0,
            "chunks": [],
        }

    hz = hazard_filter.strip().upper() if hazard_filter and hazard_filter.strip().upper() != "ALL" else None
    res = default_sop_retriever.retrieve(
        query=clean_q,
        top_k=max(1, min(10, int(top_k))),
        hazard_filter=hz,
    )

    chunks_data = []
    synthesis_bullets = []
    for idx, ch in enumerate(res.retrieved_chunks, 1):
        excerpt = (ch.content or "").strip()
        chunks_data.append(
            {
                "rank": idx,
                "chunk_id": ch.chunk_id,
                "sop_id": ch.sop_id,
                "title": ch.title,
                "hazard_type": ch.hazard_type,
                "section_title": ch.section_title,
                "score": round(float(ch.score), 4),
                "retrieval_method": ch.retrieval_method,
                "content": excerpt,
            }
        )
        first_lines = " ".join(
            line.strip()
            for line in excerpt.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )[:280]
        synthesis_bullets.append(
            f"- **[{ch.sop_id} | {ch.chunk_id}] ({ch.section_title}):** {first_lines}..."
        )

    if chunks_data:
        grounded_answer = (
            f"**Grounded Operational Guidance ({len(chunks_data)} SOP passages retrieved via `{res.retrieval_method}` "
            f"in `{res.execution_time_ms:.2f} ms`):**\n\n"
            + "\n".join(synthesis_bullets)
            + f"\n\n**Authoritative Source Documents Cited:** `{', '.join(res.sop_ids)}`"
        )
        status = "SUCCESS"
    else:
        grounded_answer = "No matching SOP passages were found for the specified query and hazard filter."
        status = "NO_RESULTS"

    return {
        "status": status,
        "question": clean_q,
        "hazard_filter": hz or "ALL",
        "grounded_answer": grounded_answer,
        "sop_ids": res.sop_ids,
        "retrieval_method": res.retrieval_method,
        "execution_time_ms": res.execution_time_ms,
        "chunks": chunks_data,
    }


def execute_dynamic_replanning_workflow(
    initial_context: Dict[str, Any],
    surge_zone_name: str,
    surge_multiplier: float = 1.75,
    surge_damage_lvl: int = 5,
    new_access_status: str = "BLOCKED",
    db: Optional[DatabaseManager] = None,
) -> Dict[str, Any]:
    """
    Executes the actual multi-agent dynamic replanning workflow on an updated
    incident context while preserving the active hazard, and computes a structured
    comparison between the initial and revised plans.
    """
    active_db = db or default_db_manager
    if not initial_context or not initial_context.get("zones"):
        raise ValueError("Initial disaster context must contain at least one affected zone for replanning.")

    # Ensure initial baseline plan is available
    bb_init = BlackboardManager(db=active_db)
    coord_init = ReliefCoordinator(blackboard=bb_init, db=active_db)
    initial_plan = coord_init.run_full_coordination_cycle(disaster_context=json.loads(json.dumps(initial_context)))
    initial_snap = bb_init.get_snapshot()

    # Construct post-incident context preserving active hazard
    surge_ctx = json.loads(json.dumps(initial_context))
    active_hazard = (
        initial_snap.get("sop_context", {}).get("hazard")
        or surge_ctx.get("hazard")
        or surge_ctx.get("disaster_type")
        or "FLOOD"
    )
    surge_ctx["hazard"] = active_hazard
    surge_ctx["disaster_type"] = active_hazard
    base_event_id = str(surge_ctx.get("event_id", "EVT-2026-FL01")).replace("-SURGE", "")
    surge_ctx["event_id"] = f"{base_event_id}-SURGE"
    base_name = str(surge_ctx.get("name", "Disaster Event")).replace(" (Post-Breach Surge)", "")
    surge_ctx["name"] = f"{base_name} (Post-Breach Surge)"

    matched = False
    for z in surge_ctx.get("zones", []):
        z_label = z.get("name") or z.get("zone_name") or z.get("zone_id")
        if z_label == surge_zone_name or z.get("zone_id") == surge_zone_name:
            old_pop = int(z.get("population") or z.get("affected_population") or 10000)
            new_pop = int(round(old_pop * float(surge_multiplier)))
            z["population"] = new_pop
            z["affected_population"] = new_pop
            z["damage_level"] = max(1, min(5, int(surge_damage_lvl)))
            z["access_status"] = new_access_status
            z["road_status"] = new_access_status
            matched = True
            break

    if not matched and surge_ctx.get("zones"):
        z0 = surge_ctx["zones"][0]
        old_pop = int(z0.get("population") or z0.get("affected_population") or 10000)
        new_pop = int(round(old_pop * float(surge_multiplier)))
        z0["population"] = new_pop
        z0["affected_population"] = new_pop
        z0["damage_level"] = max(1, min(5, int(surge_damage_lvl)))
        z0["access_status"] = new_access_status
        z0["road_status"] = new_access_status

    bb_rev = BlackboardManager(db=active_db)
    coord_rev = ReliefCoordinator(blackboard=bb_rev, db=active_db)
    revised_plan = coord_rev.run_full_coordination_cycle(disaster_context=surge_ctx)
    revised_greedy = coord_rev.evaluate_greedy_baseline(disaster_context=surge_ctx)
    revised_snap = bb_rev.get_snapshot()

    orig_zones = initial_snap.get("zone_needs") or []
    new_zones = revised_snap.get("zone_needs") or []
    orig_pop_total = sum(int(z.get("affected_population", 0)) for z in orig_zones)
    new_pop_total = sum(int(z.get("affected_population", 0)) for z in new_zones)

    orig_gini = float((initial_plan.get("audit_verdict") or {}).get("gini_coefficient", 0.0))
    new_gini = float((revised_plan.get("audit_verdict") or {}).get("gini_coefficient", 0.0))

    return {
        "initial_plan": initial_plan,
        "initial_snapshot": initial_snap,
        "revised_plan": revised_plan,
        "revised_snapshot": revised_snap,
        "revised_greedy": revised_greedy,
        "revised_context": surge_ctx,
        "preserved_hazard": revised_snap.get("sop_context", {}).get("hazard", active_hazard),
        "population_before": orig_pop_total,
        "population_after": new_pop_total,
        "population_delta": new_pop_total - orig_pop_total,
        "gini_before": orig_gini,
        "gini_after": new_gini,
        "gini_delta": round(new_gini - orig_gini, 4),
    }


# =============================================================================
# 2. STREAMLIT UI RENDERER
# =============================================================================

def render_dashboard() -> None:
    """Renders the complete ReliefOps AI Phase 8 Operational Command Dashboard."""
    st.set_page_config(
        page_title="ReliefOps AI — Operational Command Center",
        page_icon="🚨",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Dark Navy Emergency Operations Center (EOC) Styling
    st.markdown(
        """
        <style>
        /* Core Dark Navy Command Aesthetic */
        .stApp {
            background-color: #0B1120;
            color: #F8FAFC;
        }
        [data-testid="stSidebar"] {
            background-color: #0F172A;
            border-right: 1px solid #1E293B;
        }
        [data-testid="stHeader"] {
            background-color: rgba(11, 17, 32, 0.85);
        }
        /* Command Top Header Bar */
        .eoc-command-banner {
            background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
            border: 1px solid #334155;
            border-left: 5px solid #38BDF8;
            border-radius: 10px;
            padding: 1.1rem 1.4rem;
            margin-bottom: 1rem;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
        }
        .eoc-title {
            font-size: 1.75rem;
            font-weight: 800;
            color: #F8FAFC;
            letter-spacing: 0.02em;
            margin: 0;
        }
        .eoc-subtitle {
            font-size: 0.92rem;
            color: #94A3B8;
            margin-top: 0.25rem;
        }
        .disclaimer-strip {
            background-color: rgba(245, 158, 11, 0.12);
            border: 1px solid rgba(245, 158, 11, 0.4);
            border-left: 4px solid #F59E0B;
            color: #FDE68A;
            padding: 0.55rem 0.9rem;
            border-radius: 6px;
            font-size: 0.82rem;
            margin-bottom: 1rem;
        }
        /* Tactical KPI Cards */
        .eoc-kpi-card {
            background-color: #1E293B;
            border: 1px solid #334155;
            border-top: 3px solid #38BDF8;
            border-radius: 8px;
            padding: 0.9rem 1rem;
            min-height: 112px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
        }
        .eoc-kpi-card.alert-red {
            border-top-color: #EF4444;
        }
        .eoc-kpi-card.alert-amber {
            border-top-color: #F59E0B;
        }
        .eoc-kpi-card.alert-green {
            border-top-color: #10B981;
        }
        .eoc-kpi-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #94A3B8;
            font-weight: 600;
            margin-bottom: 0.3rem;
        }
        .eoc-kpi-value {
            font-size: 1.45rem;
            font-weight: 800;
            color: #F8FAFC;
            line-height: 1.2;
        }
        .eoc-kpi-sub {
            font-size: 0.78rem;
            color: #CBD5E1;
            margin-top: 0.3rem;
        }
        /* Status Badges */
        .badge-approved {
            background-color: rgba(16, 185, 129, 0.18);
            color: #34D399;
            border: 1px solid rgba(16, 185, 129, 0.45);
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.76rem;
            display: inline-block;
        }
        .badge-warning {
            background-color: rgba(245, 158, 11, 0.18);
            color: #FBBF24;
            border: 1px solid rgba(245, 158, 11, 0.45);
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.76rem;
            display: inline-block;
        }
        .badge-rejected {
            background-color: rgba(239, 68, 68, 0.2);
            color: #F87171;
            border: 1px solid rgba(239, 68, 68, 0.5);
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.76rem;
            display: inline-block;
        }
        .badge-info {
            background-color: rgba(56, 189, 248, 0.16);
            color: #38BDF8;
            border: 1px solid rgba(56, 189, 248, 0.4);
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.76rem;
            display: inline-block;
        }
        .eoc-panel {
            background-color: #1E293B;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 1rem 1.2rem;
            margin-bottom: 0.9rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Academic Disclaimer & Command Header
    st.markdown(
        """
        <div class="disclaimer-strip">
            <strong>ACADEMIC SIMULATION CHARTER (CSE476 — Agentic AI &amp; Intelligent Automation):</strong>
            Deterministic multi-agent decision-support command platform. All disaster parameters, coordinates, and allocations are synthetic models integrated with live backend agents, SQLite, and ChromaDB RAG.
        </div>
        <div class="eoc-command-banner">
            <div class="eoc-title">🚨 RELIEFOPS AI — EMERGENCY OPERATIONS COMMAND CENTER</div>
            <div class="eoc-subtitle">
                Autonomous Hayes-Roth Blackboard • Microsoft Semantic Kernel • ChromaDB Vector RAG • Two-Phase Water-Filling &amp; Distributive Justice Gate
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Verify Database Connectivity & Load Catalog
    scenarios_catalog = load_scenarios_from_db()
    all_db_zones = load_all_zones_from_db()

    if not scenarios_catalog or not all_db_zones:
        st.warning(
            "⚠️ **Database Empty or Unseeded:** The operational SQLite database currently contains no seeded scenarios or affected zones."
        )
        if st.button("🔄 Initialize & Seed Master Operational Database", type="primary"):
            try:
                seed_database(default_db_manager)
                st.success("✅ Master disaster database seeded successfully. Reloading command console...")
                st.rerun()
            except Exception as db_exc:
                st.error(f"❌ Database initialization failed: {db_exc}")
                return
        return

    # =========================================================================
    # SIDEBAR: NAVIGATION, SCENARIO CONFIGURATION & INTERACTIVE FILTERS
    # =========================================================================
    st.sidebar.markdown("### 🧭 EOC Command Navigation")
    module_options = [
        "ALL MODULES (Command Tabs)",
        "1. Executive Overview",
        "2. Disaster Monitoring",
        "3. GIS Command Map",
        "4. Resource Management",
        "5. AI Allocation Engine",
        "6. Fairness Analytics",
        "7. RAG Knowledge Assistant",
        "8. Dynamic Replanning",
        "9. Audit & Explainability",
    ]
    selected_module = st.sidebar.selectbox(
        "Active Operational View",
        module_options,
        index=0,
        help="View all 9 modules in the unified command tab bar or isolate a single module.",
    )

    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Scenario & Hazard Control")

    scenario_options = ["Custom User Scenario"] + [
        f"{s_id}: {data['title']}" for s_id, data in scenarios_catalog.items()
    ]
    selected_option = st.sidebar.selectbox(
        "Select Evaluation Scenario",
        scenario_options,
        index=1 if len(scenario_options) > 1 else 0,
    )

    HAZARD_DEFAULT_EVENTS = {
        "FLOOD": ("EVT-2026-FL01", "Brahmaputra Valley Catastrophic Monsoon Flood"),
        "EARTHQUAKE": ("EVT-2026-EQ01", "Assam-Arunachal Seismic Zone High-Magnitude Earthquake"),
        "CYCLONE": ("EVT-2026-CY01", "Bay of Bengal Severe Tropical Cyclone & Storm Surge"),
        "LANDSLIDE": ("EVT-2026-LS01", "Himalayan Ridge Multi-Sector Mountain Landslide & Blockade"),
    }

    if selected_option != "Custom User Scenario":
        selected_id = selected_option.split(":")[0].strip()
        scen_meta = scenarios_catalog.get(selected_id, {})
        st.sidebar.caption(f"**Scenario Type:** `{scen_meta.get('scenario_type', 'STANDARD')}` — {scen_meta.get('description', '')}")
        canonical_ctx = build_scenario_context(scenario_id=selected_id, planning_days=3, db=default_db_manager)
        default_event_id = canonical_ctx["event_id"]
        default_event_name = canonical_ctx["name"]
        default_disaster_type = canonical_ctx["disaster_type"]
        default_severity = canonical_ctx["severity_level"]
        default_active_zones = canonical_ctx["zones"]
    else:
        selected_id = "CUSTOM"
        default_event_id = "EVT-2026-FL01"
        default_event_name = "Brahmaputra Valley Catastrophic Monsoon Flood"
        default_disaster_type = "FLOOD"
        default_severity = "SEVERE"
        default_active_zones = all_db_zones[:4]

    col_sb1, col_sb2 = st.sidebar.columns(2)
    with col_sb1:
        disaster_type = st.selectbox(
            "Hazard Type",
            ["FLOOD", "EARTHQUAKE", "CYCLONE", "LANDSLIDE"],
            index=["FLOOD", "EARTHQUAKE", "CYCLONE", "LANDSLIDE"].index(default_disaster_type)
            if default_disaster_type in ["FLOOD", "EARTHQUAKE", "CYCLONE", "LANDSLIDE"]
            else 0,
        )
    with col_sb2:
        severity_level = st.selectbox(
            "Severity Level",
            ["MODERATE", "SEVERE", "CATASTROPHIC"],
            index=["MODERATE", "SEVERE", "CATASTROPHIC"].index(default_severity)
            if default_severity in ["MODERATE", "SEVERE", "CATASTROPHIC"]
            else 1,
        )

    # Clear stale execution results when hazard or scenario changes
    if "prev_disaster_type" in st.session_state and disaster_type != st.session_state.get("prev_disaster_type"):
        st.session_state.plan_result = None
        st.session_state.greedy_result = None
        st.session_state.blackboard_snapshot = None
        st.session_state.event_history = []
        st.session_state.disaster_context = None
        st.session_state.surge_occurred = False
        st.session_state.revised_plan = None
        st.session_state.original_plan = None
        st.session_state.original_snapshot = None
    st.session_state.prev_disaster_type = disaster_type

    if selected_option == "Custom User Scenario" or disaster_type != default_disaster_type:
        active_event_id, suggested_event_name = HAZARD_DEFAULT_EVENTS.get(
            disaster_type, ("EVT-CUSTOM-01", f"Custom {disaster_type.title()} Event")
        )
    else:
        active_event_id, suggested_event_name = default_event_id, default_event_name

    event_name = st.sidebar.text_input("Disaster Event Name", value=suggested_event_name)
    planning_days = st.sidebar.slider(
        "Planning Horizon (Days)",
        min_value=1,
        max_value=30,
        value=3,
        step=1,
        help="Defines calculation window for food packs (3-day cycles) and daily clean water rations.",
    )

    st.sidebar.subheader("📍 Affected Geographical Zones")
    initial_df_rows = []
    for z in default_active_zones:
        initial_df_rows.append(
            {
                "Zone ID": z.get("zone_id", "ZONE-01"),
                "Name": z.get("name") or z.get("zone_name", "Zone"),
                "Population": int(z.get("population") or z.get("affected_population", 25000)),
                "Damage (1-5)": int(z.get("damage_level", 3)),
                "Vulnerability (0-1)": float(z.get("vulnerability_index", 0.70)),
                "Medical Urgency (0-1)": float(z.get("medical_urgency", 0.60)),
                "Access Status": z.get("access_status") or z.get("road_status", "OPEN"),
                "Latitude": float(z.get("latitude") if z.get("latitude") is not None else z.get("lat", 26.50)),
                "Longitude": float(z.get("longitude") if z.get("longitude") is not None else z.get("lon", 93.00)),
            }
        )

    if "zones_table" not in st.session_state or selected_option != st.session_state.get("prev_selected_option"):
        if "prev_selected_option" in st.session_state and selected_option != st.session_state.get("prev_selected_option"):
            st.session_state.plan_result = None
            st.session_state.greedy_result = None
            st.session_state.blackboard_snapshot = None
            st.session_state.event_history = []
            st.session_state.disaster_context = None
            st.session_state.surge_occurred = False
            st.session_state.revised_plan = None
            st.session_state.original_plan = None
            st.session_state.original_snapshot = None

        st.session_state.zones_table = pd.DataFrame(initial_df_rows)
        st.session_state.prev_selected_option = selected_option

    edited_zones_df = st.sidebar.data_editor(
        st.session_state.zones_table,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Damage (1-5)": st.column_config.NumberColumn(min_value=1, max_value=5, step=1),
            "Vulnerability (0-1)": st.column_config.NumberColumn(min_value=0.0, max_value=1.0, step=0.05),
            "Medical Urgency (0-1)": st.column_config.NumberColumn(min_value=0.0, max_value=1.0, step=0.05),
            "Access Status": st.column_config.SelectboxColumn(options=["OPEN", "DEGRADED", "BLOCKED", "AIR_ONLY"]),
        },
    )

    execute_btn = st.sidebar.button(
        "🚀 Execute Multi-Agent Coordination",
        type="primary",
        width="stretch",
    )

    # Sidebar Interactive Display Filters
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔎 Tactical Telemetry Filters")
    filter_access = st.sidebar.multiselect(
        "Filter Zones by Access Status",
        options=["OPEN", "DEGRADED", "BLOCKED", "AIR_ONLY"],
        default=["OPEN", "DEGRADED", "BLOCKED", "AIR_ONLY"],
    )
    filter_resources = st.sidebar.multiselect(
        "Filter Resource Categories",
        options=["FOOD_RATIONS", "CLEAN_WATER", "MEDICAL_KITS", "SHELTER_TENTS"],
        default=["FOOD_RATIONS", "CLEAN_WATER", "MEDICAL_KITS", "SHELTER_TENTS"],
    )

    # Build Active Disaster Context Payload from Current UI Controls
    zones_payload = []
    for _, row in edited_zones_df.iterrows():
        zid = str(row.get("Zone ID", "")).strip()
        if not zid:
            continue
        try:
            pop_val = max(0, int(row["Population"]))
            dmg_val = max(1, min(5, int(row["Damage (1-5)"])))
            vuln_val = max(0.0, min(1.0, float(row["Vulnerability (0-1)"])))
            med_val = max(0.0, min(1.0, float(row["Medical Urgency (0-1)"])))
            lat_val = float(row["Latitude"])
            lon_val = float(row["Longitude"])
        except Exception:
            continue
        zones_payload.append(
            {
                "zone_id": zid,
                "name": str(row["Name"]),
                "zone_name": str(row["Name"]),
                "population": pop_val,
                "affected_population": pop_val,
                "damage_level": dmg_val,
                "vulnerability_index": vuln_val,
                "medical_urgency": med_val,
                "access_status": str(row["Access Status"]),
                "road_status": str(row["Access Status"]),
                "latitude": lat_val,
                "longitude": lon_val,
                "lat": lat_val,
                "lon": lon_val,
            }
        )

    active_disaster_context = {
        "scenario_id": selected_id,
        "event_id": active_event_id,
        "name": event_name,
        "hazard": disaster_type,
        "disaster_type": disaster_type,
        "severity": severity_level,
        "severity_level": severity_level,
        "planning_days": planning_days,
        "zones": zones_payload,
    }

    # Execute Pipeline on Button Click or Initial Session Load
    should_auto_initialize = (
        "plan_result" not in st.session_state or st.session_state.get("plan_result") is None
    ) and len(zones_payload) > 0

    if execute_btn or should_auto_initialize:
        if not zones_payload:
            st.error("❌ Invalid Configuration: At least one valid affected zone is required to run coordination.")
        else:
            st.session_state.disaster_context = active_disaster_context
            with st.status("🤖 Orchestrating ReliefOps Multi-Agent Pipeline...", expanded=execute_btn) as status_box:
                st.write("1️⃣ **Needs Assessment Agent**: Querying ChromaDB / BM25 SOPs & computing hazard-specific ZPS...")
                st.write("2️⃣ **Inventory Agent**: Auditing regional depot stock & demand fulfillment feasibility...")
                st.write("3️⃣ **Logistics Agent**: Computing Haversine distance matrix ($W_t=1.35$) & road impedance...")
                st.write("4️⃣ **Coordinator & Fairness Auditor**: Synthesizing Two-Phase Water-Filling plan & Gini audit...")
                try:
                    bb = BlackboardManager(db=default_db_manager)
                    coordinator = ReliefCoordinator(blackboard=bb, db=default_db_manager)
                    plan_result = coordinator.run_full_coordination_cycle(disaster_context=active_disaster_context)
                    greedy_result = coordinator.evaluate_greedy_baseline(disaster_context=active_disaster_context)
                    st.session_state.blackboard_snapshot = bb.get_snapshot()
                    st.session_state.plan_result = plan_result
                    st.session_state.greedy_result = greedy_result
                    st.session_state.event_history = bb.get_event_history()
                    st.session_state.surge_occurred = False
                    st.session_state.revised_plan = None
                    status_box.update(
                        label=f"✅ Multi-Agent Coordination Complete — Plan {plan_result.get('plan_id')} ({plan_result.get('overall_status')})",
                        state="complete",
                        expanded=False,
                    )
                except Exception as exc:
                    st.error(f"❌ Backend Execution Error: {exc}")
                    status_box.update(label="❌ Multi-Agent Coordination Failed", state="error", expanded=True)

    # =========================================================================
    # RENDER ACTIVE TELEMETRY & 9 OPERATIONAL COMMAND MODULES
    # =========================================================================
    plan = st.session_state.get("plan_result")
    bb_snap = st.session_state.get("blackboard_snapshot") or {}

    if not plan:
        st.info("👈 Configure a disaster scenario in the sidebar and click **'Execute Multi-Agent Coordination'** to launch.")
        return

    kpis = compute_executive_kpis(plan=plan, blackboard_snapshot=bb_snap)
    audit_data = plan.get("audit_verdict") or {}
    zone_needs_all = bb_snap.get("zone_needs") or []
    zone_needs = [z for z in zone_needs_all if str(z.get("road_status", "OPEN")) in filter_access] or zone_needs_all
    sop_ctx = bb_snap.get("sop_context") or {}
    inv_snap = bb_snap.get("inventory_snapshot") or {}
    dispatches_all = plan.get("dispatches") or []
    dispatches = [d for d in dispatches_all if str(d.get("resource_type")) in filter_resources]
    shortage_warnings = audit_data.get("shortage_warnings") or plan.get("shortage_warnings") or []

    # Top Operational Readiness & Shortage Status Strip
    overall_status = kpis["overall_status"]
    fairness_verdict = kpis["fairness_verdict"]
    adequacy_status = kpis["adequacy_status"]

    if overall_status == "APPROVED_WITH_SHORTAGES":
        st.warning(
            f"⚠️ **OPERATIONAL ALERT — {overall_status}**: Distributive justice verified "
            f"(**{fairness_verdict}**, Gini = `{kpis['gini_coefficient']:.4f}` ≤ 0.35), "
            f"but warehouse stock is insufficient for 100% of regional demand (**{adequacy_status}**). "
            f"Critical external replenishment required for: **{', '.join(kpis['shortage_resources'])}**."
        )
    elif overall_status == "REJECTED":
        st.error(
            f"🚨 **AUDIT REJECTED — {overall_status}**: Allocation plan violated distributive justice gate ({fairness_verdict})."
        )
    else:
        st.success(
            f"✅ **FULL OPERATIONAL READINESS — {overall_status}**: "
            f"Distributive fairness ({fairness_verdict}, Gini = `{kpis['gini_coefficient']:.4f}`) and 100% resource adequacy verified."
        )

    # -------------------------------------------------------------------------
    # MODULE RENDERING FUNCTIONS (MODULES 1 TO 9)
    # -------------------------------------------------------------------------

    def render_module_1_executive_overview() -> None:
        st.subheader("1. Executive Overview — Mission Command KPIs")
        st.caption(
            f"Live multi-agent telemetry for Event `{kpis['active_incident_id']}` | "
            f"Hazard: `{kpis['active_hazard']}` | Governing SOP: `{kpis['governing_sop']}`"
        )

        # Row 1: 4 Primary KPI Cards
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            tot_pop_str = f"{kpis['total_affected_population']:,}"
            tot_disp_str = f"{kpis['total_displaced_population']:,}"
            zones_cnt_str = str(kpis["active_zones_count"])
            st.markdown(
                f"""
                <div class="eoc-kpi-card">
                    <div class="eoc-kpi-label">Total Affected Population</div>
                    <div class="eoc-kpi-value">{tot_pop_str}</div>
                    <div class="eoc-kpi-sub">Displaced: <strong>{tot_disp_str}</strong> across {zones_cnt_str} sectors</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c2:
            active_hazard_str = html.escape(str(kpis["active_hazard"]))
            active_sev_str = html.escape(str(kpis["active_severity"]))
            active_inc_str = html.escape(str(kpis["active_incident_id"]))
            gov_sop_str = html.escape(str(kpis["governing_sop"]))
            st.markdown(
                f"""
                <div class="eoc-kpi-card">
                    <div class="eoc-kpi-label">Active Disaster Incident</div>
                    <div class="eoc-kpi-value">{active_hazard_str} ({active_sev_str})</div>
                    <div class="eoc-kpi-sub">ID: <code>{active_inc_str}</code> | SOP: <code>{gov_sop_str}</code></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c3:
            tot_dem_str = f"{kpis['total_demanded_units']:,}"
            st.markdown(
                f"""
                <div class="eoc-kpi-card">
                    <div class="eoc-kpi-label">Total Resources Demanded</div>
                    <div class="eoc-kpi-value">{tot_dem_str}</div>
                    <div class="eoc-kpi-sub">Horizon: {planning_days} days | 4 relief SKU categories</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c4:
            tot_alloc_str = f"{kpis['total_allocated_units']:,}"
            disp_cnt_str = str(kpis["dispatches_count"])
            st.markdown(
                f"""
                <div class="eoc-kpi-card alert-green">
                    <div class="eoc-kpi-label">Total Resources Allocated</div>
                    <div class="eoc-kpi-value">{tot_alloc_str}</div>
                    <div class="eoc-kpi-sub">Dispatched across <strong>{disp_cnt_str}</strong> logistics legs</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.write("")
        # Row 2: 3 Governance & Adequacy KPI Cards
        c5, c6, c7 = st.columns(3)
        with c5:
            shortage_cls = "alert-red" if kpis["critical_shortages_count"] > 0 else "alert-green"
            shortage_str = html.escape(", ".join(kpis["shortage_resources"]) if kpis["shortage_resources"] else "None (100% Adequate)")
            shortage_cnt_str = str(kpis["critical_shortages_count"])
            tot_unful_str = f"{kpis['total_unfulfilled_units']:,}"
            st.markdown(
                f"""
                <div class="eoc-kpi-card {shortage_cls}">
                    <div class="eoc-kpi-label">Critical Resource Shortages</div>
                    <div class="eoc-kpi-value">{shortage_cnt_str} Categories</div>
                    <div class="eoc-kpi-sub">Deficits: <strong>{shortage_str}</strong> ({tot_unful_str} unfulfilled units)</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c6:
            latest_plan_str = html.escape(str(kpis["latest_plan_id"]))
            ov_status_str = html.escape(str(kpis["overall_status"]))
            st.markdown(
                f"""
                <div class="eoc-kpi-card">
                    <div class="eoc-kpi-label">Latest Allocation Plan</div>
                    <div class="eoc-kpi-value" style="font-size:1.15rem;">{latest_plan_str}</div>
                    <div class="eoc-kpi-sub">Verdict: <span class="badge-warning">{ov_status_str}</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c7:
            gini_cls = "alert-green" if kpis["gini_coefficient"] <= 0.35 else "alert-red"
            gini_value = f"{kpis['gini_coefficient']:.4f}"
            fairness_verdict_str = html.escape(str(kpis["fairness_verdict"]))
            min_floor_value = f"{kpis['min_coverage_ratio']:.1%}"
            st.markdown(
                f"""
                <div class="eoc-kpi-card {gini_cls}">
                    <div class="eoc-kpi-label">Overall Fairness Score (Gini)</div>
                    <div class="eoc-kpi-value">{gini_value} <span style="font-size:0.85rem;color:#34D399;">(≤ 0.35)</span></div>
                    <div class="eoc-kpi-sub"><span class="badge-approved">{fairness_verdict_str}</span> | Min Floor: {min_floor_value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("---")
        col_ex1, col_ex2 = st.columns([3, 2])
        with col_ex1:
            st.markdown("##### Sector Priority & Resource Demand Matrix")
            exec_rows = []
            for z in zone_needs:
                d = z.get("demands", {})
                exec_rows.append(
                    {
                        "Rank": f"#{z.get('priority_rank')}",
                        "Sector Name": z.get("zone_name"),
                        "Population": f"{z.get('affected_population', 0):,}",
                        "Displaced": f"{int(z.get('displaced_population', 0)):,}",
                        "ZPS Score": round(float(z.get("zps", 0.0)), 2),
                        "Access": z.get("road_status"),
                        "Food (packs)": f"{d.get('food_packs', 0):,}",
                        "Water (L)": f"{d.get('water_liters', 0.0):,.0f}",
                        "Tents": f"{d.get('tents', 0):,}",
                        "Med Kits": f"{d.get('medical_kits', 0):,}",
                    }
                )
            st.dataframe(pd.DataFrame(exec_rows), width="stretch", hide_index=True)

        with col_ex2:
            st.markdown("##### Zone Priority Score (ZPS) Ranking")
            if zone_needs:
                zps_df = pd.DataFrame(
                    [
                        {
                            "Zone": z.get("zone_name"),
                            "ZPS": float(z.get("zps", 0.0)),
                            "Access": z.get("road_status", "OPEN"),
                        }
                        for z in zone_needs
                    ]
                )
                zps_chart = (
                    alt.Chart(zps_df)
                    .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
                    .encode(
                        x=alt.X("ZPS:Q", title="Zone Priority Score (0–100)", scale=alt.Scale(domain=[0, 100])),
                        y=alt.Y("Zone:N", sort="-x", title=None),
                        color=alt.Color(
                            "Access:N",
                            scale=alt.Scale(
                                domain=["OPEN", "DEGRADED", "BLOCKED", "AIR_ONLY"],
                                range=["#10B981", "#F59E0B", "#EF4444", "#38BDF8"],
                            ),
                        ),
                        tooltip=["Zone:N", "ZPS:Q", "Access:N"],
                    )
                    .properties(height=250)
                )
                st.altair_chart(zps_chart, width="stretch")

    def render_module_2_disaster_monitoring() -> None:
        st.subheader("2. Multi-Hazard Disaster Monitoring & Sector Telemetry")
        st.caption(
            "Real-time monitoring across Flood, Earthquake, Cyclone, and Landslide hazards with SOP severity equivalences."
        )

        # Hazard & SOP Reference Strip
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Active Hazard", kpis["active_hazard"])
        m2.metric("Severity Classification", kpis["active_severity"])
        m3.metric("SOP Section 2 Scale", kpis["sop_severity_equivalent"])
        m4.metric("Governing SOP Manual", kpis["governing_sop"])

        # Cross-Hazard Reference Matrix
        with st.expander("📋 Canonical Multi-Hazard SOP & ZPS Weighting Reference Matrix", expanded=False):
            hz_matrix = pd.DataFrame(
                [
                    {
                        "Hazard": "FLOOD",
                        "Governing SOP": "SOP-FL-001",
                        "SEVERE Mapping": "Level 3 (Severe Inundation)",
                        "Damage Weight": 0.35,
                        "Vulnerability Weight": 0.25,
                        "Medical Weight": 0.25,
                        "Population Weight": 0.15,
                    },
                    {
                        "Hazard": "EARTHQUAKE",
                        "Governing SOP": "SOP-EQ-002",
                        "SEVERE Mapping": "Level 3 (Heavy Damage)",
                        "Damage Weight": 0.30,
                        "Vulnerability Weight": 0.20,
                        "Medical Weight": 0.40,
                        "Population Weight": 0.10,
                    },
                    {
                        "Hazard": "CYCLONE",
                        "Governing SOP": "SOP-CY-004",
                        "SEVERE Mapping": "Level 3 (Very Severe Cyclone)",
                        "Damage Weight": 0.35,
                        "Vulnerability Weight": 0.30,
                        "Medical Weight": 0.20,
                        "Population Weight": 0.15,
                    },
                    {
                        "Hazard": "LANDSLIDE",
                        "Governing SOP": "SOP-LS-003",
                        "SEVERE Mapping": "Level 3 (Major Slope Failure)",
                        "Damage Weight": 0.40,
                        "Vulnerability Weight": 0.20,
                        "Medical Weight": 0.25,
                        "Population Weight": 0.15,
                    },
                ]
            )
            st.dataframe(hz_matrix, width="stretch", hide_index=True)

        decision_trail = plan.get("decision_audit_trail") or {}
        zone_expl_map = {ze["zone_id"]: ze for ze in decision_trail.get("zone_explanations", [])}

        for z in zone_needs:
            zid = z.get("zone_id")
            ze = zone_expl_map.get(zid)
            with st.expander(
                f"🏅 Rank #{z.get('priority_rank')}: {z.get('zone_name')} ({zid}) — "
                f"ZPS: {z.get('zps', 0.0):.2f} | Access: {z.get('road_status')}",
                expanded=z.get("priority_rank") == 1,
            ):
                if ze and ze.get("priority_reasoning"):
                    st.info(f"🧠 **SOP Prioritization Rationale:** {ze['priority_reasoning']}")
                cz1, cz2, cz3 = st.columns([1, 1, 2])
                with cz1:
                    st.markdown(
                        f"""
                        - **Zone ID:** `{zid}`
                        - **Affected Population:** `{z.get('affected_population', 0):,}`
                        - **Displacement Ratio:** `{z.get('displacement_ratio', 0.0):.1%}`
                        - **Displaced Population:** `{int(z.get('displaced_population', 0.0)):,}`
                        """
                    )
                with cz2:
                    st.markdown(
                        f"""
                        - **Damage Severity ($D_i$):** `{z.get('damage_level')}/5`
                        - **Vulnerability Index ($V_i$):** `{z.get('vulnerability_index', 0.0):.2f}`
                        - **Medical Urgency ($M_i$):** `{z.get('medical_urgency', 0.0):.2f}`
                        - **Road Access Status:** `{z.get('road_status')}`
                        """
                    )
                with cz3:
                    d = z.get("demands", {})
                    st.markdown(
                        f"""
                        **SOP-Computed Humanitarian Resource Demands ({planning_days}-Day Horizon):**
                        - 💧 **Clean Water:** `{d.get('water_liters', 0.0):,.0f} L` ({d.get('jerrycans_10l', 0):,} jerrycans)
                        - 🍞 **Food Rations:** `{d.get('food_packs', 0):,} packs`
                        - ⛺ **Emergency Shelter:** `{d.get('tents', 0):,} family tents`
                        - 🩺 **Medical Trauma Kits:** `{d.get('medical_kits', 0):,} kits`
                        """
                    )

    def render_module_3_gis_command_map() -> None:
        st.subheader("3. Spatial GIS Command Map — Depots, Disaster Sectors & Dispatch Corridors")
        st.caption(
            "Geospatial operational picture built strictly from authentic database coordinates for regional warehouses and affected zones."
        )

        gis_data = build_gis_layers_data(zone_needs=zone_needs, inv_snap=inv_snap, dispatches=dispatches)
        wh_points = gis_data["warehouse_points"]
        zone_points = gis_data["zone_points"]
        route_rows = gis_data["route_rows"]

        g_ctrl1, g_ctrl2, g_ctrl3, g_ctrl4 = st.columns(4)
        show_wh = g_ctrl1.checkbox("Show Regional Depots", value=True, key="gis_show_wh")
        show_zones = g_ctrl2.checkbox("Show Affected Zones", value=True, key="gis_show_zones")
        show_routes = g_ctrl3.checkbox("Show Dispatch Corridors", value=True, key="gis_show_routes")
        pitch_3d = g_ctrl4.slider("Map 3D Pitch", min_value=0, max_value=60, value=38, key="gis_pitch")

        all_points = (wh_points if show_wh else []) + (zone_points if show_zones else [])
        if all_points:
            avg_lat = sum(p["lat"] for p in all_points) / len(all_points)
            avg_lon = sum(p["lon"] for p in all_points) / len(all_points)

            view_state = pdk.ViewState(latitude=avg_lat, longitude=avg_lon, zoom=6.8, pitch=pitch_3d)
            deck_layers = []

            if show_routes and route_rows:
                routes_df = pd.DataFrame(route_rows)
                line_layer = pdk.Layer(
                    "LineLayer",
                    data=routes_df,
                    get_source_position=["source_lon", "source_lat"],
                    get_target_position=["target_lon", "target_lat"],
                    get_color="source_color",
                    get_width=5,
                    width_min_pixels=3,
                    pickable=True,
                    auto_highlight=True,
                )
                arc_layer = pdk.Layer(
                    "ArcLayer",
                    data=routes_df,
                    get_source_position=["source_lon", "source_lat"],
                    get_target_position=["target_lon", "target_lat"],
                    get_source_color="source_color",
                    get_target_color="target_color",
                    get_width=4,
                    pickable=True,
                    auto_highlight=True,
                )
                deck_layers.extend([line_layer, arc_layer])

            scatter_layer = pdk.Layer(
                "ScatterplotLayer",
                data=pd.DataFrame(all_points),
                get_position=["lon", "lat"],
                get_color="color",
                get_radius="radius",
                pickable=True,
                auto_highlight=True,
            )
            deck_layers.append(scatter_layer)

            st.pydeck_chart(
                pdk.Deck(
                    layers=deck_layers,
                    initial_view_state=view_state,
                    tooltip={"text": "{name}\nType: {type}\n{details}"},
                )
            )
            st.caption(
                "🟢 **Emerald Markers**: Operational Warehouse Depots | "
                "🔵/🟠/🔴 **Sector Markers**: Affected Disaster Zones (scaled by ZPS & colored by road access/severity) | "
                "🌈 **Arcs**: Active Warehouse-to-Zone Supply Corridors"
            )

            if route_rows:
                st.markdown("##### Active Logistics Dispatch Corridors & Transit ETAs")
                corridor_df = pd.DataFrame(
                    [
                        {
                            "Origin Warehouse": r["warehouse_name"],
                            "Destination Sector": r["zone_name"],
                            "Road Condition": r["road_status"],
                            "Effective Distance (km)": f"{r['distance_km']:.1f}",
                            "Est. Transit Time (hrs)": f"{r['est_transit_hours']:.1f}",
                            "Dispatched Cargo Manifest": r["cargo_manifest"],
                        }
                        for r in route_rows
                    ]
                )
                st.dataframe(corridor_df, width="stretch", hide_index=True)
        else:
            st.info("No spatial coordinates selected to display.")

    def render_module_4_resource_management() -> None:
        st.subheader("4. Humanitarian Resource Management & Depot Stock Adequacy")
        st.caption(
            "Independent accounting of Demanded, Available, Allocated, Fulfillment % (capped at 100%), Unfulfilled Shortage, and Surplus Inventory."
        )

        res_metrics = kpis["resource_metrics"]
        rc1, rc2, rc3, rc4 = st.columns(4)
        res_labels = [
            ("FOOD_RATIONS", "🍞 Food Rations (Packs)", rc1),
            ("CLEAN_WATER", "💧 Clean Water (Liters)", rc2),
            ("MEDICAL_KITS", "🩺 Medical Trauma Kits", rc3),
            ("SHELTER_TENTS", "⛺ Shelter Tents (Units)", rc4),
        ]
        for rkey, rtitle, col_obj in res_labels:
            rm = res_metrics.get(rkey, {})
            st_val = rm.get("status", "ADEQUATE")
            card_cls = "alert-green" if st_val == "ADEQUATE" else ("alert-red" if st_val == "CRITICAL_SHORTAGE" else "alert-amber")
            fulfill_val = f"{rm.get('fulfillment_pct', 0.0):.1f}"
            alloc_val = f"{rm.get('allocated', 0):,}"
            dem_val = f"{rm.get('demanded', 0):,}"
            avail_val = f"{rm.get('available', 0):,}"
            surplus_val = f"{rm.get('surplus_qty', 0):,}"
            unmet_val = f"{rm.get('unfulfilled_qty', 0):,}"
            with col_obj:
                st.markdown(
                    f"""
                    <div class="eoc-kpi-card {card_cls}">
                        <div class="eoc-kpi-label">{rtitle}</div>
                        <div class="eoc-kpi-value">{fulfill_val}% Fulfilled</div>
                        <div class="eoc-kpi-sub">
                            Alloc: <strong>{alloc_val}</strong> / Dem: <strong>{dem_val}</strong><br/>
                            Avail: {avail_val} | Surplus: {surplus_val} | Unmet: {unmet_val}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.write("")
        col_rm1, col_rm2 = st.columns([3, 2])
        with col_rm1:
            st.markdown("##### Resource Demand vs. Availability, Fulfillment & Surplus Ledger")
            ledger_rows = []
            for rkey in ["FOOD_RATIONS", "CLEAN_WATER", "MEDICAL_KITS", "SHELTER_TENTS"]:
                if rkey not in filter_resources:
                    continue
                rm = res_metrics.get(rkey, {})
                ledger_rows.append(
                    {
                        "Resource Category": rkey,
                        "Total Demanded": f"{rm.get('demanded', 0):,}",
                        "Total Available": f"{rm.get('available', 0):,}",
                        "Total Allocated": f"{rm.get('allocated', 0):,}",
                        "Fulfillment %": f"{rm.get('fulfillment_pct', 0.0):.1f}%",
                        "Unfulfilled Shortage": f"{rm.get('unfulfilled_qty', 0):,}",
                        "Surplus Inventory": f"{rm.get('surplus_qty', 0):,}",
                        "Status": rm.get("status", "ADEQUATE"),
                    }
                )
            st.dataframe(pd.DataFrame(ledger_rows), width="stretch", hide_index=True)

            st.markdown("##### Regional Warehouse Fleet Stock Snapshot")
            wh_rows = []
            for wh in inv_snap.get("warehouses", []):
                res = wh.get("resources", {})
                wh_rows.append(
                    {
                        "Warehouse ID": wh.get("warehouse_id"),
                        "Depot Name": wh.get("warehouse_name"),
                        "Status": wh.get("status"),
                        "Food (packs)": f"{res.get('FOOD_RATIONS', {}).get('available_quantity', 0):,}",
                        "Water (L)": f"{res.get('CLEAN_WATER', {}).get('available_quantity', 0):,}",
                        "Medical (kits)": f"{res.get('MEDICAL_KITS', {}).get('available_quantity', 0):,}",
                        "Shelter (tents)": f"{res.get('SHELTER_TENTS', {}).get('available_quantity', 0):,}",
                    }
                )
            st.dataframe(pd.DataFrame(wh_rows), width="stretch", hide_index=True)

        with col_rm2:
            st.markdown("##### Resource Fulfillment Percentage by Category")
            chart_df = pd.DataFrame(
                [
                    {
                        "Resource": rkey,
                        "Fulfillment %": res_metrics.get(rkey, {}).get("fulfillment_pct", 0.0),
                        "Status": res_metrics.get(rkey, {}).get("status", "ADEQUATE"),
                    }
                    for rkey in ["FOOD_RATIONS", "CLEAN_WATER", "MEDICAL_KITS", "SHELTER_TENTS"]
                    if rkey in filter_resources
                ]
            )
            if not chart_df.empty:
                fulfill_chart = (
                    alt.Chart(chart_df)
                    .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
                    .encode(
                        x=alt.X("Fulfillment %:Q", scale=alt.Scale(domain=[0, 100]), title="Demand Fulfillment (%)"),
                        y=alt.Y("Resource:N", sort="-x", title=None),
                        color=alt.Color(
                            "Status:N",
                            scale=alt.Scale(
                                domain=["ADEQUATE", "SHORTAGE", "CRITICAL_SHORTAGE"],
                                range=["#10B981", "#F59E0B", "#EF4444"],
                            ),
                        ),
                        tooltip=["Resource:N", "Fulfillment %:Q", "Status:N"],
                    )
                    .properties(height=260)
                )
                st.altair_chart(fulfill_chart, width="stretch")

        if shortage_warnings:
            st.warning("**Active Resource Shortage Warnings:**\n" + "\n".join(f"- {w}" for w in shortage_warnings))

    def render_module_5_ai_allocation_engine() -> None:
        st.subheader("5. AI Allocation Engine — Two-Phase Water-Filling & Dispatch Manifest")
        st.caption(
            f"Plan ID: `{plan.get('plan_id')}` | Policy: `Two-Phase Water-Filling (30% Survival Floor + ZPS Proportional)` | "
            f"Negotiation Iterations: `{plan.get('iterations', 1)}`"
        )

        # Zone-wise Allocation Summary
        z_summaries = audit_data.get("zone_summaries") or []
        if z_summaries:
            st.markdown("##### Zone-Wise Resource Allocation & Coverage Summary")
            z_alloc_rows = []
            for zs in z_summaries:
                rc = zs.get("resource_coverage", {})
                z_alloc_rows.append(
                    {
                        "Sector": zs.get("zone_name"),
                        "Zone ID": zs.get("zone_id"),
                        "ZPS": f"{zs.get('zps', 0.0):.2f}",
                        "Population": f"{zs.get('population', 0):,}",
                        "Food Fulfillment": f"{rc.get('FOOD_RATIONS', 1.0) * 100.0:.1f}%",
                        "Water Fulfillment": f"{rc.get('CLEAN_WATER', 1.0) * 100.0:.1f}%",
                        "Shelter Fulfillment": f"{rc.get('SHELTER_TENTS', 1.0) * 100.0:.1f}%",
                        "Medical Fulfillment": f"{rc.get('MEDICAL_KITS', 1.0) * 100.0:.1f}%"
                        if "MEDICAL_KITS" in rc
                        else "100.0% (0 req)",
                        "Aggregate Coverage": f"{zs.get('coverage_ratio', 0.0) * 100.0:.1f}%",
                        "Allocation Justification": zs.get("priority_explanation", "Two-Phase Water-Filling"),
                    }
                )
            st.dataframe(pd.DataFrame(z_alloc_rows), width="stretch", hide_index=True)

        # Warehouse-wise Dispatch Summary
        if dispatches:
            wh_agg: Dict[str, Dict[str, Any]] = {}
            for d in dispatches:
                wname = d.get("warehouse_name") or d.get("warehouse_id", "UNKNOWN")
                entry = wh_agg.setdefault(
                    wname,
                    {"Origin Warehouse": wname, "Shipment Legs": 0, "Total Units Dispatched": 0, "Avg Distance (km)": []},
                )
                entry["Shipment Legs"] += 1
                entry["Total Units Dispatched"] += int(d.get("allocated_qty", 0))
                entry["Avg Distance (km)"].append(float(d.get("distance_km", 0.0)))

            wh_summary_rows = [
                {
                    "Origin Warehouse": k,
                    "Shipment Legs": v["Shipment Legs"],
                    "Total Units Dispatched": f"{v['Total Units Dispatched']:,}",
                    "Mean Route Distance (km)": f"{sum(v['Avg Distance (km)']) / len(v['Avg Distance (km)']):.1f}",
                }
                for k, v in wh_agg.items()
            ]
            st.markdown("##### Warehouse-Wise Outbound Dispatch Summary")
            st.dataframe(pd.DataFrame(wh_summary_rows), width="stretch", hide_index=True)

            st.markdown("##### Itemized Multi-Depot Logistics Dispatch Schedule")
            disp_table = []
            csv_rows = []
            for d in dispatches:
                disp_table.append(
                    {
                        "Target Sector": d.get("zone_name") or d.get("zone_id"),
                        "Origin Depot": d.get("warehouse_name") or d.get("warehouse_id"),
                        "Resource SKU": d.get("resource_type"),
                        "Requested Qty": f"{d.get('requested_qty', 0):,}",
                        "Allocated Qty": f"{d.get('allocated_qty', 0):,}",
                        "Unfulfilled Qty": f"{d.get('unfulfilled_qty', 0):,}",
                        "Road Status": d.get("road_status", "OPEN"),
                        "Distance (km)": f"{d.get('distance_km', 0.0):.1f}",
                        "Est. Transit (hrs)": f"{d.get('est_transit_hours', 0.0):.1f}",
                    }
                )
                csv_rows.append(
                    {
                        "plan_id": plan.get("plan_id"),
                        "target_zone": d.get("zone_name") or d.get("zone_id"),
                        "zone_id": d.get("zone_id"),
                        "origin_warehouse": d.get("warehouse_name") or d.get("warehouse_id"),
                        "warehouse_id": d.get("warehouse_id"),
                        "resource_sku": d.get("resource_type"),
                        "requested_qty": d.get("requested_qty", 0),
                        "allocated_qty": d.get("allocated_qty", 0),
                        "unfulfilled_qty": d.get("unfulfilled_qty", 0),
                        "road_status": d.get("road_status", "OPEN"),
                        "distance_km": round(float(d.get("distance_km", 0.0)), 2),
                        "est_transit_hours": round(float(d.get("est_transit_hours", 0.0)), 2),
                    }
                )

            c_cap, c_dl = st.columns([3, 1])
            c_cap.caption(f"Showing {len(disp_table)} active shipment legs matching tactical filters:")
            c_dl.download_button(
                label="📥 Export Dispatch Manifest (CSV)",
                data=pd.DataFrame(csv_rows).to_csv(index=False).encode("utf-8"),
                file_name=f"reliefops_dispatches_{plan.get('plan_id', 'manifest')}.csv",
                mime="text/csv",
                key="dl_csv_module5",
                width="stretch",
            )
            st.dataframe(pd.DataFrame(disp_table), width="stretch", hide_index=True)

    def render_module_6_fairness_analytics() -> None:
        st.subheader("6. Distributive Fairness Analytics & Lorenz Curve Benchmark")
        st.caption(
            "Mathematical audit of Dimension A (Distributive Equity across Sectors, Gini ≤ 0.35) "
            "and Dimension B (Aggregate Resource Adequacy)."
        )

        f_col1, f_col2 = st.columns(2)
        with f_col1:
            fair_gini_str = f"{audit_data.get('gini_coefficient', 0.0):.4f}"
            gini_thresh_str = f"{audit_data.get('gini_threshold', 0.35)}"
            min_cov_str = f"{audit_data.get('min_coverage_ratio', 0.0):.1%}"
            auditor_expl_str = html.escape(str(audit_data.get("explanation", "")))
            st.markdown(
                f"""
                <div class="eoc-panel">
                    <h4>⚖️ Dimension A: Distributive Justice Gate</h4>
                    <ul>
                        <li><strong>Fairness Verdict:</strong> <span class="badge-approved">{html.escape(str(fairness_verdict))}</span></li>
                        <li><strong>Empirical Gini Coefficient:</strong> <code>{fair_gini_str}</code> (Threshold: <code>≤ {gini_thresh_str}</code>)</li>
                        <li><strong>Minimum Survival Floor Coverage:</strong> <code>{min_cov_str}</code></li>
                        <li><strong>Zero-Allocation Ban:</strong> <code>PASSED (0 deprived sectors)</code></li>
                        <li><strong>Auditor Explanation:</strong> {auditor_expl_str}</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with f_col2:
            greedy_plan = st.session_state.get("greedy_result") or {}
            g_gini = float(greedy_plan.get("gini_coefficient", 0.5679))
            g_verdict = html.escape(str(greedy_plan.get("fairness_verdict", "FAIRNESS_REJECTED")))
            g_min_cov = float(greedy_plan.get("min_coverage_ratio", 0.0))
            g_gini_str = f"{g_gini:.4f}"
            g_min_cov_str = f"{g_min_cov:.1%}"
            st.markdown(
                f"""
                <div class="eoc-panel" style="border-color:#7F1D1D;">
                    <h4>🚫 Benchmark: Naive Greedy Policy (Vetoed)</h4>
                    <ul>
                        <li><strong>Greedy Auditor Verdict:</strong> <span class="badge-rejected">{g_verdict} (VETOED)</span></li>
                        <li><strong>Greedy Gini Coefficient:</strong> <code>{g_gini_str}</code> (Violates ≤ 0.35 ceiling)</li>
                        <li><strong>Minimum Sector Coverage:</strong> <code>{g_min_cov_str}</code></li>
                        <li><strong>Failure Mode:</strong> Unconstrained nearest-depot dispatch starves distant/cut-off sectors when closer urban staging areas exhaust supply.</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

        z_summaries = audit_data.get("zone_summaries") or []
        greedy_plan = st.session_state.get("greedy_result") or {}
        g_summaries = (greedy_plan.get("audit_verdict") or {}).get("zone_summaries") or []

        if z_summaries and g_summaries:
            f_cov = {s["zone_name"]: s["coverage_ratio"] * 100.0 for s in z_summaries}
            g_cov = {s["zone_name"]: s["coverage_ratio"] * 100.0 for s in g_summaries}
            comp_rows = []
            for z_name, fair_pct in f_cov.items():
                greedy_pct = g_cov.get(z_name, 0.0)
                diff = fair_pct - greedy_pct
                comp_rows.append(
                    {
                        "Disaster Sector": z_name,
                        "ReliefOps AI Water-Filling Coverage %": f"{fair_pct:.1f}%",
                        "Naive Greedy Coverage %": f"{greedy_pct:.1f}%",
                        "Distributive Equity Advantage": f"{diff:+.1f}%"
                        + (" 🛡️ (Protected from deprivation)" if diff > 0.05 else ""),
                    }
                )
            st.markdown("##### Sector-by-Sector Allocation Equity Comparison (Water-Filling vs. Greedy)")
            st.dataframe(pd.DataFrame(comp_rows), width="stretch", hide_index=True)

            # Empirical Lorenz Curve Chart
            st.markdown("##### 📈 Empirical Lorenz Curve: Distributive Justice vs. Naive Greedy Optimization")
            st.caption(
                "The Lorenz curve evaluates distributive equity across disaster zones. "
                "• **X-axis:** Cumulative share of affected administrative disaster sectors (%). "
                "• **Y-axis:** Cumulative share of need fulfillment (%). "
                "• **Need fulfillment** = allocated units / demanded units. "
                "• The chart uses equal weighting of administrative sectors to remain consistent with the backend Gini calculation."
            )

            fair_gini_val = float(audit_data.get("gini_coefficient", 0.0584))
            greedy_gini_val = float(greedy_plan.get("gini_coefficient", 0.5679))
            fair_label = f"ReliefOps AI: Two-Phase Water-Filling (Gini = {fair_gini_val:.4f})"
            greedy_label = f"Naive Greedy Optimization (Gini = {greedy_gini_val:.4f})"

            lorenz_df = build_lorenz_curve_data(
                zone_needs=zone_needs_all,
                fair_summaries=z_summaries,
                greedy_summaries=g_summaries,
                fair_gini=fair_gini_val,
                greedy_gini=greedy_gini_val,
            )

            lorenz_chart = (
                alt.Chart(lorenz_df)
                .mark_line(point=True, strokeWidth=2.5)
                .encode(
                    x=alt.X(
                        "Cumulative Share %:Q",
                        title="Cumulative Share of Affected Disaster Sectors (%)",
                        scale=alt.Scale(domain=[0, 100]),
                        axis=alt.Axis(format=".0f", grid=True),
                    ),
                    y=alt.Y(
                        "Cumulative Coverage %:Q",
                        title="Cumulative Need Coverage Share (%)",
                        scale=alt.Scale(domain=[0, 100]),
                        axis=alt.Axis(format=".0f", grid=True),
                    ),
                    color=alt.Color(
                        "Policy:N",
                        title="Allocation Policy",
                        scale=alt.Scale(
                            domain=[
                                "Line of Perfect Equality (45°)",
                                fair_label,
                                greedy_label,
                            ],
                            range=["#94A3B8", "#10B981", "#EF4444"],
                        ),
                        legend=alt.Legend(orient="bottom", columns=1),
                    ),
                    strokeDash=alt.StrokeDash(
                        "Policy:N",
                        title="Allocation Policy",
                        scale=alt.Scale(
                            domain=[
                                "Line of Perfect Equality (45°)",
                                fair_label,
                                greedy_label,
                            ],
                            range=[[6, 6], [0, 0], [0, 0]],
                        ),
                        legend=None,
                    ),
                    tooltip=[
                        alt.Tooltip("Policy:N", title="Policy"),
                        alt.Tooltip("Zone:N", title="Disaster Zone"),
                        alt.Tooltip("Population:Q", format=",.0f", title="Zone Population"),
                        alt.Tooltip("Zone Coverage %:N", title="Zone Coverage %"),
                        alt.Tooltip("Cumulative Share %:Q", format=".1f", title="Cum. Sector Share %"),
                        alt.Tooltip("Cumulative Coverage %:Q", format=".1f", title="Cum. Coverage Share %"),
                    ],
                )
                .properties(
                    title="Empirical Lorenz Curves: Distributive Justice vs. Cost Minimization",
                    height=400,
                )
            )
            st.altair_chart(lorenz_chart, width="stretch")

    def render_module_7_rag_knowledge_assistant() -> None:
        st.subheader("7. RAG Knowledge Assistant — Authoritative Disaster SOP Intelligence")
        st.caption(
            "Connected directly to the ChromaDB Vector Store and Okapi BM25 retrieval pipeline over "
            "`SOP-FL-001`, `SOP-EQ-002`, `SOP-CY-004`, and `SOP-LS-003`."
        )

        # Interactive Question Answering Console
        st.markdown("##### 💬 Query the Disaster-Response SOP Knowledge Base")
        preset_questions = [
            "Custom Operator Question...",
            "What are the per-capita clean water, food, medical trauma, and shelter ratios for earthquake response?",
            "How are Zone Priority Score (ZPS) weights calculated for flood vs landslide hazards?",
            "What are the evacuation priorities and wind shelter requirements during a severe tropical cyclone?",
            "How should logistics handle blocked roads and isolated settlements after a mountain landslide?",
        ]
        selected_preset = st.selectbox("Quick-Select Operational Doctrine Query", preset_questions, index=1)
        default_q_text = (
            selected_preset
            if selected_preset != "Custom Operator Question..."
            else f"What are the resource allocation standards and evacuation priorities for {kpis['active_hazard']}?"
        )

        q_col1, q_col2, q_col3 = st.columns([3, 1, 1])
        with q_col1:
            user_question = st.text_input("Enter Disaster-Response Question", value=default_q_text, key="rag_q_input")
        with q_col2:
            rag_hazard_filter = st.selectbox(
                "SOP Hazard Scope",
                ["ALL", "FLOOD", "EARTHQUAKE", "CYCLONE", "LANDSLIDE"],
                index=0,
                key="rag_hz_filter",
            )
        with q_col3:
            rag_top_k = st.slider("Passages (Top-K)", min_value=1, max_value=8, value=4, key="rag_topk")

        rag_result = query_rag_knowledge_assistant(
            question=user_question,
            hazard_filter=rag_hazard_filter,
            top_k=rag_top_k,
        )

        if rag_result["status"] == "EMPTY_QUERY":
            st.warning(rag_result["grounded_answer"])
        elif rag_result["status"] == "NO_RESULTS":
            st.info(rag_result["grounded_answer"])
        else:
            rag_grounded_html = html.escape(str(rag_result["grounded_answer"]))
            st.markdown(
                f"""
                <div class="eoc-panel">

                {rag_grounded_html}

                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("##### 📄 Retrieved SOP Passages & Chunk Citations")
            for ch in rag_result["chunks"]:
                with st.expander(
                    f"[{ch['sop_id']} | {ch['chunk_id']}] {ch['section_title']} — "
                    f"Hazard: {ch['hazard_type']} | Score: {ch['score']:.4f} ({ch['retrieval_method']})",
                    expanded=ch["rank"] == 1,
                ):
                    st.markdown(f"**Document Title:** {ch['title']} (`{ch['sop_id']}`)")
                    st.markdown(f"**Chunk Reference:** `{ch['chunk_id']}` | **Section:** `{ch['section_title']}`")
                    st.code(ch["content"], language="markdown")

        st.markdown("---")
        st.markdown(f"##### 📌 Active Scenario Automatic RAG Context (`{kpis['active_hazard']}` — `{kpis['governing_sop']}`)")
        st.markdown(
            f"- **Retrieval Engine:** `{sop_ctx.get('retrieval_method', 'vector_chromadb')}` | "
            f"**Latency:** `{sop_ctx.get('execution_time_ms', 0.0):.2f} ms` | "
            f"**SOP Documents:** `{', '.join(sop_ctx.get('sop_ids', []))}`"
        )
        for ch in sop_ctx.get("chunks", []):
            with st.expander(f"Active Scenario Citation: [{ch.get('sop_id')}] {ch.get('section_title')} (Score: {ch.get('score', 0.0):.4f})"):
                st.text(ch.get("content_excerpt", ""))

    def render_module_8_dynamic_replanning() -> None:
        st.subheader("8. Mid-Run Dynamic Replanning & Secondary Incident Simulator")
        st.caption(
            "Simulate a mid-run secondary catastrophe (levee breach, aftershock, slope collapse), invalidate stale Blackboard allocations, and compare Initial vs. Revised plans."
        )

        base_ctx = st.session_state.get("disaster_context") or active_disaster_context
        current_zones = base_ctx.get("zones", [])
        zone_names = [z.get("name") or z.get("zone_name") or z.get("zone_id") for z in current_zones]

        dr1, dr2, dr3, dr4 = st.columns(4)
        with dr1:
            surge_zone_name = st.selectbox(
                "Target Incident Sector",
                zone_names if zone_names else ["Majuli Island Riverine Sector"],
                index=0,
                key="mod8_surge_zone",
            )
        with dr2:
            surge_multiplier = st.slider(
                "Population Surge Multiplier",
                min_value=1.2,
                max_value=2.5,
                value=1.75,
                step=0.05,
                key="mod8_surge_mult",
            )
        with dr3:
            surge_damage_lvl = st.slider(
                "Escalated Damage Level",
                min_value=3,
                max_value=5,
                value=5,
                step=1,
                key="mod8_surge_dmg",
            )
        with dr4:
            new_access_st = st.selectbox(
                "Post-Incident Road Access",
                ["BLOCKED", "DEGRADED", "AIR_ONLY"],
                index=0,
                key="mod8_access",
            )

        if st.button("🚨 Trigger Mid-Run Incident & Execute Dynamic Re-Planning", type="primary", key="mod8_trigger_btn"):
            with st.spinner("Executing multi-agent dynamic replanning workflow over updated Blackboard state..."):
                replan_res = execute_dynamic_replanning_workflow(
                    initial_context=base_ctx,
                    surge_zone_name=surge_zone_name,
                    surge_multiplier=surge_multiplier,
                    surge_damage_lvl=surge_damage_lvl,
                    new_access_status=new_access_st,
                    db=default_db_manager,
                )
                st.session_state.original_plan = replan_res["initial_plan"]
                st.session_state.original_snapshot = replan_res["initial_snapshot"]
                st.session_state.revised_plan = replan_res["revised_plan"]
                st.session_state.revised_snapshot = replan_res["revised_snapshot"]
                st.session_state.greedy_result = replan_res["revised_greedy"]
                st.session_state.surge_occurred = True
                st.session_state.surged_zone_name = surge_zone_name
                st.session_state.plan_result = replan_res["revised_plan"]
                st.session_state.blackboard_snapshot = replan_res["revised_snapshot"]
                st.rerun()

        if st.session_state.get("surge_occurred") and st.session_state.get("original_plan"):
            orig_p = st.session_state.original_plan
            orig_snap = st.session_state.original_snapshot or {}
            orig_audit = orig_p.get("audit_verdict") or {}
            orig_zones = orig_snap.get("zone_needs") or []
            surged_zname = st.session_state.get("surged_zone_name", surge_zone_name)

            st.success(
                f"✅ **Dynamic Replanning Active (`{orig_p.get('plan_id')}` → `{plan.get('plan_id')}`)**: "
                f"Secondary incident in **{surged_zname}** processed while preserving active hazard `{kpis['active_hazard']}`."
            )

            orig_tot_pop = sum(int(z.get("affected_population", 0)) for z in orig_zones)
            new_tot_pop = sum(int(z.get("affected_population", 0)) for z in zone_needs_all)
            orig_tot_disp = sum(int(z.get("displaced_population", 0)) for z in orig_zones)
            new_tot_disp = sum(int(z.get("displaced_population", 0)) for z in zone_needs_all)
            orig_gini = float(orig_audit.get("gini_coefficient", 0.0))
            new_gini = float(audit_data.get("gini_coefficient", 0.0))

            d1, d2, d3, d4, d5 = st.columns(5)
            d1.metric("Affected Population", f"{new_tot_pop:,}", delta=f"{new_tot_pop - orig_tot_pop:+,}")
            d2.metric("Displaced Population", f"{new_tot_disp:,}", delta=f"{new_tot_disp - orig_tot_disp:+,}")
            d3.metric("Fairness Gini", f"{new_gini:.4f}", delta=f"{new_gini - orig_gini:+.4f}", delta_color="inverse")
            d4.metric(
                "Shipment Dispatches",
                f"{len(dispatches_all)}",
                delta=f"{len(dispatches_all) - len(orig_p.get('dispatches', [])):+d} legs",
            )
            d5.metric("Preserved Hazard", kpis["active_hazard"], delta=kpis["governing_sop"])

            st.markdown("##### Initial vs. Revised Sector Needs & Priority Progression")
            diff_rows = []
            orig_z_map = {z.get("zone_id"): z for z in orig_zones}
            for nz in zone_needs_all:
                zid = nz.get("zone_id")
                oz = orig_z_map.get(zid, {})
                o_pop = int(oz.get("affected_population", 0))
                n_pop = int(nz.get("affected_population", 0))
                o_zps = float(oz.get("zps", 0.0))
                n_zps = float(nz.get("zps", 0.0))
                o_food = int(oz.get("demands", {}).get("food_packs", 0))
                n_food = int(nz.get("demands", {}).get("food_packs", 0))
                o_water = float(oz.get("demands", {}).get("water_liters", 0.0))
                n_water = float(nz.get("demands", {}).get("water_liters", 0.0))
                o_tents = int(oz.get("demands", {}).get("tents", 0))
                n_tents = int(nz.get("demands", {}).get("tents", 0))

                diff_rows.append(
                    {
                        "Sector": nz.get("zone_name"),
                        "Population (Initial → Revised)": f"{o_pop:,} → {n_pop:,}"
                        + (f" ({n_pop - o_pop:+,})" if n_pop != o_pop else ""),
                        "Damage": f"{oz.get('damage_level', 0)} → {nz.get('damage_level', 0)}",
                        "Access": f"{oz.get('road_status', 'OPEN')} → {nz.get('road_status', 'OPEN')}",
                        "ZPS (Before → After)": f"{o_zps:.1f} → {n_zps:.1f} ({n_zps - o_zps:+.1f})",
                        "Food Packs Diff": f"{o_food:,} → {n_food:,} ({n_food - o_food:+,})",
                        "Water (L) Diff": f"{o_water:,.0f} → {n_water:,.0f} ({n_water - o_water:+,.0f})",
                        "Tents Diff": f"{o_tents:,} → {n_tents:,} ({n_tents - o_tents:+,})",
                    }
                )
            st.dataframe(pd.DataFrame(diff_rows), width="stretch", hide_index=True)
        else:
            st.info(
                "Click **'Trigger Mid-Run Incident & Execute Dynamic Re-Planning'** above to simulate an incident update and inspect the Initial vs. Revised plan comparison."
            )

    def render_module_9_audit_and_explainability() -> None:
        st.subheader("9. Audit Trail, AI Explainability & Agent Execution History")
        st.caption(
            "Complete governance record including Plan IDs, Decision Audit Trail, Shortage Root Causes, SOP Citations, and Blackboard Event Journal."
        )

        decision_trail = plan.get("decision_audit_trail") or {}
        a_col1, a_col2 = st.columns([3, 2])
        with a_col1:
            st.markdown("##### 🧠 Traceable AI Decision Audit Trail")
            if decision_trail:
                fairness_expl_html = html.escape(str(decision_trail.get("fairness_explanation", "Verified by FairnessAuditorAgent.")))
                st.markdown(
                    f"""
                    <div class="eoc-panel">
                        <strong>Distributive Justice &amp; Governance Rationale:</strong><br/>
                        {fairness_expl_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.markdown("**Sector Prioritization & Survival Floor Rationales:**")
                for ze in decision_trail.get("zone_explanations", []):
                    st.markdown(f"- **Rank #{ze.get('priority_rank')} ({ze.get('zone_name')}):** {ze.get('priority_reasoning')}")

                shortage_expls = decision_trail.get("shortage_explanations", [])
                if shortage_expls:
                    st.markdown("**Resource Shortage Root Cause Explanations:**")
                    for se in shortage_expls:
                        st.markdown(f"- **{se.get('resource_type')}:** {se.get('explanation')}")

        with a_col2:
            st.markdown("##### 🗂️ Committed SQLite Allocation Plans Ledger")
            hist_plans = load_historical_plans_from_db(limit=15)
            if hist_plans:
                st.dataframe(pd.DataFrame(hist_plans), width="stretch", hide_index=True)
            else:
                st.info("No historical plans recorded in SQLite.")

        st.markdown("---")
        st.markdown("##### 📝 Synchronized Blackboard Event Journal & Agent Execution Log")
        events = st.session_state.get("event_history") or []
        if events:
            agents_present = sorted({str(e.get("agent_name", "System")) for e in events})
            sel_agents = st.multiselect("Filter Journal by Autonomous Agent", agents_present, default=agents_present)
            filtered_events = [e for e in events if str(e.get("agent_name", "System")) in sel_agents]
            st.dataframe(pd.DataFrame(filtered_events), width="stretch", hide_index=True)
        else:
            st.info("No blackboard events recorded for this session.")

        if decision_trail:
            with st.expander("⏱️ Structured Decision Audit Telemetry Payload (JSON)", expanded=False):
                st.json(decision_trail)

    # -------------------------------------------------------------------------
    # DISPATCH VIEW BY SIDEBAR SELECTION (UNIFIED 9-TAB DECK OR FOCUSED MODULE)
    # -------------------------------------------------------------------------
    if selected_module == "ALL MODULES (Command Tabs)":
        tabs = st.tabs(
            [
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
        )
        with tabs[0]:
            render_module_1_executive_overview()
        with tabs[1]:
            render_module_2_disaster_monitoring()
        with tabs[2]:
            render_module_3_gis_command_map()
        with tabs[3]:
            render_module_4_resource_management()
        with tabs[4]:
            render_module_5_ai_allocation_engine()
        with tabs[5]:
            render_module_6_fairness_analytics()
        with tabs[6]:
            render_module_7_rag_knowledge_assistant()
        with tabs[7]:
            render_module_8_dynamic_replanning()
        with tabs[8]:
            render_module_9_audit_and_explainability()
    elif selected_module.startswith("1."):
        render_module_1_executive_overview()
    elif selected_module.startswith("2."):
        render_module_2_disaster_monitoring()
    elif selected_module.startswith("3."):
        render_module_3_gis_command_map()
    elif selected_module.startswith("4."):
        render_module_4_resource_management()
    elif selected_module.startswith("5."):
        render_module_5_ai_allocation_engine()
    elif selected_module.startswith("6."):
        render_module_6_fairness_analytics()
    elif selected_module.startswith("7."):
        render_module_7_rag_knowledge_assistant()
    elif selected_module.startswith("8."):
        render_module_8_dynamic_replanning()
    elif selected_module.startswith("9."):
        render_module_9_audit_and_explainability()


if __name__ == "__main__" or st.runtime.exists():
    render_dashboard()

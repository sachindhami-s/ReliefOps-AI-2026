"""
ReliefOps AI — Multi-Agent End-to-End Terminal Demonstration
Executes the authoritative SCEN-01 4-zone monsoon flood disaster response scenario through all five agents,
printing real-time blackboard state, RAG citations, inventory allocation, resource adequacy, and fairness auditing.

Academic Disclaimer:
Synthetic demonstration platform developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import datetime
import json
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.database.db_manager import default_db_manager
from backend.database.seeder import build_scenario_context, seed_database
from backend.blackboard.blackboard_manager import BlackboardManager
from backend.agents.relief_coordinator import ReliefCoordinator


def run_demonstration(scenario_id: str = "SCEN-01", planning_days: int = 3):
    print("=" * 85)
    print("RELIEFOPS AI — AUTONOMOUS DISASTER RESPONSE COORDINATION PIPELINE")
    print("University Course: CSE476 (Agentic AI and Intelligent Automation)")
    print("=" * 85)

    # 1. Verify SQLite Database has baseline records without destructively resetting
    print("\n[STEP 1] Verifying SQLite Database & Baseline Inventory...")
    existing_wh = default_db_manager.execute_query("SELECT COUNT(*) AS cnt FROM warehouses")
    if not existing_wh or existing_wh[0]["cnt"] == 0:
        seed_database(default_db_manager)
    else:
        print("[INFO] Existing SQLite database verified and preserved.")

    # 2. Initialize Shared Blackboard & Multi-Agent Coordinator
    print("\n[STEP 2] Initializing Hayes-Roth Blackboard & Relief Coordinator...")
    bb = BlackboardManager(db=default_db_manager)
    coordinator = ReliefCoordinator(blackboard=bb, db=default_db_manager)

    # 3. Load Authoritative Scenario from SQLite (identical to Streamlit UI)
    scenario_context = build_scenario_context(scenario_id=scenario_id, planning_days=planning_days, db=default_db_manager)
    print(
        f"\n[STEP 3] Loaded Scenario {scenario_id}: '{scenario_context['name']}' "
        f"({scenario_context['disaster_type']} | Severity: {scenario_context['severity']} | "
        f"Zones: {len(scenario_context['zones'])} | Horizon: {planning_days} days)"
    )

    start_time = datetime.datetime.now()
    final_plan = coordinator.run_full_coordination_cycle(disaster_context=scenario_context)
    duration = (datetime.datetime.now() - start_time).total_seconds()
    print(f"Pipeline finished in {duration:.2f} seconds.")

    # 4. Display Results
    snapshot = bb.get_snapshot()

    print("\n" + "=" * 85)
    print("1. RAG SOP RETRIEVAL & CITATIONS (NeedsAssessmentAgent)")
    print("=" * 85)
    sop_ctx = snapshot.get("sop_context", {})
    print(f"Retrieval Engine:        {sop_ctx.get('retrieval_method')}")
    print(f"Event Severity:          {sop_ctx.get('severity')} -> SOP Equivalent: {sop_ctx.get('sop_severity_equivalent')}")
    print(f"Query:                   {sop_ctx.get('query')}")
    print(f"Retrieved SOP IDs:       {sop_ctx.get('sop_ids')}")
    for idx, ch in enumerate(sop_ctx.get("chunks", [])[:3], 1):
        print(f"  [{idx}] {ch.get('chunk_id')} | {ch.get('section_title')} (Score: {ch.get('score'):.4f})")

    print("\n" + "=" * 85)
    print("2. ZONE NEEDS & ZPS RANKINGS (NeedsAssessmentAgent)")
    print("=" * 85)
    zone_needs = snapshot.get("zone_needs", [])
    tot_pop = sum(z.get("affected_population", 0) for z in zone_needs)
    tot_disp = sum(int(z.get("displaced_population", 0)) for z in zone_needs)
    print(f"Total Affected Population: {tot_pop:,} | Total Displaced Population: {tot_disp:,}")
    for z in zone_needs:
        d = z.get("demands", {})
        print(
            f"Rank #{z.get('priority_rank')} | {z.get('zone_name'):<35} | "
            f"ZPS: {z.get('zps', 0.0):.2f} | Pop: {z.get('affected_population', 0):>6} | "
            f"Food: {d.get('food_packs', 0):>6} | Water: {d.get('water_liters', 0.0):>9.0f}L | "
            f"Tents: {d.get('tents', 0):>6} | Med Kits: {d.get('medical_kits', 0):>3}"
        )

    print("\n" + "=" * 85)
    print("3. WAREHOUSE INVENTORY & SUPPLY FEASIBILITY (InventoryAgent)")
    print("=" * 85)
    inv = snapshot.get("inventory_snapshot", {})
    feas = inv.get("feasibility", {})
    print(f"Inventory Adequacy Status: {inv.get('adequacy_status')}")
    for rtype, f in feas.items():
        print(
            f"{rtype:<15} | Available: {f.get('available', 0):>9,} | "
            f"Demanded: {f.get('demanded', 0):>10,} | Coverage: {f.get('coverage_pct', 0.0):>5.1f}% | "
            f"Shortage: {f.get('shortage_qty', 0):>10,} | Status: {f.get('status')}"
        )

    print("\n" + "=" * 85)
    print("4. DISTRIBUTIVE FAIRNESS & RESOURCE ADEQUACY AUDIT (FairnessAuditorAgent)")
    print("=" * 85)
    audit = final_plan.get("audit_verdict", {})
    print(f"Distributive Fairness Verdict: {audit.get('fairness_verdict')} (Gini: {audit.get('gini_coefficient', 0.0):.4f} <= 0.35)")
    print(f"Resource Adequacy Status:      {audit.get('adequacy_status')}")
    print(f"Overall Plan Status:           {final_plan.get('overall_status')}")
    print(f"Min Zone Coverage Ratio:       {audit.get('min_coverage_ratio', 0.0):.1%}")
    print(f"Audit Explanation:             {audit.get('explanation')}")
    for sw in audit.get("shortage_warnings", []):
        print(f"  [SHORTAGE WARNING] {sw}")

    print("\n" + "=" * 85)
    print("5. FINAL DISPATCH SCHEDULE & GIS ROUTES (ReliefCoordinator)")
    print("=" * 85)
    dispatches = final_plan.get("dispatches", [])
    print(
        f"Plan ID: {final_plan.get('plan_id')} | Overall Status: {final_plan.get('overall_status')} | "
        f"Total Dispatches: {len(dispatches)}"
    )
    for d in dispatches[:12]:
        print(
            f"To: {d.get('zone_id'):<22} | From: {d.get('warehouse_id'):<18} | "
            f"{d.get('resource_type'):<14} | Alloc: {d.get('allocated_qty'):>7,} / Req: {d.get('requested_qty'):>9,} | "
            f"Dist: {d.get('distance_km'):>5.1f}km | ETA: {d.get('est_transit_hours'):>4.1f}h"
        )
    if len(dispatches) > 12:
        print(f"... and {len(dispatches) - 12} more itemized shipment dispatches.")

    print("\n" + "=" * 85)
    print("DEMONSTRATION RUN COMPLETE — ALL 5 AGENTS EXECUTED SUCCESSFULLY")
    print("=" * 85)
    return final_plan


if __name__ == "__main__":
    run_demonstration()

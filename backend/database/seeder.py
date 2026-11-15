"""
ReliefOps AI — Master Database Seeder
Seeds baseline disaster events, affected zones, regional warehouses, inventory SKUs,
and university evaluation scenarios into SQLite.
"""

import datetime
import json
import os
from typing import Optional
from backend.database.db_manager import DatabaseManager, default_db_manager


def seed_database(db: Optional[DatabaseManager] = None) -> None:
    """Populates SQLite with authoritative baseline operational data and scenarios."""
    if db is None:
        db = default_db_manager

    # Ensure tables exist
    db.initialize_database()

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Seed Disaster Events across canonical hazard types
    events = [
        ("EVT-2026-FL01", "Brahmaputra Valley Catastrophic Monsoon Flood", "FLOOD", "SEVERE", now, "ACTIVE", 332000),
        ("EVT-2026-EQ01", "Assam-Arunachal Seismic Zone High-Magnitude Earthquake", "EARTHQUAKE", "SEVERE", now, "ACTIVE", 248000),
        ("EVT-2026-CY01", "Bay of Bengal Severe Tropical Cyclone & Storm Surge", "CYCLONE", "SEVERE", now, "ACTIVE", 210000),
        ("EVT-2026-LS01", "Himalayan Ridge Multi-Sector Mountain Landslide & Blockade", "LANDSLIDE", "SEVERE", now, "ACTIVE", 145000),
    ]

    for ev in events:
        db.execute_non_query(
            """
            INSERT INTO disaster_events
            (event_id, name, disaster_type, severity_level, reported_at, status, total_affected_pop)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                name=excluded.name,
                disaster_type=excluded.disaster_type,
                severity_level=excluded.severity_level,
                status=excluded.status,
                total_affected_pop=excluded.total_affected_pop
            """,
            ev,
        )

    # 2. Seed Affected Zones
    zones = [
        (
            "ZONE-MAJULI-ISLAND", "EVT-2026-FL01", "Majuli Island Riverine Sector",
            26.96, 94.22, 45000, 0.88, 4, 0.85, "DEGRADED", 0.0
        ),
        (
            "ZONE-KAZIRANGA-RURAL", "EVT-2026-FL01", "Kaziranga Foothills & Rural Belt",
            26.58, 93.17, 28000, 0.75, 3, 0.60, "OPEN", 0.0
        ),
        (
            "ZONE-DIBRUGARH-URBAN", "EVT-2026-FL01", "Dibrugarh Municipal Perimeter",
            27.47, 94.91, 110000, 0.52, 3, 0.45, "OPEN", 0.0
        ),
        (
            "ZONE-DHEMAJI-PERIPHERY", "EVT-2026-FL01", "Dhemaji North Submerged Sector",
            27.48, 94.58, 32000, 0.92, 5, 0.95, "BLOCKED", 0.0
        ),
        (
            "ZONE-NAGAON-CENTRAL", "EVT-2026-FL01", "Nagaon Plains Staging Area",
            26.35, 92.68, 65000, 0.60, 2, 0.35, "OPEN", 0.0
        ),
        (
            "ZONE-BARPETA-SOUTH", "EVT-2026-FL01", "Barpeta Lowland Inundation Basin",
            26.32, 91.01, 52000, 0.81, 4, 0.75, "OPEN", 0.0
        )
    ]

    for z in zones:
        db.execute_non_query(
            """
            INSERT OR REPLACE INTO affected_zones
            (zone_id, event_id, name, latitude, longitude, population, vulnerability_index,
             damage_level, medical_urgency, access_status, calculated_priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            z
        )

    # 3. Seed Regional Warehouses
    warehouses = [
        ("WH-GUWAHATI-NORTH", "Guwahati Central Strategic Logistics Depot", 26.18, 91.73, "OPERATIONAL", 50000.0),
        ("WH-JORHAT-EAST", "Jorhat Regional Forward Supply Hub", 26.75, 94.22, "OPERATIONAL", 30000.0),
        ("WH-SILIGURI-WEST", "Siliguri Inter-State Transshipment Depot", 26.72, 88.42, "OPERATIONAL", 45000.0),
        ("WH-TEZPUR-CENTRAL", "Tezpur Quick-Response Base", 26.63, 92.79, "OPERATIONAL", 35000.0)
    ]

    for w in warehouses:
        db.execute_non_query(
            """
            INSERT OR REPLACE INTO warehouses (warehouse_id, name, latitude, longitude, status, total_capacity_m3)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            w
        )

    # 4. Seed Warehouse Inventory SKUs
    # Total available: Food ~120,000 packs, Water ~350,000 liters, Medical ~2,400 kits, Tents ~4,500 units
    inventory_items = [
        # Guwahati Central (Major Depot)
        ("WH-GUWAHATI-NORTH", "FOOD_RATIONS", 50000, 0, "packs", now),
        ("WH-GUWAHATI-NORTH", "CLEAN_WATER", 150000, 0, "liters", now),
        ("WH-GUWAHATI-NORTH", "MEDICAL_KITS", 1000, 0, "kits", now),
        ("WH-GUWAHATI-NORTH", "SHELTER_TENTS", 2000, 0, "tents", now),

        # Jorhat Forward Hub (Close to East / Majuli)
        ("WH-JORHAT-EAST", "FOOD_RATIONS", 25000, 0, "packs", now),
        ("WH-JORHAT-EAST", "CLEAN_WATER", 70000, 0, "liters", now),
        ("WH-JORHAT-EAST", "MEDICAL_KITS", 500, 0, "kits", now),
        ("WH-JORHAT-EAST", "SHELTER_TENTS", 800, 0, "tents", now),

        # Siliguri Inter-State Hub (High capacity, distant)
        ("WH-SILIGURI-WEST", "FOOD_RATIONS", 30000, 0, "packs", now),
        ("WH-SILIGURI-WEST", "CLEAN_WATER", 80000, 0, "liters", now),
        ("WH-SILIGURI-WEST", "MEDICAL_KITS", 500, 0, "kits", now),
        ("WH-SILIGURI-WEST", "SHELTER_TENTS", 1000, 0, "tents", now),

        # Tezpur Base (Central Corridor)
        ("WH-TEZPUR-CENTRAL", "FOOD_RATIONS", 15000, 0, "packs", now),
        ("WH-TEZPUR-CENTRAL", "CLEAN_WATER", 50000, 0, "liters", now),
        ("WH-TEZPUR-CENTRAL", "MEDICAL_KITS", 400, 0, "kits", now),
        ("WH-TEZPUR-CENTRAL", "SHELTER_TENTS", 700, 0, "tents", now)
    ]

    for item in inventory_items:
        db.execute_non_query(
            """
            INSERT OR REPLACE INTO warehouse_inventory
            (warehouse_id, resource_type, available_quantity, reserved_quantity, unit, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            item
        )

    # 5. Seed Five Academic Evaluation Scenarios
    scenarios = [
        (
            "SCEN-01",
            "Baseline Multi-Zone Flood (Rapid Onset)",
            "Moderate resource scarcity across 4 affected zones; tests standard end-to-end allocation, SOP RAG, and baseline fairness.",
            "BASELINE",
            json.dumps({
                "zones": ["ZONE-MAJULI-ISLAND", "ZONE-KAZIRANGA-RURAL", "ZONE-DIBRUGARH-URBAN", "ZONE-NAGAON-CENTRAL"],
                "supply_multiplier": 1.0,
                "road_blockages": []
            }),
            now
        ),
        (
            "SCEN-02",
            "Severe Resource Deficit (Mountain Earthquake)",
            "Extreme resource deficit (stock covers only 35% of total aggregate need); verifies that the Fairness Auditor enforces the minimum survival floor without starving peripheral communities.",
            "EXTREME_SCARCITY",
            json.dumps({
                "zones": ["ZONE-MAJULI-ISLAND", "ZONE-KAZIRANGA-RURAL", "ZONE-DIBRUGARH-URBAN", "ZONE-DHEMAJI-PERIPHERY", "ZONE-BARPETA-SOUTH"],
                "supply_multiplier": 0.35,
                "road_blockages": []
            }),
            now
        ),
        (
            "SCEN-03",
            "Bay of Bengal Tropical Cyclone & Logistics Blockade",
            "Primary river crossing bridge washed away during severe cyclone surge; road access into Zone 4 (Dhemaji) is BLOCKED. Tests Logistics Agent rerouting and aerial delivery flag.",
            "LOGISTICS_FAILURE",
            json.dumps({
                "zones": ["ZONE-DHEMAJI-PERIPHERY", "ZONE-MAJULI-ISLAND", "ZONE-DIBRUGARH-URBAN"],
                "supply_multiplier": 0.8,
                "road_blockages": ["ZONE-DHEMAJI-PERIPHERY"]
            }),
            now
        ),
        (
            "SCEN-04",
            "Himalayan Ridge Landslide & Mid-Run Dynamic Re-Planning (Secondary Surge)",
            "A catastrophic slope failure and embankment breach surges into Zone 3 mid-run, doubling its population and damage score. Demonstrates blackboard state invalidation, dynamic re-planning, and plan diff analysis.",
            "DYNAMIC_REPLAN",
            json.dumps({
                "initial_zones": ["ZONE-MAJULI-ISLAND", "ZONE-KAZIRANGA-RURAL", "ZONE-NAGAON-CENTRAL"],
                "surge_zone": "ZONE-MAJULI-ISLAND",
                "surge_damage": 5,
                "surge_pop_multiplier": 1.75
            }),
            now
        ),
        (
            "SCEN-05",
            "Fairness Auditor Veto & Negotiation Loop",
            "Coordinator is intentionally forced to execute a naive greedy cost-minimization plan giving 0% supplies to distant Zone 6. Tests mandatory fairness gate veto, constraint feedback, and auto-revised resolution.",
            "AUDIT_REJECTION",
            json.dumps({
                "force_greedy": True,
                "deprived_zone": "ZONE-BARPETA-SOUTH"
            }),
            now
        )
    ]

    for sc in scenarios:
        db.execute_non_query(
            """
            INSERT OR REPLACE INTO simulation_scenarios
            (scenario_id, title, description, scenario_type, parameters_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            sc
        )

    print("[SUCCESS] SQLite database successfully seeded with master disaster data and 5 evaluation scenarios.")


def build_scenario_context(
    scenario_id: str = "SCEN-01",
    planning_days: int = 3,
    db: Optional[DatabaseManager] = None,
) -> dict:
    """
    Loads an authoritative evaluation scenario and its associated zones from SQLite,
    ensuring 100% input consistency across Streamlit UI, CLI demonstrations, and integration tests.
    """
    if db is None:
        db = default_db_manager

    scen_rows = db.execute_query(
        "SELECT scenario_id, title, description, scenario_type, parameters_json FROM simulation_scenarios WHERE scenario_id = ?",
        (scenario_id,),
    )
    all_zones_rows = db.execute_query(
        "SELECT zone_id, event_id, name, latitude, longitude, population, vulnerability_index, damage_level, medical_urgency, access_status FROM affected_zones"
    )
    zones_by_id = {r["zone_id"]: dict(r) for r in all_zones_rows}

    if scen_rows:
        scen = dict(scen_rows[0])
        try:
            params = json.loads(scen.get("parameters_json", "{}"))
        except Exception:
            params = {}
        title = scen.get("title", f"Scenario {scenario_id}")
        target_ids = (
            params.get("zones")
            or params.get("initial_zones")
            or ["ZONE-MAJULI-ISLAND", "ZONE-KAZIRANGA-RURAL", "ZONE-DIBRUGARH-URBAN", "ZONE-NAGAON-CENTRAL"]
        )
        road_blockages = set(params.get("road_blockages", []))
        surge_zone = params.get("surge_zone")
        surge_damage = params.get("surge_damage")
        surge_pop_mult = params.get("surge_pop_multiplier")
    else:
        title = "Baseline Multi-Zone Flood (Rapid Onset)"
        target_ids = ["ZONE-MAJULI-ISLAND", "ZONE-KAZIRANGA-RURAL", "ZONE-DIBRUGARH-URBAN", "ZONE-NAGAON-CENTRAL"]
        road_blockages = set()
        surge_zone = None
        surge_damage = None
        surge_pop_mult = None

    # Determine canonical hazard type from scenario_id or title
    canonical_scenario_hazards = {
        "SCEN-01": "FLOOD",
        "SCEN-02": "EARTHQUAKE",
        "SCEN-03": "CYCLONE",
        "SCEN-04": "LANDSLIDE",
    }
    title_upper = title.upper()
    if "EARTHQUAKE" in title_upper:
        disaster_type = "EARTHQUAKE"
    elif "CYCLONE" in title_upper:
        disaster_type = "CYCLONE"
    elif "LANDSLIDE" in title_upper:
        disaster_type = "LANDSLIDE"
    elif scenario_id in canonical_scenario_hazards:
        disaster_type = canonical_scenario_hazards[scenario_id]
    else:
        disaster_type = "FLOOD"

    selected_zones = []
    for zid in target_ids:
        if zid not in zones_by_id:
            continue
        z = dict(zones_by_id[zid])
        pop = int(z["population"])
        dmg = int(z["damage_level"])
        access = z["access_status"]

        if zid in road_blockages:
            access = "BLOCKED"
        if surge_zone and zid == surge_zone:
            if surge_damage is not None:
                dmg = int(surge_damage)
            if surge_pop_mult is not None:
                pop = int(round(pop * float(surge_pop_mult)))

        selected_zones.append(
            {
                "zone_id": zid,
                "name": z["name"],
                "zone_name": z["name"],
                "population": pop,
                "affected_population": pop,
                "damage_level": dmg,
                "vulnerability_index": float(z["vulnerability_index"]),
                "medical_urgency": float(z["medical_urgency"]),
                "access_status": access,
                "road_status": access,
                "latitude": float(z["latitude"]),
                "longitude": float(z["longitude"]),
                "lat": float(z["latitude"]),
                "lon": float(z["longitude"]),
            }
        )

    hazard_code = {
        "FLOOD": "FL",
        "EARTHQUAKE": "EQ",
        "CYCLONE": "CY",
        "LANDSLIDE": "LS",
    }.get(disaster_type, "FL")
    event_id = f"EVT-2026-{hazard_code}01"

    return {
        "scenario_id": scenario_id,
        "event_id": event_id,
        "name": title,
        "hazard": disaster_type,
        "disaster_type": disaster_type,
        "severity": "SEVERE",
        "severity_level": "SEVERE",
        "planning_days": max(1, int(planning_days)),
        "zones": selected_zones,
    }


if __name__ == "__main__":
    seed_database()


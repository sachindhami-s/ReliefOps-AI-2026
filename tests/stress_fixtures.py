"""
ReliefOps AI — Stress Testing Scenarios & Fixture Infrastructure
Defines 12 deterministic synthetic test scenarios and isolated test environment fixtures
for multi-hazard stress testing, resource constraints, fairness auditing, dynamic replanning,
and operational resilience benchmarking.

Academic Disclaimer:
Synthetic test fixtures developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.relief_coordinator import ReliefCoordinator
from backend.blackboard.blackboard_manager import BlackboardManager
from backend.database.db_manager import DatabaseManager
from backend.database.seeder import seed_database


# ==============================================================================
# 12 Deterministic Synthetic Stress Scenarios
# ==============================================================================

STRESS_SCENARIOS: Dict[str, Dict[str, Any]] = {
    # 1. Baseline Flood — Moderate severity, normal population
    "SCEN_01_BASELINE_FLOOD": {
        "scenario_id": "STRESS-SCEN-01",
        "event_id": "EVT-STRESS-01",
        "name": "Baseline Flood (Moderate Inundation)",
        "disaster_type": "FLOOD",
        "severity_level": "MODERATE",
        "planning_days": 2,
        "expected_sop": "SOP-FL-001",
        "expected_severity_mapping": "Level 2 (Moderate Inundation)",
        "expected_fairness": "FAIRNESS_APPROVED",
        "description": "Moderate severity flood across 3 riverine zones with normal population and open transit corridors.",
        "zones": [
            {
                "zone_id": "ZONE-S01-MAJULI",
                "name": "Majuli Riverine Island",
                "population": 3000,
                "affected_population": 3000,
                "damage_level": 2,
                "vulnerability_index": 0.65,
                "medical_urgency": 0.40,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 26.96,
                "longitude": 94.22,
            },
            {
                "zone_id": "ZONE-S01-KAZIRANGA",
                "name": "Kaziranga Buffer Zone",
                "population": 2500,
                "affected_population": 2500,
                "damage_level": 2,
                "vulnerability_index": 0.55,
                "medical_urgency": 0.35,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 26.58,
                "longitude": 93.17,
            },
            {
                "zone_id": "ZONE-S01-NAGAON",
                "name": "Nagaon Rural Lowlands",
                "population": 3500,
                "affected_population": 3500,
                "damage_level": 3,
                "vulnerability_index": 0.70,
                "medical_urgency": 0.50,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 26.35,
                "longitude": 92.68,
            },
        ],
    },

    # 2. Extreme Flood — Catastrophic severity, high displacement
    "SCEN_02_EXTREME_FLOOD": {
        "scenario_id": "STRESS-SCEN-02",
        "event_id": "EVT-STRESS-02",
        "name": "Extreme Flood (Catastrophic Embankment Failure)",
        "disaster_type": "FLOOD",
        "severity_level": "CATASTROPHIC",
        "planning_days": 5,
        "expected_sop": "SOP-FL-001",
        "expected_severity_mapping": "Level 5 (Catastrophic Breach)",
        "expected_fairness": "FAIRNESS_APPROVED",
        "description": "Massive basin-wide inundation across 5 sectors displacing 185,000 people with severe shelter and water demands.",
        "zones": [
            {
                "zone_id": "ZONE-S02-DHEMAJI",
                "name": "Dhemaji Submerged Core",
                "population": 45000,
                "affected_population": 45000,
                "damage_level": 5,
                "vulnerability_index": 0.95,
                "medical_urgency": 0.90,
                "access_status": "BLOCKED",
                "road_status": "BLOCKED",
                "latitude": 27.48,
                "longitude": 94.58,
            },
            {
                "zone_id": "ZONE-S02-MAJULI",
                "name": "Majuli Deep Inundation",
                "population": 35000,
                "affected_population": 35000,
                "damage_level": 5,
                "vulnerability_index": 0.90,
                "medical_urgency": 0.85,
                "access_status": "BLOCKED",
                "road_status": "BLOCKED",
                "latitude": 26.96,
                "longitude": 94.22,
            },
            {
                "zone_id": "ZONE-S02-BARPETA",
                "name": "Barpeta Inundated Floodplain",
                "population": 40000,
                "affected_population": 40000,
                "damage_level": 4,
                "vulnerability_index": 0.85,
                "medical_urgency": 0.80,
                "access_status": "DEGRADED",
                "road_status": "DEGRADED",
                "latitude": 26.32,
                "longitude": 91.01,
            },
            {
                "zone_id": "ZONE-S02-NAGAON",
                "name": "Nagaon Overflow Sector",
                "population": 35000,
                "affected_population": 35000,
                "damage_level": 4,
                "vulnerability_index": 0.75,
                "medical_urgency": 0.70,
                "access_status": "DEGRADED",
                "road_status": "DEGRADED",
                "latitude": 26.35,
                "longitude": 92.68,
            },
            {
                "zone_id": "ZONE-S02-DHUBRI",
                "name": "Dhubri Downstream Delta",
                "population": 30000,
                "affected_population": 30000,
                "damage_level": 4,
                "vulnerability_index": 0.80,
                "medical_urgency": 0.75,
                "access_status": "DEGRADED",
                "road_status": "DEGRADED",
                "latitude": 26.02,
                "longitude": 89.97,
            },
        ],
    },

    # 3. Severe Earthquake — Critical medical requirements
    "SCEN_03_SEVERE_EARTHQUAKE": {
        "scenario_id": "STRESS-SCEN-03",
        "event_id": "EVT-STRESS-03",
        "name": "Severe Earthquake (Heavy Damage & Medical Emergency)",
        "disaster_type": "EARTHQUAKE",
        "severity_level": "SEVERE",
        "planning_days": 3,
        "expected_sop": "SOP-EQ-002",
        "expected_severity_mapping": "Level 3 (Heavy Damage)",
        "expected_fairness": "FAIRNESS_APPROVED",
        "description": "Magnitude 6.8 seismic shock triggering severe urban trauma, requiring elevated medical triage priority.",
        "zones": [
            {
                "zone_id": "ZONE-S03-GUWAHATI",
                "name": "Guwahati Dense Urban Core",
                "population": 50000,
                "affected_population": 50000,
                "damage_level": 4,
                "vulnerability_index": 0.75,
                "medical_urgency": 0.95,
                "access_status": "DEGRADED",
                "road_status": "DEGRADED",
                "latitude": 26.18,
                "longitude": 91.75,
            },
            {
                "zone_id": "ZONE-S03-TEZPUR",
                "name": "Tezpur Foothill Epicenter",
                "population": 28000,
                "affected_population": 28000,
                "damage_level": 4,
                "vulnerability_index": 0.80,
                "medical_urgency": 0.90,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 26.63,
                "longitude": 92.80,
            },
            {
                "zone_id": "ZONE-S03-NAGAON",
                "name": "Nagaon Peripheral Fractures",
                "population": 22000,
                "affected_population": 22000,
                "damage_level": 3,
                "vulnerability_index": 0.70,
                "medical_urgency": 0.85,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 26.35,
                "longitude": 92.68,
            },
        ],
    },

    # 4. Catastrophic Earthquake — Structural collapse and mass casualties
    "SCEN_04_CATASTROPHIC_EARTHQUAKE": {
        "scenario_id": "STRESS-SCEN-04",
        "event_id": "EVT-STRESS-04",
        "name": "Catastrophic Earthquake (Violent Destruction & Building Collapse)",
        "disaster_type": "EARTHQUAKE",
        "severity_level": "CATASTROPHIC",
        "planning_days": 5,
        "expected_sop": "SOP-EQ-002",
        "expected_severity_mapping": "Level 5 (Catastrophic Flattening)",
        "expected_fairness": "FAIRNESS_APPROVED",
        "description": "Magnitude 7.8 major seismic event causing widespread structural collapse, blocked arteries, and mass casualty trauma.",
        "zones": [
            {
                "zone_id": "ZONE-S04-SHILLONG",
                "name": "Shillong Plateau Epicenter",
                "population": 60000,
                "affected_population": 60000,
                "damage_level": 5,
                "vulnerability_index": 0.95,
                "medical_urgency": 1.00,
                "access_status": "BLOCKED",
                "road_status": "BLOCKED",
                "latitude": 25.57,
                "longitude": 91.88,
            },
            {
                "zone_id": "ZONE-S04-GUWAHATI",
                "name": "Guwahati Collapsed Highrises",
                "population": 75000,
                "affected_population": 75000,
                "damage_level": 5,
                "vulnerability_index": 0.90,
                "medical_urgency": 0.98,
                "access_status": "BLOCKED",
                "road_status": "BLOCKED",
                "latitude": 26.18,
                "longitude": 91.75,
            },
            {
                "zone_id": "ZONE-S04-DISPUR",
                "name": "Dispur Administrative Valley",
                "population": 40000,
                "affected_population": 40000,
                "damage_level": 4,
                "vulnerability_index": 0.85,
                "medical_urgency": 0.90,
                "access_status": "DEGRADED",
                "road_status": "DEGRADED",
                "latitude": 26.14,
                "longitude": 91.79,
            },
            {
                "zone_id": "ZONE-S04-GOALPARA",
                "name": "Goalpara River Bank Settlements",
                "population": 30000,
                "affected_population": 30000,
                "damage_level": 4,
                "vulnerability_index": 0.88,
                "medical_urgency": 0.85,
                "access_status": "DEGRADED",
                "road_status": "DEGRADED",
                "latitude": 26.17,
                "longitude": 90.62,
            },
        ],
    },

    # 5. Severe Cyclone — Coastal evacuation and shelter requirements
    "SCEN_05_SEVERE_CYCLONE": {
        "scenario_id": "STRESS-SCEN-05",
        "event_id": "EVT-STRESS-05",
        "name": "Severe Cyclone (Very Severe Cyclonic Storm)",
        "disaster_type": "CYCLONE",
        "severity_level": "SEVERE",
        "planning_days": 3,
        "expected_sop": "SOP-CY-004",
        "expected_severity_mapping": "Level 3 (Very Severe Cyclone)",
        "expected_fairness": "FAIRNESS_APPROVED",
        "description": "Category 3 storm surge with 140 km/h winds requiring emergency shelter tents and safe drinking water for displaced coastal populations.",
        "zones": [
            {
                "zone_id": "ZONE-S05-COASTAL-A",
                "name": "Coastal Sector Alpha (Beachhead)",
                "population": 32000,
                "affected_population": 32000,
                "damage_level": 4,
                "vulnerability_index": 0.85,
                "medical_urgency": 0.65,
                "access_status": "DEGRADED",
                "road_status": "DEGRADED",
                "latitude": 25.80,
                "longitude": 90.10,
            },
            {
                "zone_id": "ZONE-S05-ESTUARY-B",
                "name": "Estuary Inundation Sector",
                "population": 24000,
                "affected_population": 24000,
                "damage_level": 4,
                "vulnerability_index": 0.90,
                "medical_urgency": 0.70,
                "access_status": "BLOCKED",
                "road_status": "BLOCKED",
                "latitude": 25.65,
                "longitude": 90.30,
            },
            {
                "zone_id": "ZONE-S05-INLAND-C",
                "name": "Inland Evacuation Camp",
                "population": 40000,
                "affected_population": 40000,
                "damage_level": 3,
                "vulnerability_index": 0.75,
                "medical_urgency": 0.55,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 26.05,
                "longitude": 90.50,
            },
        ],
    },

    # 6. Catastrophic Cyclone — Extreme wind damage and infrastructure disruption
    "SCEN_06_CATASTROPHIC_CYCLONE": {
        "scenario_id": "STRESS-SCEN-06",
        "event_id": "EVT-STRESS-06",
        "name": "Catastrophic Cyclone (Super Cyclonic Storm & Grid Outage)",
        "disaster_type": "CYCLONE",
        "severity_level": "CATASTROPHIC",
        "planning_days": 5,
        "expected_sop": "SOP-CY-004",
        "expected_severity_mapping": "Level 5 (Super Cyclone)",
        "expected_fairness": "FAIRNESS_APPROVED",
        "description": "Category 5 super cyclone with >220 km/h winds, widespread forest debris, and extensive road and power grid failures.",
        "zones": [
            {
                "zone_id": "ZONE-S06-PORT-CORRIDOR",
                "name": "Port Maritime Corridor",
                "population": 50000,
                "affected_population": 50000,
                "damage_level": 5,
                "vulnerability_index": 0.95,
                "medical_urgency": 0.85,
                "access_status": "BLOCKED",
                "road_status": "BLOCKED",
                "latitude": 25.50,
                "longitude": 89.80,
            },
            {
                "zone_id": "ZONE-S06-RIVER-ISLANDS",
                "name": "Exposed Sandbar Settlements",
                "population": 28000,
                "affected_population": 28000,
                "damage_level": 5,
                "vulnerability_index": 0.95,
                "medical_urgency": 0.90,
                "access_status": "BLOCKED",
                "road_status": "BLOCKED",
                "latitude": 25.70,
                "longitude": 90.00,
            },
            {
                "zone_id": "ZONE-S06-COASTAL-TOWN",
                "name": "Coastal Municipal Center",
                "population": 45000,
                "affected_population": 45000,
                "damage_level": 4,
                "vulnerability_index": 0.85,
                "medical_urgency": 0.75,
                "access_status": "DEGRADED",
                "road_status": "DEGRADED",
                "latitude": 25.90,
                "longitude": 90.20,
            },
            {
                "zone_id": "ZONE-S06-INLAND-HUB",
                "name": "Inland Staging Terminal",
                "population": 35000,
                "affected_population": 35000,
                "damage_level": 4,
                "vulnerability_index": 0.70,
                "medical_urgency": 0.60,
                "access_status": "DEGRADED",
                "road_status": "DEGRADED",
                "latitude": 26.10,
                "longitude": 90.60,
            },
        ],
    },

    # 7. Severe Landslide — Isolated settlements and blocked roads
    "SCEN_07_SEVERE_LANDSLIDE": {
        "scenario_id": "STRESS-SCEN-07",
        "event_id": "EVT-STRESS-07",
        "name": "Severe Landslide (Major Slope Failure & Cut-off Valleys)",
        "disaster_type": "LANDSLIDE",
        "severity_level": "SEVERE",
        "planning_days": 3,
        "expected_sop": "SOP-LS-003",
        "expected_severity_mapping": "Level 3 (Major Slope Failure)",
        "expected_fairness": "FAIRNESS_APPROVED",
        "description": "Monsoon-triggered hillslope collapse severing primary highway connections to remote mountain communities.",
        "zones": [
            {
                "zone_id": "ZONE-S07-DIMA-HASAO",
                "name": "Dima Hasao Hill Sector",
                "population": 22000,
                "affected_population": 22000,
                "damage_level": 4,
                "vulnerability_index": 0.88,
                "medical_urgency": 0.80,
                "access_status": "BLOCKED",
                "road_status": "BLOCKED",
                "latitude": 25.18,
                "longitude": 93.03,
            },
            {
                "zone_id": "ZONE-S07-HAFLONG",
                "name": "Haflong Valley Settlement",
                "population": 16000,
                "affected_population": 16000,
                "damage_level": 4,
                "vulnerability_index": 0.82,
                "medical_urgency": 0.75,
                "access_status": "DEGRADED",
                "road_status": "DEGRADED",
                "latitude": 25.17,
                "longitude": 93.01,
            },
            {
                "zone_id": "ZONE-S07-LUMDING",
                "name": "Lumding Foothill Depot",
                "population": 20000,
                "affected_population": 20000,
                "damage_level": 2,
                "vulnerability_index": 0.60,
                "medical_urgency": 0.40,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 25.75,
                "longitude": 93.17,
            },
        ],
    },

    # 8. Catastrophic Landslide — Multiple inaccessible zones
    "SCEN_08_CATASTROPHIC_LANDSLIDE": {
        "scenario_id": "STRESS-SCEN-08",
        "event_id": "EVT-STRESS-08",
        "name": "Catastrophic Landslide (Massive Valley Burial)",
        "disaster_type": "LANDSLIDE",
        "severity_level": "CATASTROPHIC",
        "planning_days": 5,
        "expected_sop": "SOP-LS-003",
        "expected_severity_mapping": "Level 5 (Village Burial / Mountain Collapse)",
        "expected_fairness": "FAIRNESS_APPROVED",
        "description": "Massive multi-ridge failure engulfing access roads across 4 mountain sectors, necessitating aerial delivery.",
        "zones": [
            {
                "zone_id": "ZONE-S08-UPPER-VALLEY",
                "name": "Upper Ridge Enclave",
                "population": 18000,
                "affected_population": 18000,
                "damage_level": 5,
                "vulnerability_index": 0.95,
                "medical_urgency": 0.95,
                "access_status": "BLOCKED",
                "road_status": "BLOCKED",
                "latitude": 25.25,
                "longitude": 93.10,
            },
            {
                "zone_id": "ZONE-S08-MID-SLOPE",
                "name": "Mid-Slope Terrace Hamlets",
                "population": 15000,
                "affected_population": 15000,
                "damage_level": 5,
                "vulnerability_index": 0.92,
                "medical_urgency": 0.90,
                "access_status": "BLOCKED",
                "road_status": "BLOCKED",
                "latitude": 25.20,
                "longitude": 93.08,
            },
            {
                "zone_id": "ZONE-S08-RIVER-BED",
                "name": "Debris Dammed River Reach",
                "population": 20000,
                "affected_population": 20000,
                "damage_level": 5,
                "vulnerability_index": 0.90,
                "medical_urgency": 0.85,
                "access_status": "BLOCKED",
                "road_status": "BLOCKED",
                "latitude": 25.15,
                "longitude": 93.05,
            },
            {
                "zone_id": "ZONE-S08-LOWER-PASS",
                "name": "Lower Gorge Chokepoint",
                "population": 12000,
                "affected_population": 12000,
                "damage_level": 4,
                "vulnerability_index": 0.80,
                "medical_urgency": 0.70,
                "access_status": "BLOCKED",
                "road_status": "BLOCKED",
                "latitude": 25.10,
                "longitude": 93.00,
            },
        ],
    },

    # 9. Extreme Population Surge — Sudden 3x population increase
    "SCEN_09_POPULATION_SURGE": {
        "scenario_id": "STRESS-SCEN-09",
        "event_id": "EVT-STRESS-09",
        "name": "Extreme Population Surge (3x Influx Into Reception Zone)",
        "disaster_type": "FLOOD",
        "severity_level": "SEVERE",
        "planning_days": 3,
        "expected_sop": "SOP-FL-001",
        "expected_severity_mapping": "Level 3 (Severe Inundation)",
        "expected_fairness": "FAIRNESS_APPROVED",
        "description": "Massive secondary influx of displaced citizens scaling reception zone population from 15,000 to 45,000 (3x surge).",
        "zones": [
            {
                "zone_id": "ZONE-S09-SURGE-CORE",
                "name": "Central Staging Relocation Hub",
                "population": 45000,  # Surged 3x from baseline 15,000
                "affected_population": 45000,
                "damage_level": 4,
                "vulnerability_index": 0.85,
                "medical_urgency": 0.80,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 26.50,
                "longitude": 93.20,
            },
            {
                "zone_id": "ZONE-S09-STABLE-A",
                "name": "Adjacent Lowland Settlement A",
                "population": 20000,
                "affected_population": 20000,
                "damage_level": 3,
                "vulnerability_index": 0.65,
                "medical_urgency": 0.50,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 26.40,
                "longitude": 93.00,
            },
            {
                "zone_id": "ZONE-S09-STABLE-B",
                "name": "Adjacent Lowland Settlement B",
                "population": 18000,
                "affected_population": 18000,
                "damage_level": 3,
                "vulnerability_index": 0.60,
                "medical_urgency": 0.45,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 26.30,
                "longitude": 92.80,
            },
        ],
    },

    # 10. Critical Water Shortage — Inventory insufficient for demand
    "SCEN_10_WATER_SHORTAGE": {
        "scenario_id": "STRESS-SCEN-10",
        "event_id": "EVT-STRESS-10",
        "name": "Critical Clean Water Deficit (10% Stock Coverage)",
        "disaster_type": "FLOOD",
        "severity_level": "SEVERE",
        "planning_days": 3,
        "expected_sop": "SOP-FL-001",
        "expected_severity_mapping": "Level 3 (Severe Inundation)",
        "expected_fairness": "FAIRNESS_APPROVED",
        "inventory_override": {"CLEAN_WATER": 0.05},  # Only 5% water available across warehouses
        "description": "Regional water purification infrastructure compromised; available potable stock covers only a fraction of survival demand.",
        "zones": [
            {
                "zone_id": "ZONE-S10-ALPHA",
                "name": "Flood Zone Alpha",
                "population": 30000,
                "affected_population": 30000,
                "damage_level": 4,
                "vulnerability_index": 0.80,
                "medical_urgency": 0.70,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 26.60,
                "longitude": 93.30,
            },
            {
                "zone_id": "ZONE-S10-BETA",
                "name": "Flood Zone Beta",
                "population": 25000,
                "affected_population": 25000,
                "damage_level": 3,
                "vulnerability_index": 0.75,
                "medical_urgency": 0.65,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 26.45,
                "longitude": 93.10,
            },
            {
                "zone_id": "ZONE-S10-GAMMA",
                "name": "Flood Zone Gamma",
                "population": 20000,
                "affected_population": 20000,
                "damage_level": 3,
                "vulnerability_index": 0.70,
                "medical_urgency": 0.60,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 26.30,
                "longitude": 92.90,
            },
        ],
    },

    # 11. Critical Medical Shortage — High trauma demand with limited kits
    "SCEN_11_MEDICAL_SHORTAGE": {
        "scenario_id": "STRESS-SCEN-11",
        "event_id": "EVT-STRESS-11",
        "name": "Critical Medical Shortage (10% Medical Kits Coverage)",
        "disaster_type": "EARTHQUAKE",
        "severity_level": "SEVERE",
        "planning_days": 3,
        "expected_sop": "SOP-EQ-002",
        "expected_severity_mapping": "Level 3 (Heavy Damage)",
        "expected_fairness": "FAIRNESS_APPROVED",
        "inventory_override": {"MEDICAL_KITS": 0.08},  # Only 8% medical kits available
        "description": "Mass casualty seismic triage with acute shortage of trauma supplies; forces prioritisation to critical zones.",
        "zones": [
            {
                "zone_id": "ZONE-S11-CRITICAL-HOSPITAL",
                "name": "Hospital Triage Complex",
                "population": 35000,
                "affected_population": 35000,
                "damage_level": 5,
                "vulnerability_index": 0.90,
                "medical_urgency": 0.98,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 26.20,
                "longitude": 91.80,
            },
            {
                "zone_id": "ZONE-S11-COLLAPSED-SUBURB",
                "name": "Collapsed Suburb Cluster",
                "population": 28000,
                "affected_population": 28000,
                "damage_level": 4,
                "vulnerability_index": 0.85,
                "medical_urgency": 0.85,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 26.15,
                "longitude": 91.70,
            },
            {
                "zone_id": "ZONE-S11-PERIPHERAL-TOWN",
                "name": "Peripheral Town Clinic",
                "population": 20000,
                "affected_population": 20000,
                "damage_level": 3,
                "vulnerability_index": 0.70,
                "medical_urgency": 0.60,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 26.10,
                "longitude": 91.60,
            },
        ],
    },

    # 12. Combined Resource Crisis — Simultaneous food, water, medical and shelter shortages
    "SCEN_12_COMBINED_CRISIS": {
        "scenario_id": "STRESS-SCEN-12",
        "event_id": "EVT-STRESS-12",
        "name": "Combined Quadruple Resource Crisis (15% Regional Coverage)",
        "disaster_type": "EARTHQUAKE",
        "severity_level": "CATASTROPHIC",
        "planning_days": 5,
        "expected_sop": "SOP-EQ-002",
        "expected_severity_mapping": "Level 5 (Catastrophic Flattening)",
        "expected_fairness": "FAIRNESS_APPROVED",
        "inventory_override": {
            "FOOD_RATIONS": 0.15,
            "CLEAN_WATER": 0.15,
            "MEDICAL_KITS": 0.15,
            "SHELTER_TENTS": 0.15,
        },
        "description": "Total compound crisis: catastrophic seismic event coinciding with multi-resource warehouse deficits across all 4 categories.",
        "zones": [
            {
                "zone_id": "ZONE-S12-CORE",
                "name": "Disaster Epicenter Ground Zero",
                "population": 50000,
                "affected_population": 50000,
                "damage_level": 5,
                "vulnerability_index": 0.95,
                "medical_urgency": 1.00,
                "access_status": "BLOCKED",
                "road_status": "BLOCKED",
                "latitude": 26.25,
                "longitude": 92.50,
            },
            {
                "zone_id": "ZONE-S12-PERIPHERY-WEST",
                "name": "Western Submerged Periphery",
                "population": 35000,
                "affected_population": 35000,
                "damage_level": 4,
                "vulnerability_index": 0.88,
                "medical_urgency": 0.85,
                "access_status": "DEGRADED",
                "road_status": "DEGRADED",
                "latitude": 26.10,
                "longitude": 92.20,
            },
            {
                "zone_id": "ZONE-S12-PERIPHERY-EAST",
                "name": "Eastern Hills Settlements",
                "population": 30000,
                "affected_population": 30000,
                "damage_level": 4,
                "vulnerability_index": 0.85,
                "medical_urgency": 0.80,
                "access_status": "DEGRADED",
                "road_status": "DEGRADED",
                "latitude": 26.40,
                "longitude": 92.80,
            },
            {
                "zone_id": "ZONE-S12-OUTPOST",
                "name": "Distant Rural Outpost",
                "population": 20000,
                "affected_population": 20000,
                "damage_level": 3,
                "vulnerability_index": 0.75,
                "medical_urgency": 0.65,
                "access_status": "OPEN",
                "road_status": "OPEN",
                "latitude": 26.55,
                "longitude": 93.10,
            },
        ],
    },
}


# ==============================================================================
# Isolated Test Environment Helpers
# ==============================================================================

class IsolatedStressEnvironment:
    """
    Encapsulates an isolated temporary SQLite database and Blackboard instance
    for zero-side-effect stress testing.
    """

    def __init__(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "stress_test.db")
        self.db = DatabaseManager(self.db_path)
        seed_database(self.db)
        self.blackboard = BlackboardManager(db=self.db)
        self.coordinator = ReliefCoordinator(blackboard=self.blackboard, db=self.db)

    def set_inventory_multipliers(self, multipliers: Dict[str, float]) -> None:
        """
        Adjusts warehouse inventory in the isolated database by multiplying current stock.
        """
        for rtype, mult in multipliers.items():
            self.db.execute_non_query(
                "UPDATE warehouse_inventory SET available_quantity = CAST(ROUND(available_quantity * ?) AS INTEGER) WHERE resource_type = ?",
                (mult, rtype),
            )

    def set_exact_stock(self, warehouse_id: str, resource_type: str, qty: int) -> None:
        """
        Sets exact available quantity for a specific warehouse and resource.
        """
        self.db.execute_non_query(
            "UPDATE warehouse_inventory SET available_quantity = ? WHERE warehouse_id = ? AND resource_type = ?",
            (qty, warehouse_id, resource_type),
        )

    def set_zero_stock_for_resource(self, resource_type: str) -> None:
        """
        Sets 0 stock for a specific resource across all warehouses.
        """
        self.db.execute_non_query(
            "UPDATE warehouse_inventory SET available_quantity = 0 WHERE resource_type = ?",
            (resource_type,),
        )

    def set_zero_all_stocks(self) -> None:
        """
        Sets 0 stock for all resources across all warehouses.
        """
        self.db.execute_non_query("UPDATE warehouse_inventory SET available_quantity = 0")

    def set_warehouse_status(self, warehouse_id: str, status: str) -> None:
        """
        Updates operational status of a warehouse (e.g. INACCESSIBLE).
        """
        self.db.execute_non_query(
            "UPDATE warehouses SET status = ? WHERE warehouse_id = ?",
            (status, warehouse_id),
        )

    def cleanup(self) -> None:
        """
        Cleanly closes database handles before removing the temp directory (Windows-safe).
        """
        try:
            self.db.close()
        except Exception:
            pass
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

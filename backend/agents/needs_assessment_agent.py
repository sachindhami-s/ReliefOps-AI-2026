"""
ReliefOps AI — Needs Assessment Agent
Specialized agent responsible for assessing disaster zone severity, retrieving
governing SOP standards via RAG, and computing per-zone resource demands and ZPS priorities.

Academic Disclaimer:
Synthetic demonstration agent developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import json
from typing import Any, Dict, List, Optional
from semantic_kernel import Kernel

from backend.agents.base_agent import BaseAgent
from backend.plugins.needs_plugin import NeedsAssessmentPlugin


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely converts an arbitrary value to int with a fallback default."""
    try:
        if val is None:
            return default
        return int(val)
    except (TypeError, ValueError):
        return default


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely converts an arbitrary value to float with a fallback default."""
    try:
        if val is None:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


class NeedsAssessmentAgent(BaseAgent):
    """
    Needs Assessment Agent for ReliefOps AI.
    Inherits from BaseAgent, integrates with Microsoft Semantic Kernel and the NeedsAssessmentPlugin,
    evaluates disaster zones, retrieves SOP guidelines via RAG, and writes assessment data to the Blackboard.
    """

    def __init__(
        self,
        name: str = "NeedsAssessmentAgent",
        kernel: Optional[Kernel] = None,
        blackboard: Optional[Any] = None,
        plugin: Optional[NeedsAssessmentPlugin] = None,
    ):
        """
        Initializes the Needs Assessment Agent.

        Args:
            name: Agent name identifier.
            kernel: Optional Semantic Kernel instance.
            blackboard: Optional shared Blackboard reference.
            plugin: Optional NeedsAssessmentPlugin instance.
        """
        super().__init__(name=name, kernel=kernel, blackboard=blackboard)
        self.plugin = plugin or NeedsAssessmentPlugin()

        # Register plugin with Semantic Kernel if not already registered
        try:
            if "NeedsAssessment" not in self.kernel.plugins:
                self.kernel.add_plugin(self.plugin, plugin_name="NeedsAssessment")
                self.log("Registered NeedsAssessmentPlugin on Semantic Kernel.")
        except Exception as e:
            self.log(f"Plugin registration check warning: {e}", level="WARNING")

    def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes the Needs Assessment lifecycle:
        1. Consumes disaster_context from Blackboard (or input parameter).
        2. Retrieves relevant SOP guidelines via RAG using the NeedsAssessmentPlugin.
        3. Evaluates all affected geographical zones independently.
        4. Calculates physical relief demands (water, food, medical kits, tents).
        5. Computes normalized Zone Priority Scores (ZPS) and assigns priority rankings.
        6. Writes 'sop_context' and 'zone_needs' to the shared Blackboard.

        Args:
            context: Optional disaster context dictionary overriding Blackboard state.

        Returns:
            Structured dictionary of the complete needs assessment.
        """
        self.log("Starting needs assessment execution cycle.")

        # 1. Resolve and validate disaster context
        disaster_context = context
        if disaster_context is None:
            disaster_context = self.read_section("disaster_context")

        if not disaster_context or not isinstance(disaster_context, dict):
            self.log("Disaster context is missing or invalid.", level="WARNING")
            return {
                "status": "EMPTY_CONTEXT",
                "message": "No valid disaster_context available for assessment.",
                "zones_assessed": 0,
                "zone_needs": [],
                "sop_context": {},
            }

        event_id = disaster_context.get("event_id", "EVENT-UNKNOWN")
        disaster_type = str(disaster_context.get("disaster_type", "FLOOD")).strip().upper()
        raw_severity = disaster_context.get("severity") or disaster_context.get("severity_level") or "Level 3"
        severity = str(raw_severity).strip()
        planning_days = max(1, _safe_int(disaster_context.get("planning_days"), default=1))
        zones = disaster_context.get("zones", [])

        if not zones or not isinstance(zones, list):
            self.log("Disaster context contains no affected zones.", level="WARNING")
            return {
                "status": "NO_ZONES",
                "event_id": event_id,
                "disaster_type": disaster_type,
                "message": "Disaster context contains an empty zones list.",
                "zones_assessed": 0,
                "zone_needs": [],
                "sop_context": {},
            }

        # 2. Retrieve SOP guidelines via RAG (delegated to NeedsAssessmentPlugin)
        self.log(f"Retrieving SOP guidelines for hazard '{disaster_type}' at severity '{severity}'.")
        raw_sop_json = self.plugin.retrieve_sop_guidelines(
            disaster_type=disaster_type,
            severity=severity,
        )
        try:
            sop_context = json.loads(raw_sop_json)
        except Exception as e:
            self.log(f"Failed to parse SOP retrieval response: {e}", level="ERROR")
            sop_context = {"status": "ERROR", "error": str(e), "sop_ids": [], "chunks": []}

        # Write retrieved SOP context to Blackboard immediately
        self.write_section("sop_context", sop_context)

        # 3. Determine regional population benchmark for robust ZPS normalization
        zone_populations = [
            _safe_int(z.get("affected_population") or z.get("population"), default=0)
            for z in zones
            if isinstance(z, dict)
        ]
        regional_max_pop = max(zone_populations) if zone_populations else 1000
        declared_max_pop = disaster_context.get("pop_max")
        if declared_max_pop is not None:
            regional_max_pop = max(regional_max_pop, _safe_int(declared_max_pop, default=regional_max_pop))

        # 4. Process each affected zone independently
        zone_profiles: List[Dict[str, Any]] = []
        total_water_liters = 0.0
        total_jerrycans = 0
        total_food_packs = 0
        total_medical_kits = 0
        total_tents = 0
        total_displaced = 0.0
        total_affected = 0

        self.log(f"Evaluating resource demands and ZPS priorities for {len(zones)} zones.")

        for zone_raw in zones:
            if not isinstance(zone_raw, dict):
                continue

            zone_id = str(zone_raw.get("zone_id", f"ZONE-{len(zone_profiles)+1}"))
            zone_name = str(zone_raw.get("zone_name") or zone_raw.get("name") or zone_id)
            population = max(0, _safe_int(zone_raw.get("affected_population") or zone_raw.get("population"), default=0))
            damage_lvl = _safe_float(zone_raw.get("damage_level"), default=1.0)
            vulnerability_idx = _safe_float(zone_raw.get("vulnerability_index"), default=0.0)
            medical_urgency = _safe_float(zone_raw.get("medical_urgency"), default=0.0)
            road_status = str(zone_raw.get("road_status") or zone_raw.get("access_status") or "OPEN").strip().upper()
            lat = zone_raw.get("lat") or zone_raw.get("latitude")
            lon = zone_raw.get("lon") or zone_raw.get("longitude")

            # Calculate physical relief resource demands via plugin
            demands_json = self.plugin.calculate_zone_demands(
                population=population,
                vulnerability_idx=vulnerability_idx,
                damage_lvl=damage_lvl,
                medical_urgency=medical_urgency,
                days=planning_days,
            )
            demands_res = json.loads(demands_json)
            demands_data = demands_res.get("demands", {})

            # Calculate Zone Priority Score (ZPS) via plugin
            zps_json = self.plugin.compute_zone_priority(
                damage_lvl=damage_lvl,
                vulnerability_idx=vulnerability_idx,
                medical_urgency=medical_urgency,
                population=population,
                pop_max=regional_max_pop,
            )
            zps_res = json.loads(zps_json)

            # Accumulate aggregates
            total_affected += population
            total_displaced += demands_res.get("displaced_population", 0.0)
            total_water_liters += demands_data.get("water_liters", 0.0)
            total_jerrycans += demands_data.get("jerrycans_10l", 0)
            total_food_packs += demands_data.get("food_packs", 0)
            total_medical_kits += demands_data.get("medical_kits", 0)
            total_tents += demands_data.get("tents", 0)

            zone_profile = {
                "zone_id": zone_id,
                "zone_name": zone_name,
                "affected_population": population,
                "damage_level": demands_res.get("parameters", {}).get("damage_level", damage_lvl),
                "vulnerability_index": demands_res.get("parameters", {}).get("vulnerability_index", vulnerability_idx),
                "medical_urgency": demands_res.get("parameters", {}).get("medical_urgency", medical_urgency),
                "displacement_ratio": demands_res.get("displacement_ratio", 0.20),
                "displaced_population": demands_res.get("displaced_population", 0.0),
                "zps": zps_res.get("zps", 0.0),
                "priority_rank": 0,  # Assigned after sorting
                "zps_components": zps_res.get("components", {}),
                "demands": demands_data,
                "road_status": road_status,
                "lat": lat,
                "lon": lon,
            }
            zone_profiles.append(zone_profile)

        # 5. Rank zones by Zone Priority Score (descending)
        zone_profiles.sort(key=lambda z: z["zps"], reverse=True)
        for rank, zp in enumerate(zone_profiles, start=1):
            zp["priority_rank"] = rank

        # 6. Write zone_needs to Blackboard
        self.write_section("zone_needs", zone_profiles)

        top_zone = zone_profiles[0] if zone_profiles else {}
        self.log(
            f"Needs assessment completed. Top priority: {top_zone.get('zone_name')} "
            f"(ZPS: {top_zone.get('zps')}, Rank 1)."
        )

        return {
            "status": "SUCCESS",
            "event_id": event_id,
            "disaster_type": disaster_type,
            "severity": severity,
            "planning_days": planning_days,
            "zones_assessed": len(zone_profiles),
            "top_priority_zone": {
                "zone_id": top_zone.get("zone_id"),
                "zone_name": top_zone.get("zone_name"),
                "zps": top_zone.get("zps"),
            },
            "total_demands": {
                "total_affected_population": total_affected,
                "total_displaced_population": round(total_displaced, 2),
                "total_water_liters": total_water_liters,
                "total_jerrycans_10l": total_jerrycans,
                "total_food_packs": total_food_packs,
                "total_medical_kits": total_medical_kits,
                "total_tents": total_tents,
            },
            "zone_needs": zone_profiles,
            "sop_context": sop_context,
            "summary": (
                f"Assessed {len(zone_profiles)} zones for {disaster_type} ({severity}). "
                f"Total affected: {total_affected:,}, Total displaced: {int(total_displaced):,}. "
                f"Highest urgency zone: {top_zone.get('zone_name')} (ZPS: {top_zone.get('zps')})."
            ),
        }


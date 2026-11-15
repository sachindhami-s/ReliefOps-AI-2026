"""
ReliefOps AI — Needs Assessment Semantic Kernel Plugin
Provides native Microsoft Semantic Kernel plugin functions for multi-hazard disaster needs assessment,
SOP-guided resource demand calculation, and hazard-specific Zone Priority Scoring (ZPS).

Academic Disclaimer:
Synthetic demonstration plugin developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
Formulations adhere to synthetic SOP-FL-001, SOP-EQ-002, SOP-CY-004, and SOP-LS-003 relief specifications.
"""

import json
import math
from typing import Annotated, Any, Dict, List, Optional
from semantic_kernel.functions import kernel_function


# Authoritative hazard configuration constants
HAZARD_SEVERITY_MAPS: Dict[str, Dict[str, str]] = {
    "FLOOD": {
        "MODERATE": "Level 2 (Moderate Inundation)",
        "SEVERE": "Level 3 (Severe Inundation)",
        "CATASTROPHIC": "Level 5 (Catastrophic Breach)",
        "LEVEL 1": "Level 1 (Minor Inundation)",
        "LEVEL 2": "Level 2 (Moderate Inundation)",
        "LEVEL 3": "Level 3 (Severe Inundation)",
        "LEVEL 4": "Level 4 (Critical Submersion)",
        "LEVEL 5": "Level 5 (Catastrophic Breach)",
    },
    "EARTHQUAKE": {
        "MODERATE": "Level 2 (Moderate Damage)",
        "SEVERE": "Level 3 (Heavy Damage)",
        "CATASTROPHIC": "Level 5 (Catastrophic Flattening)",
        "LEVEL 1": "Level 1 (Slight Damage)",
        "LEVEL 2": "Level 2 (Moderate Damage)",
        "LEVEL 3": "Level 3 (Heavy Damage)",
        "LEVEL 4": "Level 4 (Severe Structural Failure)",
        "LEVEL 5": "Level 5 (Catastrophic Flattening)",
    },
    "CYCLONE": {
        "MODERATE": "Level 2 (Severe Cyclone)",
        "SEVERE": "Level 3 (Very Severe Cyclone)",
        "CATASTROPHIC": "Level 5 (Super Cyclone)",
        "LEVEL 1": "Level 1 (Gale Force Warning)",
        "LEVEL 2": "Level 2 (Severe Cyclone)",
        "LEVEL 3": "Level 3 (Very Severe Cyclone)",
        "LEVEL 4": "Level 4 (Extremely Severe Cyclone)",
        "LEVEL 5": "Level 5 (Super Cyclone)",
    },
    "LANDSLIDE": {
        "MODERATE": "Level 2 (Partial Slide)",
        "SEVERE": "Level 3 (Major Slope Failure)",
        "CATASTROPHIC": "Level 5 (Village Burial / Mountain Collapse)",
        "LEVEL 1": "Level 1 (Rockfall Hazard)",
        "LEVEL 2": "Level 2 (Partial Slide)",
        "LEVEL 3": "Level 3 (Major Slope Failure)",
        "LEVEL 4": "Level 4 (Multi-Sector Blockade)",
        "LEVEL 5": "Level 5 (Village Burial / Mountain Collapse)",
    },
}

# Hazard-specific ZPS Priority Weights (SOP Section 4)
HAZARD_ZPS_WEIGHTS: Dict[str, Dict[str, float]] = {
    "FLOOD": {"damage": 0.35, "vulnerability": 0.25, "medical": 0.25, "population": 0.15},
    "EARTHQUAKE": {"damage": 0.30, "vulnerability": 0.20, "medical": 0.40, "population": 0.10},
    "CYCLONE": {"damage": 0.35, "vulnerability": 0.30, "medical": 0.20, "population": 0.15},
    "LANDSLIDE": {"damage": 0.40, "vulnerability": 0.20, "medical": 0.25, "population": 0.15},
}


class NeedsAssessmentPlugin:
    """
    Semantic Kernel plugin providing deterministic functions for evaluating disaster zone needs,
    retrieving domain SOP guidelines via RAG, and computing Zone Priority Scores (ZPS) across
    all four canonical hazard classifications (FLOOD, EARTHQUAKE, CYCLONE, LANDSLIDE).
    """

    HAZARD_SEVERITY_MAPS = HAZARD_SEVERITY_MAPS
    SEVERITY_SOP_LEVEL_MAP = HAZARD_SEVERITY_MAPS["FLOOD"]
    HAZARD_ZPS_WEIGHTS = HAZARD_ZPS_WEIGHTS

    @kernel_function(
        name="retrieve_sop_guidelines",
        description=(
            "Retrieves disaster management SOP standard guidelines, evacuation priorities, "
            "and resource norms using ChromaDB vector search and BM25 fallback."
        ),
    )
    def retrieve_sop_guidelines(
        self,
        disaster_type: Annotated[str, "Type of disaster (e.g. 'FLOOD', 'EARTHQUAKE', 'CYCLONE', 'LANDSLIDE')"],
        severity: Annotated[str, "Severity classification or level (e.g. 'Level 3', 'Severe', 'Critical')"],
    ) -> str:
        """
        Retrieves relevant SOP guidelines for the specified disaster hazard and severity.
        Dynamically adjusts retrieval parameters to prevent cross-hazard contamination.
        Maps the severity score to the hazard's authoritative SOP Section 2 scale.
        """
        try:
            from backend.rag import default_sop_retriever

            clean_disaster = (disaster_type or "FLOOD").strip().upper()
            clean_severity = (severity or "Level 3").strip()

            # Dynamic query without hardcoded hazard terms
            query = (
                f"{clean_disaster} disaster severity {clean_severity} emergency response "
                f"evacuation rescue vulnerable population relief standards"
            )

            # Apply hazard filter if disaster matches one of the canonical hazard types in the knowledge base
            known_hazards = {"FLOOD", "EARTHQUAKE", "CYCLONE", "LANDSLIDE"}
            hazard_filter = clean_disaster if clean_disaster in known_hazards else None

            retrieval_res = default_sop_retriever.retrieve(
                query=query,
                top_k=5,
                hazard_filter=hazard_filter,
            )

            chunks_payload = [
                {
                    "chunk_id": chunk.chunk_id,
                    "sop_id": chunk.sop_id,
                    "title": chunk.title,
                    "section_title": chunk.section_title,
                    "score": round(float(chunk.score), 4),
                    "content_excerpt": (chunk.content or "").strip()[:300],
                }
                for chunk in retrieval_res.retrieved_chunks
            ]

            # Resolve hazard-specific severity equivalence
            hazard_map = self.HAZARD_SEVERITY_MAPS.get(clean_disaster, self.HAZARD_SEVERITY_MAPS["FLOOD"])
            sop_equivalent = hazard_map.get(clean_severity.upper(), clean_severity)

            payload: Dict[str, Any] = {
                "status": "SUCCESS",
                "hazard": clean_disaster,
                "disaster_type": clean_disaster,
                "severity": clean_severity,
                "severity_level": clean_severity,
                "sop_severity_equivalent": sop_equivalent,
                "query": retrieval_res.query,
                "retrieval_method": retrieval_res.retrieval_method,
                "total_hits": retrieval_res.total_hits,
                "execution_time_ms": retrieval_res.execution_time_ms,
                "sop_ids": retrieval_res.sop_ids,
                "chunks": chunks_payload,
            }
            return json.dumps(payload, indent=2)

        except Exception as exc:
            fallback_hazard = (disaster_type or "FLOOD").strip().upper()
            return json.dumps(
                {
                    "status": "ERROR",
                    "hazard": fallback_hazard,
                    "disaster_type": fallback_hazard,
                    "error": str(exc),
                    "sop_ids": [],
                    "chunks": [],
                    "retrieval_method": "failed",
                }
            )

    @kernel_function(
        name="calculate_zone_demands",
        description=(
            "Calculates required physical humanitarian relief supplies (water, food ration packs, "
            "medical trauma kits, family tents) for an affected zone based on hazard-specific SOP standards."
        ),
    )
    def calculate_zone_demands(
        self,
        population: Annotated[int, "Total affected population of the zone"],
        vulnerability_idx: Annotated[float, "Demographic vulnerability index in [0.0, 1.0]"],
        damage_lvl: Annotated[float, "Damage severity level in [1.0, 5.0]"],
        medical_urgency: Annotated[float, "Medical urgency index in [0.0, 1.0]"],
        days: Annotated[int, "Planning horizon in days (default: 1)"] = 1,
        disaster_type: Annotated[str, "Hazard classification: FLOOD, EARTHQUAKE, CYCLONE, LANDSLIDE"] = "FLOOD",
    ) -> str:
        """
        Computes indivisible resource quantities following hazard-specific SOP specifications:
        - FLOOD (SOP-FL-001): 15L water/day, 1 kit/250 people (M >= 0.60), 1 tent/family displaced.
        - EARTHQUAKE (SOP-EQ-002): 10L water/day, aftershock displacement (70%-100%), 1 trauma kit/100 people (M >= 0.70).
        - CYCLONE (SOP-CY-004): 15L water/day (inland source), 1 anti-venom kit/200 people (M >= 0.50), 2 tie-down tents/tarps per family.
        - LANDSLIDE (SOP-LS-003): 10L water/day, 1 crush/hypothermia kit/150 people (M >= 0.50), alpine thermal tents.
        """
        try:
            clean_disaster = (disaster_type or "FLOOD").strip().upper()
            clean_pop = max(0, int(population))
            clean_dmg = max(1.0, min(5.0, float(damage_lvl)))
            clean_vuln = max(0.0, min(1.0, float(vulnerability_idx)))
            clean_med = max(0.0, min(1.0, float(medical_urgency)))
            clean_days = max(1, int(days))

            food_cycles = math.ceil(clean_days / 3.0)

            # Hazard-specific displacement, water, food, medical, and shelter norms
            if clean_disaster == "EARTHQUAKE":
                # SOP-EQ-002 Section 3: Aftershock panic displaces 70% to 100% of residents
                displacement_ratio = round(min(1.0, max(0.70, clean_dmg * 0.20)), 4)
                displaced_population = round(clean_pop * displacement_ratio, 4)
                displaced_families = math.ceil(displaced_population / 5.0) if displaced_population > 0 else 0

                water_liters = float(clean_pop * 10.0 * clean_days)  # 10.0 L/person/day
                tents = displaced_families
                food_packs = displaced_families * food_cycles
                # 1 Level-A Major Surgical & Orthopedic Trauma Kit per 100 people at medical urgency >= 0.70
                medical_kits = math.ceil(clean_pop / 100.0) if clean_med >= 0.70 and clean_pop > 0 else 0

            elif clean_disaster == "CYCLONE":
                # SOP-CY-004 Section 3: Coastal storm surge & structural destruction
                displacement_ratio = round(min(1.0, clean_dmg * 0.20), 4)
                displaced_population = round(clean_pop * displacement_ratio, 4)
                displaced_families = math.ceil(displaced_population / 5.0) if displaced_population > 0 else 0

                water_liters = float(clean_pop * 15.0 * clean_days)  # 15.0 L/person/day
                tents = displaced_families * 2  # 2 tie-down tarpaulins/tents per displaced family
                food_packs = displaced_families * food_cycles
                # 1 Anti-venom & waterborne disease kit per 200 people at medical urgency >= 0.50
                medical_kits = math.ceil(clean_pop / 200.0) if clean_med >= 0.50 and clean_pop > 0 else 0

            elif clean_disaster == "LANDSLIDE":
                # SOP-LS-003 Section 3: Slope failure and valley isolation
                displacement_ratio = round(min(1.0, clean_dmg * 0.20), 4)
                displaced_population = round(clean_pop * displacement_ratio, 4)
                displaced_families = math.ceil(displaced_population / 5.0) if displaced_population > 0 else 0

                water_liters = float(clean_pop * 10.0 * clean_days)  # 10.0 L/person/day
                tents = displaced_families  # Alpine thermal shelter units
                food_packs = displaced_families * food_cycles
                # 1 Crush injury & hypothermia kit per 150 people at medical urgency >= 0.50
                medical_kits = math.ceil(clean_pop / 150.0) if clean_med >= 0.50 and clean_pop > 0 else 0

            else:
                # SOP-FL-001 Section 3: Standard Riverine & Flash Flood
                displacement_ratio = round(min(1.0, clean_dmg * 0.20), 4)
                displaced_population = round(clean_pop * displacement_ratio, 4)
                displaced_families = math.ceil(displaced_population / 5.0) if displaced_population > 0 else 0

                water_liters = float(clean_pop * 15.0 * clean_days)  # 15.0 L/person/day
                tents = displaced_families
                food_packs = displaced_families * food_cycles
                # 1 Level-1 Trauma & Waterborne Disease kit per 250 people at medical urgency >= 0.60
                medical_kits = math.ceil(clean_pop / 250.0) if clean_med >= 0.60 and clean_pop > 0 else 0

            jerrycans_10l = math.ceil(water_liters / 10.0) if water_liters > 0 else 0

            result_payload: Dict[str, Any] = {
                "status": "SUCCESS",
                "hazard_type": clean_disaster,
                "population": clean_pop,
                "planning_days": clean_days,
                "displacement_ratio": displacement_ratio,
                "displaced_population": displaced_population,
                "demands": {
                    "water_liters": water_liters,
                    "jerrycans_10l": jerrycans_10l,
                    "food_packs": food_packs,
                    "food_replenishment_cycles": food_cycles,
                    "medical_kits": medical_kits,
                    "tents": tents,
                },
                "parameters": {
                    "damage_level": clean_dmg,
                    "vulnerability_index": clean_vuln,
                    "medical_urgency": clean_med,
                },
            }
            return json.dumps(result_payload, indent=2)

        except Exception as exc:
            return json.dumps({"status": "ERROR", "error": str(exc)})

    @kernel_function(
        name="compute_zone_priority",
        description=(
            "Calculates the Zone Priority Score (ZPS in [0, 100]) using hazard-specific SOP weights: "
            "Earthquake elevates medical (0.40) & damage (0.30); Flood uses damage (0.35), vuln (0.25), med (0.25)."
        ),
    )
    def compute_zone_priority(
        self,
        damage_lvl: Annotated[float, "Damage severity level in [1.0, 5.0]"],
        vulnerability_idx: Annotated[float, "Demographic vulnerability index in [0.0, 1.0]"],
        medical_urgency: Annotated[float, "Medical urgency index in [0.0, 1.0]"],
        population: Annotated[int, "Population of the zone being evaluated"],
        pop_max: Annotated[int, "Regional maximum population benchmark for normalization"],
        disaster_type: Annotated[str, "Hazard classification: FLOOD, EARTHQUAKE, CYCLONE, LANDSLIDE"] = "FLOOD",
    ) -> str:
        """
        Computes Zone Priority Score (ZPS) on a normalized 0–100 scale using hazard-specific SOP weights:
        - FLOOD: 0.35 * Damage + 0.25 * Vuln + 0.25 * Med + 0.15 * Pop
        - EARTHQUAKE: 0.30 * Damage + 0.20 * Vuln + 0.40 * Med + 0.10 * Pop (SOP-EQ-002 Section 4)
        - CYCLONE: 0.35 * Damage + 0.30 * Vuln + 0.20 * Med + 0.15 * Pop
        - LANDSLIDE: 0.40 * Damage + 0.20 * Vuln + 0.25 * Med + 0.15 * Pop
        """
        try:
            clean_disaster = (disaster_type or "FLOOD").strip().upper()
            clean_dmg = max(1.0, min(5.0, float(damage_lvl)))
            clean_vuln = max(0.0, min(1.0, float(vulnerability_idx)))
            clean_med = max(0.0, min(1.0, float(medical_urgency)))
            clean_pop = max(0, int(population))

            pop_max_effective = max(2, int(pop_max), clean_pop)

            weights = self.HAZARD_ZPS_WEIGHTS.get(clean_disaster, self.HAZARD_ZPS_WEIGHTS["FLOOD"])
            w_dmg = weights["damage"]
            w_vuln = weights["vulnerability"]
            w_med = weights["medical"]
            w_pop = weights["population"]

            damage_component = w_dmg * (clean_dmg / 5.0)
            vulnerability_component = w_vuln * clean_vuln
            medical_component = w_med * clean_med

            pop_numerator = math.log10(max(clean_pop, 1))
            pop_denominator = math.log10(pop_max_effective)
            population_component = w_pop * (pop_numerator / pop_denominator)

            raw_zps = 100.0 * (
                damage_component
                + vulnerability_component
                + medical_component
                + population_component
            )
            final_zps = max(0.0, min(100.0, round(raw_zps, 4)))

            payload: Dict[str, Any] = {
                "status": "SUCCESS",
                "hazard_type": clean_disaster,
                "zps": final_zps,
                "pop_max_effective": pop_max_effective,
                "weights_applied": {
                    "damage_weight": w_dmg,
                    "vulnerability_weight": w_vuln,
                    "medical_weight": w_med,
                    "population_weight": w_pop,
                },
                "components": {
                    "damage_weight": round(damage_component, 4),
                    "vulnerability_weight": round(vulnerability_component, 4),
                    "medical_weight": round(medical_component, 4),
                    "population_weight": round(population_component, 4),
                },
                "normalized_scores": {
                    "damage_ratio": round(clean_dmg / 5.0, 4),
                    "vulnerability_index": round(clean_vuln, 4),
                    "medical_urgency": round(clean_med, 4),
                    "population_ratio": round(pop_numerator / pop_denominator, 4),
                },
            }
            return json.dumps(payload, indent=2)

        except Exception as exc:
            return json.dumps({"status": "ERROR", "error": str(exc)})

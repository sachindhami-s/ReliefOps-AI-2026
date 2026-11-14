"""
ReliefOps AI — Needs Assessment Semantic Kernel Plugin
Provides native Microsoft Semantic Kernel plugin functions for disaster needs assessment,
SOP-guided resource demand calculation, and Zone Priority Scoring (ZPS).

Academic Disclaimer:
Synthetic demonstration plugin developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
Formulations adhere to synthetic SOP-FL-001 humanitarian relief specifications.
"""

import json
import math
from typing import Annotated, Any, Dict, List, Optional
from semantic_kernel.functions import kernel_function


class NeedsAssessmentPlugin:
    """
    Semantic Kernel plugin providing deterministic functions for evaluating disaster zone needs,
    retrieving domain SOP guidelines via RAG, and computing Zone Priority Scores (ZPS).
    """

    SEVERITY_SOP_LEVEL_MAP = {
        "MODERATE": "Level 2 (Moderate Inundation)",
        "SEVERE": "Level 3 (Severe Inundation)",
        "CATASTROPHIC": "Level 5 (Catastrophic Breach)",
        "LEVEL 1": "Level 1 (Minor Inundation)",
        "LEVEL 2": "Level 2 (Moderate Inundation)",
        "LEVEL 3": "Level 3 (Severe Inundation)",
        "LEVEL 4": "Level 4 (Critical Submersion)",
        "LEVEL 5": "Level 5 (Catastrophic Breach)",
    }

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

        Args:
            disaster_type: Hazard classification (e.g. FLOOD, EARTHQUAKE, CYCLONE, LANDSLIDE).
            severity: Disaster severity score or descriptive tier.

        Returns:
            JSON string containing sop_ids, retrieved chunks, score, and retrieval_method.
        """
        try:
            from backend.rag import default_sop_retriever

            clean_disaster = (disaster_type or "DISASTER").strip().upper()
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

            sop_equivalent = self.SEVERITY_SOP_LEVEL_MAP.get(clean_severity.upper(), clean_severity)

            payload: Dict[str, Any] = {
                "status": "SUCCESS",
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
            return json.dumps(
                {
                    "status": "ERROR",
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
            "medical trauma kits, family tents) for an affected zone based on SOP-FL-001 standards."
        ),
    )
    def calculate_zone_demands(
        self,
        population: Annotated[int, "Total affected population of the zone"],
        vulnerability_idx: Annotated[float, "Demographic vulnerability index in [0.0, 1.0]"],
        damage_lvl: Annotated[float, "Damage severity level in [1.0, 5.0]"],
        medical_urgency: Annotated[float, "Medical urgency index in [0.0, 1.0]"],
        days: Annotated[int, "Planning horizon in days (default: 1)"] = 1,
    ) -> str:
        """
        Computes indivisible resource quantities following SOP-FL-001 Section 3 humanitarian standards:
        - Damage Level: strictly clamped to [1.0, 5.0]
        - Displacement Ratio: min(1.0, DamageLevel * 0.20)
        - Clean Drinking Water: 15.0 L/person/day for total affected population
        - Food Rations: ceil(P_displaced / 5) * ceil(days / 3) 3-day family survival ration packs
        - Medical Kits: ceil(P_total / 250) Level-1 Trauma kits strictly when medical_urgency >= 0.60
        - Emergency Shelter: ceil(P_displaced / 5) weatherproof family tents

        Returns:
            JSON string containing discrete ceiling quantities for all resource SKUs.
        """
        try:
            # 1. Input normalization and bounds validation
            clean_pop = max(0, int(population))
            # Strict damage severity domain enforcement: D_i in [1.0, 5.0]
            clean_dmg = max(1.0, min(5.0, float(damage_lvl)))
            clean_vuln = max(0.0, min(1.0, float(vulnerability_idx)))
            clean_med = max(0.0, min(1.0, float(medical_urgency)))
            clean_days = max(1, int(days))

            # 2. Displacement calculations (SOP-FL-001 Section 3 & 3.4)
            # Displacement Ratio = min(1.0, DamageLevel * 0.20)
            displacement_ratio = round(min(1.0, clean_dmg * 0.20), 4)
            displaced_population = round(clean_pop * displacement_ratio, 4)

            # 3. Emergency Shelter: 1 tent per displaced family (average 5 individuals)
            tents = math.ceil(displaced_population / 5.0) if displaced_population > 0 else 0

            # 4. Clean Drinking Water (Sphere WASH 2.1): 15.0 L per person per day
            water_liters = float(clean_pop * 15.0 * clean_days)
            jerrycans_10l = math.ceil(water_liters / 10.0) if water_liters > 0 else 0

            # 5. Food Rations (Sphere Food 1.1): 3-day family packs on displaced population
            # Multi-cycle planning horizon: ceil(days / 3) replenishment tranches
            food_cycles = math.ceil(clean_days / 3.0)
            displaced_families = math.ceil(displaced_population / 5.0) if displaced_population > 0 else 0
            food_packs = displaced_families * food_cycles

            # 6. Emergency Medical Kits (SOP-FL-001 Section 3):
            # 1 Level-1 Trauma kit per 250 individuals strictly when medical urgency >= 0.60
            if clean_med >= 0.60 and clean_pop > 0:
                medical_kits = math.ceil(clean_pop / 250.0)
            else:
                medical_kits = 0

            result_payload: Dict[str, Any] = {
                "status": "SUCCESS",
                "population": clean_pop,
                "planning_days": clean_days,
                "displacement_ratio": round(displacement_ratio, 4),
                "displaced_population": round(displaced_population, 2),
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
            "Calculates the Zone Priority Score (ZPS in [0, 100]) using SOP-FL-001 Section 4 weights: "
            "0.35 damage severity, 0.25 vulnerability, 0.25 medical urgency, 0.15 population scale."
        ),
    )
    def compute_zone_priority(
        self,
        damage_lvl: Annotated[float, "Damage severity level in [1.0, 5.0]"],
        vulnerability_idx: Annotated[float, "Demographic vulnerability index in [0.0, 1.0]"],
        medical_urgency: Annotated[float, "Medical urgency index in [0.0, 1.0]"],
        population: Annotated[int, "Population of the zone being evaluated"],
        pop_max: Annotated[int, "Regional maximum population benchmark for normalization"],
    ) -> str:
        """
        Computes Zone Priority Score (ZPS) on a normalized 0–100 scale:
        ZPS = 100 * (0.35 * (D/5) + 0.25 * V + 0.25 * M + 0.15 * (log10(P) / log10(P_max_effective)))

        Enforces D_i in [1.0, 5.0] and P_max_effective = max(2, pop_max, population) to guarantee
        the population component never exceeds 1.0, even with inconsistent population benchmarks.

        Returns:
            JSON string containing overall ZPS and individual component weight contributions.
        """
        try:
            # 1. Strict input normalization & bounds validation
            clean_dmg = max(1.0, min(5.0, float(damage_lvl)))
            clean_vuln = max(0.0, min(1.0, float(vulnerability_idx)))
            clean_med = max(0.0, min(1.0, float(medical_urgency)))
            clean_pop = max(0, int(population))

            # 2. Strict population normalization benchmark
            # Ensures P_max is never smaller than P_i and never < 2
            pop_max_effective = max(2, int(pop_max), clean_pop)

            # 3. Component calculations (SOP-FL-001 Section 4)
            damage_component = 0.35 * (clean_dmg / 5.0)
            vulnerability_component = 0.25 * clean_vuln
            medical_component = 0.25 * clean_med

            pop_numerator = math.log10(max(clean_pop, 1))
            pop_denominator = math.log10(pop_max_effective)
            population_component = 0.15 * (pop_numerator / pop_denominator)

            # 4. Total ZPS synthesis (clamped to [0.0, 100.0])
            raw_zps = 100.0 * (
                damage_component
                + vulnerability_component
                + medical_component
                + population_component
            )
            final_zps = max(0.0, min(100.0, round(raw_zps, 4)))

            payload: Dict[str, Any] = {
                "status": "SUCCESS",
                "zps": final_zps,
                "pop_max_effective": pop_max_effective,
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

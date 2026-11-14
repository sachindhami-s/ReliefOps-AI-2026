"""
ReliefOps AI — Fairness and Distributive Justice Auditor Plugin
Evaluates allocation equity using the Gini coefficient, enforces the zero-allocation ban,
validates vulnerability and priority monotonicity, audits comprehensive resource adequacy,
and generates explainable audit reports and actionable recommendations.

Academic Disclaimer:
Synthetic demonstration platform developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import json
from typing import Annotated, Any, Dict, List, Optional
from semantic_kernel.functions import kernel_function


class FairnessPlugin:
    """Semantic Kernel plugin for auditing humanitarian distributive justice and resource adequacy."""

    GINI_THRESHOLD: float = 0.35

    DEMAND_ALIAS_MAP = {
        "FOOD_RATIONS": ["food_packs", "FOOD_RATIONS", "food_rations", "food"],
        "CLEAN_WATER": ["water_liters", "CLEAN_WATER", "clean_water", "water", "jerrycans_10l"],
        "MEDICAL_KITS": ["medical_kits", "MEDICAL_KITS", "trauma_kits"],
        "SHELTER_TENTS": ["tents", "emergency_shelter_tents", "SHELTER_TENTS", "shelter_tents"],
    }

    def __init__(self, gini_threshold: float = 0.35):
        self.gini_threshold: float = float(gini_threshold)

    @staticmethod
    def calculate_gini(values: List[float]) -> float:
        """
        Calculates the Gini coefficient for a non-negative sequence of coverage ratios.
        Returns 0.0 if values are empty or sum to 0.
        Formula: Gini = (2 * sum((i + 1) * y_i) - (n + 1) * sum(y_i)) / (n * sum(y_i))
        """
        if not values:
            return 0.0
        n = len(values)
        if n == 1:
            return 0.0

        total = sum(values)
        if total == 0.0:
            return 0.0

        sorted_vals = sorted(values)
        weighted_sum = sum((idx + 1) * val for idx, val in enumerate(sorted_vals))
        gini = (2.0 * weighted_sum - (n + 1) * total) / (n * total)
        return max(0.0, min(1.0, float(gini)))

    @staticmethod
    def determine_verdict(
        fairness_approved: bool,
        has_shortages: bool,
        is_complete_shortage: bool = False,
    ) -> str:
        """
        Verdict Engine mapping:
        - REJECTED: Fairness threshold violated or zero-allocation detected.
        - RESOURCE_SHORTAGE: Distributive fairness verified, but severe/total resource scarcity exists.
        - APPROVED_WITH_SHORTAGES: Distributive fairness verified, but partial resource shortages remain.
        - FAIRNESS_APPROVED: Distributive fairness verified and 100% resource adequacy achieved.
        """
        if not fairness_approved:
            return "REJECTED"
        if is_complete_shortage:
            return "RESOURCE_SHORTAGE"
        if has_shortages:
            return "APPROVED_WITH_SHORTAGES"
        return "FAIRNESS_APPROVED"

    @kernel_function(
        name="audit_allocation_equity",
        description=(
            "Audit relief allocation equity, vulnerability prioritization, and resource adequacy: "
            "computes Gini coefficient, zero-allocation ban, priority monotonicity, resource shortages, "
            "and generates explainable audit recommendations."
        ),
    )
    def audit_allocation_equity(
        self,
        allocations_json: Annotated[Any, "JSON list, dict, or dispatch array of allocated items per zone"],
        zone_demands_json: Annotated[Any, "JSON list or dict of zone needs containing zone_id, zps, demands"],
        inventory_snapshot_json: Annotated[Optional[Any], "Optional JSON inventory snapshot with available stock"] = None,
        gini_threshold: Annotated[Optional[float], "Configurable fairness Gini threshold (default: 0.35)"] = None,
    ) -> str:
        """
        Audits allocation equity and resource adequacy across multiple dimensions:
        1. Distributive Fairness Analysis (Gini coefficient, zero-allocation ban, priority monotonicity)
        2. Resource Adequacy Analysis (Requested, Available, Allocated, Fulfilled, Unfulfilled, Fulfillment %, Shortage %)
        3. Vulnerability Prioritisation Audit (Demographic vulnerability, damage severity, medical urgency, logistics access)
        4. Audit Verdict Engine (FAIRNESS_APPROVED, RESOURCE_SHORTAGE, APPROVED_WITH_SHORTAGES, REJECTED)
        5. Explainable Audit Report (Markdown explanation, zone-wise analysis, critical shortage alerts, actionable recommendations)
        """
        effective_threshold = float(gini_threshold) if gini_threshold is not None else self.gini_threshold

        try:
            # Handle empty or invalid inputs gracefully
            if allocations_json is None or zone_demands_json is None:
                return self._create_invalid_input_response(
                    "Missing allocation draft or zone demands.", effective_threshold
                )

            alloc_data = json.loads(allocations_json) if isinstance(allocations_json, str) else allocations_json
            zone_data = json.loads(zone_demands_json) if isinstance(zone_demands_json, str) else zone_demands_json
            inv_data = (
                json.loads(inventory_snapshot_json)
                if isinstance(inventory_snapshot_json, str)
                else (inventory_snapshot_json or {})
            )

            zones = zone_data.get("zones", zone_data) if isinstance(zone_data, dict) else zone_data
            if not isinstance(zones, list) or len(zones) == 0:
                return self._create_invalid_input_response(
                    "Empty zone demands list.", effective_threshold
                )

            # Canonicalize allocations per zone: {zone_id: {canonical_resource: allocated_qty}}
            zone_allocations: Dict[str, Dict[str, int]] = {}
            if isinstance(alloc_data, dict) and isinstance(alloc_data.get("dispatches"), list):
                alloc_items = alloc_data["dispatches"]
            elif isinstance(alloc_data, list):
                alloc_items = alloc_data
            elif isinstance(alloc_data, dict):
                alloc_items = []
                for zid, res_map in alloc_data.items():
                    if isinstance(res_map, dict):
                        for rtype_raw, qty in res_map.items():
                            alloc_items.append({"zone_id": zid, "resource_type": rtype_raw, "allocated_qty": qty})
            else:
                alloc_items = []

            for item in alloc_items:
                if not isinstance(item, dict):
                    continue
                zid = item.get("zone_id")
                rtype_raw = item.get("resource_type", "")
                qty = int(item.get("allocated_qty") or item.get("quantity") or 0)
                if not zid:
                    continue
                if zid not in zone_allocations:
                    zone_allocations[zid] = {}

                canon_rtype = rtype_raw
                for c_type, aliases in self.DEMAND_ALIAS_MAP.items():
                    if rtype_raw == c_type or rtype_raw in aliases:
                        canon_rtype = c_type
                        break
                zone_allocations[zid][canon_rtype] = zone_allocations[zid].get(canon_rtype, 0) + qty

            # -----------------------------------------------------------------
            # 1. Resource Adequacy Tracking Initialization
            # -----------------------------------------------------------------
            resource_totals: Dict[str, Dict[str, int]] = {
                c_type: {"demanded": 0, "allocated": 0, "available": 0}
                for c_type in self.DEMAND_ALIAS_MAP
            }

            # Populate available inventory
            if isinstance(inv_data, dict):
                tot_avail_map = inv_data.get("total_available", {})
                if tot_avail_map:
                    for c_type in self.DEMAND_ALIAS_MAP:
                        if c_type in tot_avail_map:
                            resource_totals[c_type]["available"] = int(tot_avail_map[c_type])
                elif "warehouses" in inv_data:
                    for wh in inv_data.get("warehouses", []):
                        res_dict = wh.get("resources", {})
                        for c_type in self.DEMAND_ALIAS_MAP:
                            if c_type in res_dict:
                                resource_totals[c_type]["available"] += int(
                                    res_dict[c_type].get("available_quantity", 0)
                                )
                elif "inventory" in inv_data:
                    for c_type, qty in inv_data["inventory"].items():
                        if c_type in resource_totals:
                            resource_totals[c_type]["available"] = int(qty)

            # Check if allocation draft has resource_summary with available stock
            if isinstance(alloc_data, dict) and "resource_summary" in alloc_data:
                for c_type, r_sum in alloc_data["resource_summary"].items():
                    if c_type in resource_totals and isinstance(r_sum, dict) and "available" in r_sum:
                        resource_totals[c_type]["available"] = max(
                            resource_totals[c_type]["available"], int(r_sum["available"])
                        )

            # -----------------------------------------------------------------
            # 2. Zone-wise Resource Allocation & Vulnerability Analysis
            # -----------------------------------------------------------------
            coverage_ratios: List[float] = []
            zone_summaries: List[Dict[str, Any]] = []
            violations: List[str] = []

            for z in zones:
                if not isinstance(z, dict):
                    continue
                zid = z.get("zone_id", "UNKNOWN")
                zname = z.get("zone_name") or z.get("name", zid)
                zps = float(z.get("zps") if "zps" in z else z.get("zps_score", 50.0))
                demands = z.get("demands", {}) if isinstance(z.get("demands"), dict) else {}
                params = z.get("parameters", {}) if isinstance(z.get("parameters"), dict) else {}

                pop = int(z.get("population") or z.get("affected_population") or params.get("population") or 1000)
                dmg = float(z.get("damage_level") or params.get("damage_level") or 2.0)
                vuln = float(z.get("vulnerability_index") or params.get("vulnerability_index") or 0.5)
                med = float(z.get("medical_urgency") or params.get("medical_urgency") or 0.5)
                access = str(z.get("access_status") or params.get("access_status") or "ACCESSIBLE").upper()

                total_demanded = 0
                total_allocated = 0
                allocated_for_zone = zone_allocations.get(zid, {})
                per_resource_coverage: Dict[str, float] = {}

                for c_type, aliases in self.DEMAND_ALIAS_MAP.items():
                    req_val = 0
                    for alias in aliases:
                        if alias in demands and demands[alias] is not None:
                            req_val = int(round(float(demands[alias])))
                            break
                    alloc_val = int(allocated_for_zone.get(c_type, 0))
                    total_demanded += req_val
                    total_allocated += alloc_val

                    resource_totals[c_type]["demanded"] += req_val
                    resource_totals[c_type]["allocated"] += alloc_val

                    if req_val > 0:
                        per_resource_coverage[c_type] = round(min(1.0, alloc_val / req_val), 4)

                coverage = (total_allocated / total_demanded) if total_demanded > 0 else 1.0
                coverage = min(1.0, max(0.0, coverage))
                coverage_ratios.append(coverage)

                # Check Zero-Allocation Ban
                if total_demanded > 0 and total_allocated == 0 and zps > 0 and pop > 0:
                    violations.append(
                        f"Zero-allocation violation: Zone '{zname}' ({zid}) with ZPS {zps:.1f} and population {pop:,} received 0% relief."
                    )

                # Zone Priority Explanation
                priority_explanation = (
                    f"Priority ZPS {zps:.1f}: Population {pop:,}, Damage {dmg:.1f}/5.0, "
                    f"Vulnerability {vuln:.2f}, Medical Urgency {med:.2f}, Logistics: {access}."
                )

                zone_summaries.append(
                    {
                        "zone_id": zid,
                        "zone_name": zname,
                        "zps": zps,
                        "population": pop,
                        "damage_level": dmg,
                        "vulnerability_index": vuln,
                        "medical_urgency": med,
                        "access_status": access,
                        "total_demanded": total_demanded,
                        "total_allocated": total_allocated,
                        "coverage_ratio": round(coverage, 4),
                        "resource_coverage": per_resource_coverage,
                        "priority_explanation": priority_explanation,
                    }
                )

            # -----------------------------------------------------------------
            # 3. Distributive Fairness Analysis (Gini & Priority Monotonicity)
            # -----------------------------------------------------------------
            gini = self.calculate_gini(coverage_ratios)
            min_cov = min(coverage_ratios) if coverage_ratios else 0.0

            if gini > effective_threshold:
                violations.append(
                    f"Gini index violation: Gini coefficient {gini:.4f} exceeds configured fairness threshold {effective_threshold:.2f}."
                )

            # Priority Monotonicity & Vulnerability Protection Check
            sorted_by_zps = sorted(zone_summaries, key=lambda x: x["zps"], reverse=True)
            for i in range(len(sorted_by_zps) - 1):
                high_z = sorted_by_zps[i]
                low_z = sorted_by_zps[i + 1]
                if high_z["zps"] - low_z["zps"] >= 10.0:
                    if high_z["coverage_ratio"] < low_z["coverage_ratio"] - 0.15:
                        if high_z["access_status"] in ["BLOCKED", "CUT_OFF", "IMPASSABLE"]:
                            violations.append(
                                f"Accessibility bottleneck: High priority zone '{high_z['zone_name']}' (ZPS {high_z['zps']:.1f}) "
                                f"has reduced coverage ({high_z['coverage_ratio']:.1%}) due to {high_z['access_status']} logistics access."
                            )
                        else:
                            violations.append(
                                f"Vulnerability prioritization violation: High priority zone '{high_z['zone_name']}' (ZPS {high_z['zps']:.1f}) "
                                f"received significantly lower coverage ({high_z['coverage_ratio']:.1%}) than lower priority zone '{low_z['zone_name']}' ({low_z['coverage_ratio']:.1%})."
                            )

            fairness_approved = (
                gini <= effective_threshold
                and not any("Zero-allocation" in v for v in violations)
                and not any("Vulnerability prioritization" in v for v in violations)
            )
            fairness_verdict = "FAIRNESS_APPROVED" if fairness_approved else "FAIRNESS_REJECTED"

            # -----------------------------------------------------------------
            # 4. Resource Adequacy Analysis
            # -----------------------------------------------------------------
            resource_adequacy: Dict[str, Dict[str, Any]] = {}
            shortage_resources: List[str] = []
            critical_shortages: List[str] = []
            critical_shortage_alerts: List[str] = []
            shortage_warnings: List[str] = []

            for c_type, totals in resource_totals.items():
                req_total = totals["demanded"]
                alloc_total = totals["allocated"]
                avail_total = (
                    totals["available"]
                    if (isinstance(inv_data, dict) and inv_data)
                    else max(totals["available"], alloc_total)
                )
                fulfilled = min(req_total, alloc_total)
                unfulfilled = max(0, req_total - alloc_total)

                # Standard Formula: Fulfilment % = (Allocated / Requested) * 100
                fulfill_pct = round((alloc_total / req_total * 100.0), 1) if req_total > 0 else 100.0
                shortage_pct = round((unfulfilled / req_total * 100.0), 1) if req_total > 0 else 0.0

                if req_total > 0 and unfulfilled > 0:
                    is_critical = fulfill_pct < 50.0 or (avail_total == 0 and req_total > 0)
                    res_status = "CRITICAL_SHORTAGE" if is_critical else "SHORTAGE"
                    shortage_resources.append(c_type)

                    warning_msg = (
                        f"{c_type} shortage: {alloc_total:,} / {req_total:,} fulfilled ({fulfill_pct:.1f}%) — "
                        f"{unfulfilled:,} unfulfilled ({shortage_pct:.1f}% shortage)."
                    )
                    shortage_warnings.append(warning_msg)

                    if is_critical or c_type in ["CLEAN_WATER", "SHELTER_TENTS", "FOOD_RATIONS", "MEDICAL_KITS"]:
                        critical_shortages.append(c_type)
                        critical_shortage_alerts.append(
                            f"🚨 Critical Shortage Alert: {c_type} demand at {req_total:,} units with only {alloc_total:,} allocated ({fulfill_pct:.1f}% fulfillment, {shortage_pct:.1f}% shortage)."
                        )
                else:
                    res_status = "ADEQUATE"

                resource_adequacy[c_type] = {
                    "resource_type": c_type,
                    "demanded": req_total,
                    "available": avail_total,
                    "allocated": alloc_total,
                    "fulfilled_qty": fulfilled,
                    "unfulfilled_qty": unfulfilled,
                    "fulfillment_pct": fulfill_pct,
                    "shortage_pct": shortage_pct,
                    "status": res_status,
                }

            has_shortages = len(shortage_resources) > 0
            adequacy_status = "RESOURCE_SHORTAGE" if has_shortages else "RESOURCE_ADEQUATE"

            # Determine complete shortage condition (all requested resources have 0 allocation or 0 stock)
            demanded_types = [t for t, d in resource_totals.items() if d["demanded"] > 0]
            is_complete_shortage = bool(
                demanded_types
                and all(resource_totals[t]["allocated"] == 0 for t in demanded_types)
            )

            # -----------------------------------------------------------------
            # 5. Audit Verdict Engine
            # -----------------------------------------------------------------
            audit_verdict = self.determine_verdict(
                fairness_approved=fairness_approved,
                has_shortages=has_shortages,
                is_complete_shortage=is_complete_shortage,
            )

            # Backward-compatible flags
            verdict = "APPROVED" if fairness_approved else "REJECTED"
            overall_status = "OVERALL_APPROVED" if audit_verdict == "FAIRNESS_APPROVED" else audit_verdict

            # -----------------------------------------------------------------
            # 6. Explainable Recommendations & Narrative Report
            # -----------------------------------------------------------------
            recommendations: List[str] = []
            if gini > effective_threshold:
                recommendations.append(
                    f"Increase baseline floor ratio in Phase 1 Water-Filling: Gini index ({gini:.4f}) exceeds the {effective_threshold:.2f} threshold."
                )
            if any("Zero-allocation" in v for v in violations):
                recommendations.append(
                    "Enforce strict non-zero allocation constraint: every affected administrative sector must receive essential survival supplies."
                )
            if any("Vulnerability prioritization" in v for v in violations):
                recommendations.append(
                    "Rebalance resource corridors toward high-vulnerability and high-medical-urgency zones before fulfilling low-priority quotas."
                )
            for c_res in set(critical_shortages):
                r_info = resource_adequacy.get(c_res, {})
                unf_q = r_info.get("unfulfilled_qty", 0)
                recommendations.append(
                    f"Procure emergency mutual aid supply for {c_res}: {unf_q:,} units required to reach 100% humanitarian sufficiency."
                )
            if not violations and not has_shortages:
                recommendations.append(
                    "Allocation plan meets both distributive justice criteria and 100% resource adequacy. Authorize immediate dispatch."
                )

            if not fairness_approved:
                explanation = f"Plan REJECTED with {len(violations)} distributive fairness and vulnerability violation(s)."
            elif is_complete_shortage:
                explanation = (
                    f"Distributive fairness evaluated, but critical RESOURCE_SHORTAGE detected across all requested supplies "
                    f"(0 units allocated out of {sum(t['demanded'] for t in resource_totals.values()):,} requested)."
                )
            elif has_shortages:
                explanation = (
                    f"Distributive fairness APPROVED (Gini={gini:.4f} <= {effective_threshold:.2f}), "
                    f"but operational resource shortages remain in: {', '.join(shortage_resources)}."
                )
            else:
                explanation = "Allocation plan meets both distributive justice criteria and 100% resource adequacy."

            return json.dumps(
                {
                    "success": True,
                    "verdict": verdict,
                    "audit_verdict": audit_verdict,
                    "overall_verdict": audit_verdict,
                    "fairness_verdict": fairness_verdict,
                    "adequacy_status": adequacy_status,
                    "overall_status": overall_status,
                    "gini_coefficient": round(gini, 4),
                    "min_coverage_ratio": round(min_cov, 4),
                    "gini_threshold": effective_threshold,
                    "zero_allocation_check_passed": not any("Zero-allocation" in v for v in violations),
                    "priority_monotonicity_passed": not any(
                        "monotonicity" in v.lower() or "vulnerability prioritization" in v.lower() for v in violations
                    ),
                    "violations": violations,
                    "shortage_resources": shortage_resources,
                    "critical_shortages": list(set(critical_shortages)),
                    "critical_shortage_alerts": critical_shortage_alerts,
                    "shortage_warnings": shortage_warnings,
                    "resource_adequacy": resource_adequacy,
                    "zone_summaries": zone_summaries,
                    "recommendations": recommendations,
                    "explanation": explanation,
                }
            )

        except Exception as exc:
            return self._create_invalid_input_response(str(exc), effective_threshold)

    def _create_invalid_input_response(self, error_msg: str, threshold: float) -> str:
        """Helper to create standardized rejected response for missing, empty, or invalid inputs."""
        return json.dumps(
            {
                "success": False,
                "verdict": "REJECTED",
                "audit_verdict": "REJECTED",
                "overall_verdict": "REJECTED",
                "fairness_verdict": "FAIRNESS_REJECTED",
                "adequacy_status": "RESOURCE_SHORTAGE",
                "overall_status": "REJECTED",
                "error": error_msg,
                "gini_coefficient": 1.0,
                "min_coverage_ratio": 0.0,
                "gini_threshold": threshold,
                "zero_allocation_check_passed": False,
                "priority_monotonicity_passed": False,
                "violations": [error_msg],
                "shortage_resources": [],
                "critical_shortages": [],
                "critical_shortage_alerts": [],
                "shortage_warnings": [],
                "resource_adequacy": {},
                "zone_summaries": [],
                "recommendations": ["Provide valid non-empty allocation dispatches and zone demand specifications."],
                "explanation": f"Audit rejected due to invalid input: {error_msg}",
            }
        )

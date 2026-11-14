"""
ReliefOps AI — Fairness and Distributive Justice Auditor Plugin
Evaluates allocation equity using the Gini coefficient, enforces the zero-allocation ban,
validates priority monotonicity, and audits aggregate resource adequacy across disaster zones.

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
        "FOOD_RATIONS": ["food_packs", "FOOD_RATIONS", "food_rations"],
        "CLEAN_WATER": ["water_liters", "CLEAN_WATER", "clean_water"],
        "MEDICAL_KITS": ["medical_kits", "MEDICAL_KITS"],
        "SHELTER_TENTS": ["tents", "emergency_shelter_tents", "SHELTER_TENTS", "shelter_tents"],
    }

    @staticmethod
    def calculate_gini(values: List[float]) -> float:
        """
        Calculates the Gini coefficient for a non-negative sequence of coverage ratios.
        Returns 0.0 if values are empty or sum to 0.
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

    @kernel_function(
        name="audit_allocation_equity",
        description=(
            "Audit relief allocation equity and resource adequacy: computes Gini coefficient, "
            "zero-allocation ban, priority monotonicity, and resource shortage metrics."
        ),
    )
    def audit_allocation_equity(
        self,
        allocations_json: Annotated[str, "JSON list or dict of allocated items per zone"],
        zone_demands_json: Annotated[str, "JSON list of zone needs containing zone_id, zps, demands"],
        inventory_snapshot_json: Annotated[Optional[str], "Optional JSON inventory snapshot with available stock"] = None,
    ) -> str:
        """
        Audits allocation equity across two independent dimensions:
        1. Distributive Fairness (FAIRNESS_APPROVED vs FAIRNESS_REJECTED)
        2. Resource Adequacy (RESOURCE_ADEQUATE vs RESOURCE_SHORTAGE)
        Synthesizes combined overall_status: OVERALL_APPROVED, APPROVED_WITH_SHORTAGES, or REJECTED.
        """
        try:
            alloc_data = json.loads(allocations_json) if isinstance(allocations_json, str) else allocations_json
            zone_data = json.loads(zone_demands_json) if isinstance(zone_demands_json, str) else zone_demands_json
            inv_data = (
                json.loads(inventory_snapshot_json)
                if isinstance(inventory_snapshot_json, str)
                else (inventory_snapshot_json or {})
            )

            zones = zone_data.get("zones", zone_data) if isinstance(zone_data, dict) else zone_data

            # Canonicalize allocations per zone: {zone_id: {canonical_resource: allocated_qty}}
            zone_allocations: Dict[str, Dict[str, int]] = {}
            if isinstance(alloc_data, dict) and isinstance(alloc_data.get("dispatches"), list):
                alloc_data = alloc_data["dispatches"]

            if isinstance(alloc_data, list):
                for item in alloc_data:
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
            elif isinstance(alloc_data, dict):
                for zid, res_map in alloc_data.items():
                    zone_allocations[zid] = {}
                    if isinstance(res_map, dict):
                        for rtype_raw, qty in res_map.items():
                            canon_rtype = rtype_raw
                            for c_type, aliases in self.DEMAND_ALIAS_MAP.items():
                                if rtype_raw == c_type or rtype_raw in aliases:
                                    canon_rtype = c_type
                                    break
                            zone_allocations[zid][canon_rtype] = zone_allocations[zid].get(canon_rtype, 0) + int(qty)

            # Track aggregate resource demands and allocations across all zones
            resource_totals: Dict[str, Dict[str, int]] = {
                c_type: {"demanded": 0, "allocated": 0, "available": 0}
                for c_type in self.DEMAND_ALIAS_MAP
            }

            # Populate available inventory if provided in inventory_snapshot
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
                                resource_totals[c_type]["available"] += int(res_dict[c_type].get("available_quantity", 0))

            coverage_ratios: List[float] = []
            zone_summaries: List[Dict[str, Any]] = []
            violations: List[str] = []

            for z in zones:
                zid = z.get("zone_id", "UNKNOWN")
                zname = z.get("zone_name") or z.get("name", zid)
                zps = float(z.get("zps") if "zps" in z else z.get("zps_score", 50.0))
                demands = z.get("demands", {})

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
                if total_demanded > 0 and total_allocated == 0 and zps > 0:
                    violations.append(
                        f"Zero-allocation violation: Zone '{zname}' ({zid}) with ZPS {zps:.1f} received 0% relief."
                    )

                zone_summaries.append(
                    {
                        "zone_id": zid,
                        "zone_name": zname,
                        "zps": zps,
                        "total_demanded": total_demanded,
                        "total_allocated": total_allocated,
                        "coverage_ratio": round(coverage, 4),
                        "resource_coverage": per_resource_coverage,
                    }
                )

            # Dimension A: Distributive Fairness Evaluation
            gini = self.calculate_gini(coverage_ratios)
            min_cov = min(coverage_ratios) if coverage_ratios else 0.0

            if gini > self.GINI_THRESHOLD:
                violations.append(
                    f"Gini index violation: Gini coefficient {gini:.4f} exceeds fairness threshold {self.GINI_THRESHOLD}."
                )

            # Monotonicity Check
            sorted_by_zps = sorted(zone_summaries, key=lambda x: x["zps"], reverse=True)
            for i in range(len(sorted_by_zps) - 1):
                high_z = sorted_by_zps[i]
                low_z = sorted_by_zps[i + 1]
                if high_z["zps"] - low_z["zps"] >= 10.0:
                    if high_z["coverage_ratio"] < low_z["coverage_ratio"] - 0.15:
                        violations.append(
                            f"Monotonicity warning: High priority zone '{high_z['zone_name']}' (ZPS {high_z['zps']:.1f}) "
                            f"has lower coverage ({high_z['coverage_ratio']:.1%}) than '{low_z['zone_name']}' ({low_z['coverage_ratio']:.1%})."
                        )

            fairness_approved = (
                gini <= self.GINI_THRESHOLD
                and not any("Zero-allocation" in v for v in violations)
            )
            fairness_verdict = "FAIRNESS_APPROVED" if fairness_approved else "FAIRNESS_REJECTED"
            verdict = "APPROVED" if fairness_approved else "REJECTED"

            # Dimension B: Resource Adequacy Evaluation
            resource_adequacy: Dict[str, Dict[str, Any]] = {}
            shortage_resources: List[str] = []
            shortage_warnings: List[str] = []

            for c_type, totals in resource_totals.items():
                req_total = totals["demanded"]
                alloc_total = totals["allocated"]
                # If inventory snapshot was not supplied, infer available from allocated
                avail_total = totals["available"] if (isinstance(inv_data, dict) and inv_data) else max(totals["available"], alloc_total)
                unfulfilled = max(0, req_total - alloc_total)
                fulfill_pct = round((alloc_total / req_total * 100.0), 1) if req_total > 0 else 100.0

                if req_total > 0 and unfulfilled > 0:
                    res_status = "CRITICAL_SHORTAGE" if fulfill_pct < 50.0 else "SHORTAGE"
                    shortage_resources.append(c_type)
                    shortage_warnings.append(
                        f"{c_type} shortage: {alloc_total:,} / {req_total:,} fulfilled ({fulfill_pct:.1f}%) — {unfulfilled:,} unfulfilled."
                    )
                else:
                    res_status = "ADEQUATE"

                resource_adequacy[c_type] = {
                    "resource_type": c_type,
                    "available": avail_total,
                    "demanded": req_total,
                    "allocated": alloc_total,
                    "unfulfilled_qty": unfulfilled,
                    "fulfillment_pct": fulfill_pct,
                    "status": res_status,
                }

            has_shortages = len(shortage_resources) > 0
            adequacy_status = "RESOURCE_SHORTAGE" if has_shortages else "RESOURCE_ADEQUATE"

            # Dimension C: Overall Status
            if not fairness_approved:
                overall_status = "REJECTED"
                explanation = f"Plan rejected with {len(violations)} distributive fairness violation(s)."
            elif has_shortages:
                overall_status = "APPROVED_WITH_SHORTAGES"
                explanation = (
                    f"Distributive fairness APPROVED (Gini={gini:.4f} <= {self.GINI_THRESHOLD}), "
                    f"but operational resource shortages remain in: {', '.join(shortage_resources)}."
                )
            else:
                overall_status = "OVERALL_APPROVED"
                explanation = "Allocation plan meets both distributive justice criteria and 100% resource adequacy."

            return json.dumps(
                {
                    "success": True,
                    "verdict": verdict,
                    "fairness_verdict": fairness_verdict,
                    "adequacy_status": adequacy_status,
                    "overall_status": overall_status,
                    "gini_coefficient": round(gini, 4),
                    "min_coverage_ratio": round(min_cov, 4),
                    "gini_threshold": self.GINI_THRESHOLD,
                    "zero_allocation_check_passed": not any("Zero-allocation" in v for v in violations),
                    "priority_monotonicity_passed": not any("Monotonicity" in v for v in violations),
                    "violations": violations,
                    "shortage_resources": shortage_resources,
                    "shortage_warnings": shortage_warnings,
                    "resource_adequacy": resource_adequacy,
                    "zone_summaries": zone_summaries,
                    "explanation": explanation,
                }
            )
        except Exception as exc:
            return json.dumps(
                {
                    "success": False,
                    "verdict": "REJECTED",
                    "fairness_verdict": "FAIRNESS_REJECTED",
                    "adequacy_status": "RESOURCE_SHORTAGE",
                    "overall_status": "REJECTED",
                    "error": str(exc),
                    "gini_coefficient": 1.0,
                    "violations": [str(exc)],
                }
            )

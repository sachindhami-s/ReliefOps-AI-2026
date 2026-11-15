"""
ReliefOps AI — Inventory Management Agent
Specialized agent responsible for assessing warehouse availability, tracking stock
levels across regional depots, identifying shortages, and reserving allocations.

Academic Disclaimer:
Synthetic demonstration agent developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import json
from typing import Any, Dict, List, Optional
from semantic_kernel import Kernel
from backend.agents.base_agent import BaseAgent
from backend.plugins.inventory_plugin import InventoryPlugin


class InventoryAgent(BaseAgent):
    """
    Inventory Agent for ReliefOps AI.
    Inherits from BaseAgent, integrates with Microsoft Semantic Kernel and InventoryPlugin,
    evaluates regional stock levels, computes supply vs demand feasibility, and writes to the Blackboard.
    """

    DEMAND_KEY_MAP = {
        "FOOD_RATIONS": ["food_packs", "FOOD_RATIONS", "food_rations"],
        "CLEAN_WATER": ["water_liters", "CLEAN_WATER", "clean_water"],
        "MEDICAL_KITS": ["medical_kits", "MEDICAL_KITS"],
        "SHELTER_TENTS": ["tents", "emergency_shelter_tents", "SHELTER_TENTS", "shelter_tents"],
    }

    def __init__(
        self,
        name: str = "InventoryAgent",
        kernel: Optional[Kernel] = None,
        blackboard: Optional[Any] = None,
        plugin: Optional[InventoryPlugin] = None,
    ):
        super().__init__(name=name, kernel=kernel, blackboard=blackboard)
        self.plugin = plugin or InventoryPlugin()

        # Register plugin with Semantic Kernel
        if "Inventory" not in self.kernel.plugins:
            self.kernel.add_plugin(self.plugin, plugin_name="Inventory")

    def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes stock auditing across operational depots and compares against zone demands.
        """
        self.log("Beginning inventory availability audit...")

        # 1. Retrieve zone needs from context or Blackboard
        zone_needs = None
        if context and "zone_needs" in context:
            zone_needs = context["zone_needs"]
        else:
            zone_needs = self.read_section("zone_needs")

        # 2. Query available inventory via plugin
        inv_raw = self.plugin.get_available_inventory()
        inv_data = json.loads(inv_raw) if isinstance(inv_raw, str) else inv_raw

        warehouses = inv_data.get("warehouses", [])

        # 3. Aggregate total available quantities across warehouses
        total_available = {
            "FOOD_RATIONS": 0,
            "CLEAN_WATER": 0,
            "MEDICAL_KITS": 0,
            "SHELTER_TENTS": 0,
        }
        for wh in warehouses:
            res_dict = wh.get("resources", {})
            for rtype in total_available:
                if rtype in res_dict:
                    total_available[rtype] += int(res_dict[rtype].get("available_quantity", 0))

        # 4. Compare with demands if zone_needs available
        total_demanded = {
            "FOOD_RATIONS": 0,
            "CLEAN_WATER": 0,
            "MEDICAL_KITS": 0,
            "SHELTER_TENTS": 0,
        }
        if zone_needs:
            zones = zone_needs.get("zones", zone_needs) if isinstance(zone_needs, dict) else zone_needs
            for z in zones:
                if not isinstance(z, dict):
                    continue
                demands = z.get("demands", {})
                for rtype, aliases in self.DEMAND_KEY_MAP.items():
                    for alias in aliases:
                        if alias in demands and demands[alias] is not None:
                            total_demanded[rtype] += int(round(float(demands[alias])))
                            break

        feasibility = {}
        shortage_resources = []
        for rtype in total_available:
            avail = total_available[rtype]
            req = total_demanded[rtype]
            allocated = min(avail, req)
            unfulfilled_qty = max(0, req - allocated)
            shortage_qty = unfulfilled_qty
            surplus_qty = max(0, avail - allocated)
            fulfillment_pct = round(min(100.0, (allocated / req * 100.0)), 1) if req > 0 else 100.0
            if req > 0 and unfulfilled_qty > 0:
                status = "CRITICAL_SHORTAGE" if fulfillment_pct < 50.0 else "SHORTAGE"
                shortage_resources.append(rtype)
            else:
                status = "ADEQUATE"

            feasibility[rtype] = {
                "demanded": req,
                "available": avail,
                "allocated": allocated,
                "fulfillment_pct": fulfillment_pct,
                "coverage_pct": fulfillment_pct,
                "unfulfilled_qty": unfulfilled_qty,
                "shortage_qty": shortage_qty,
                "surplus_qty": surplus_qty,
                "surplus_deficit": avail - req,
                "status": status,
            }

        adequacy_status = "RESOURCE_SHORTAGE" if shortage_resources else "RESOURCE_ADEQUATE"

        snapshot = {
            "warehouses": warehouses,
            "total_available": total_available,
            "total_demanded": total_demanded,
            "feasibility": feasibility,
            "adequacy_status": adequacy_status,
            "shortage_resources": shortage_resources,
            "total_warehouses": len(warehouses),
        }

        # 5. Write to Blackboard
        self.write_section("inventory_snapshot", snapshot)
        self.log(
            f"Inventory audit complete. {len(warehouses)} operational warehouses cataloged. "
            f"Adequacy: {adequacy_status}. "
            f"Stock feasibility: Food {feasibility['FOOD_RATIONS']['coverage_pct']}%, "
            f"Water {feasibility['CLEAN_WATER']['coverage_pct']}%, "
            f"Medical {feasibility['MEDICAL_KITS']['coverage_pct']}%, "
            f"Shelter {feasibility['SHELTER_TENTS']['coverage_pct']}%."
        )

        return {"status": "SUCCESS", "inventory_snapshot": snapshot}

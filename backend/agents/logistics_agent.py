"""
ReliefOps AI — Logistics and Transport Routing Agent
Specialized agent responsible for calculating geographic distance matrices,
evaluating road impedance, and planning rapid humanitarian transport dispatches.

Academic Disclaimer:
Synthetic demonstration agent developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import json
from typing import Any, Dict, List, Optional
from semantic_kernel import Kernel
from backend.agents.base_agent import BaseAgent
from backend.plugins.logistics_plugin import LogisticsPlugin


class LogisticsAgent(BaseAgent):
    """
    Logistics Agent for ReliefOps AI.
    Inherits from BaseAgent, integrates with Microsoft Semantic Kernel and LogisticsPlugin,
    computes warehouse-to-zone distance matrices, travel times, and writes to the Blackboard.
    """

    def __init__(
        self,
        name: str = "LogisticsAgent",
        kernel: Optional[Kernel] = None,
        blackboard: Optional[Any] = None,
        plugin: Optional[LogisticsPlugin] = None,
    ):
        super().__init__(name=name, kernel=kernel, blackboard=blackboard)
        self.plugin = plugin or LogisticsPlugin()

        if "Logistics" not in self.kernel.plugins:
            self.kernel.add_plugin(self.plugin, plugin_name="Logistics")

    def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Computes transit times and distance metrics between operational warehouses and affected zones.
        """
        self.log("Beginning logistics distance matrix evaluation...")

        # 1. Retrieve zone needs and inventory snapshot
        zone_needs = (context and context.get("zone_needs")) or self.read_section("zone_needs")
        inventory = (context and context.get("inventory_snapshot")) or self.read_section("inventory_snapshot")

        zones = []
        if zone_needs:
            zones = zone_needs.get("zones", zone_needs) if isinstance(zone_needs, dict) else zone_needs

        warehouses = []
        if inventory:
            warehouses = inventory.get("warehouses", []) if isinstance(inventory, dict) else inventory

        if not zones or not warehouses:
            self.log("Missing zones or warehouses data; using empty matrix.", level="WARNING")
            matrix_data = {"matrix": [], "total_connections": 0}
            self.write_section("logistics_matrix", matrix_data)
            return {"status": "SUCCESS", "logistics_matrix": matrix_data}

        # 2. Compute matrix using LogisticsPlugin
        matrix_raw = self.plugin.calculate_distance_matrix(warehouses, zones)
        matrix_data = json.loads(matrix_raw) if isinstance(matrix_raw, str) else matrix_raw

        # 3. Write to Blackboard
        self.write_section("logistics_matrix", matrix_data)
        self.log(
            f"Logistics matrix complete. Evaluated {matrix_data.get('total_connections', 0)} "
            f"warehouse-to-zone routes (winding factor: {self.plugin.WINDING_FACTOR})."
        )

        return {"status": "SUCCESS", "logistics_matrix": matrix_data}


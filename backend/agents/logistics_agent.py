"""
ReliefOps AI — Logistics and Transport Routing Agent (Phase 12 Upgraded)
Specialized agent responsible for calculating geographic distance matrices (supporting optional
OpenStreetMap/OSRM ROAD_NETWORK routing with automatic HAVERSINE_FALLBACK), evaluating road
impedance (OPEN, DEGRADED, BLOCKED, AIR_ONLY), and writing route geometry and metadata to the Blackboard.

Academic Disclaimer:
Synthetic demonstration agent developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import json
from typing import Any, Dict, Optional
from semantic_kernel import Kernel
from backend.agents.base_agent import BaseAgent
from backend.plugins.logistics_plugin import LogisticsPlugin


class LogisticsAgent(BaseAgent):
    """
    Logistics Agent for ReliefOps AI.
    Inherits from BaseAgent, integrates with Microsoft Semantic Kernel and LogisticsPlugin,
    computes warehouse-to-zone distance matrices, route geometries, travel times, and writes to the Blackboard.
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
        Computes transit times, route geometries, availability, and distance metrics between
        operational warehouses and affected zones.
        """
        self.log("Beginning logistics distance matrix & routing evaluation...")

        # 1. Retrieve zone needs, inventory snapshot, and optional routing configuration
        disaster_ctx = (context and context.get("disaster_context")) or self.read_section("disaster_context") or {}
        zone_needs = (context and context.get("zone_needs")) or self.read_section("zone_needs")
        inventory = (context and context.get("inventory_snapshot")) or self.read_section("inventory_snapshot")

        routing_mode = (
            (context and context.get("routing_mode"))
            or (disaster_ctx.get("routing_mode") if isinstance(disaster_ctx, dict) else None)
            or self.plugin.routing_mode
        )
        osrm_base_url = (
            (context and context.get("osrm_base_url"))
            or (disaster_ctx.get("osrm_base_url") if isinstance(disaster_ctx, dict) else None)
            or self.plugin.osrm_base_url
        )

        zones = []
        if zone_needs:
            zones = zone_needs.get("zones", zone_needs) if isinstance(zone_needs, dict) else zone_needs

        warehouses = []
        if inventory:
            warehouses = inventory.get("warehouses", []) if isinstance(inventory, dict) else inventory

        if not zones or not warehouses:
            self.log("Missing zones or warehouses data; using empty matrix.", level="WARNING")
            matrix_data = {
                "success": True,
                "matrix": [],
                "total_connections": 0,
                "routing_mode_requested": routing_mode,
                "active_routing_method": routing_mode,
                "fallback_used": False,
                "routing_summary": {
                    "routing_mode_requested": routing_mode,
                    "active_routing_method": routing_mode,
                    "total_routes": 0,
                    "road_network_routes": 0,
                    "haversine_routes": 0,
                    "fallback_routes": 0,
                    "blocked_routes": 0,
                    "invalid_routes": 0,
                    "fallback_used": False,
                },
            }
            self.write_section("logistics_matrix", matrix_data)
            return {"status": "SUCCESS", "logistics_matrix": matrix_data}

        # 2. Compute matrix using LogisticsPlugin (ROAD_NETWORK or HAVERSINE_FALLBACK)
        matrix_raw = self.plugin.calculate_distance_matrix(
            warehouses,
            zones,
            routing_mode=routing_mode,
            osrm_base_url=osrm_base_url,
        )
        matrix_data = json.loads(matrix_raw) if isinstance(matrix_raw, str) else matrix_raw

        # 3. Write to Blackboard
        self.write_section("logistics_matrix", matrix_data)
        summary = matrix_data.get("routing_summary", {})
        self.log(
            f"Logistics matrix complete. Evaluated {matrix_data.get('total_connections', 0)} routes "
            f"[requested={summary.get('routing_mode_requested', routing_mode)}, "
            f"active={summary.get('active_routing_method', routing_mode)}, "
            f"road_network={summary.get('road_network_routes', 0)}, "
            f"fallback={summary.get('fallback_routes', 0)}, "
            f"blocked={summary.get('blocked_routes', 0)}]."
        )

        return {"status": "SUCCESS", "logistics_matrix": matrix_data}

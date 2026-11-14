"""
ReliefOps AI — Plugins Module
Exports all Semantic Kernel plugins for disaster needs assessment, inventory management,
logistics routing, distributive fairness auditing, and multi-agent coordination.

Academic Disclaimer:
Synthetic demonstration platform developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

from backend.plugins.needs_plugin import NeedsAssessmentPlugin
from backend.plugins.inventory_plugin import InventoryPlugin
from backend.plugins.logistics_plugin import LogisticsPlugin
from backend.plugins.fairness_plugin import FairnessPlugin
from backend.plugins.coordinator_plugin import CoordinatorPlugin

__all__ = [
    "NeedsAssessmentPlugin",
    "InventoryPlugin",
    "LogisticsPlugin",
    "FairnessPlugin",
    "CoordinatorPlugin",
]

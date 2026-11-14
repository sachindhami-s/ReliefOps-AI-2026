"""
ReliefOps AI — Agents Module
Exports all specialized multi-agent components for disaster response coordination.

Academic Disclaimer:
Synthetic demonstration platform developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

from backend.agents.base_agent import BaseAgent
from backend.agents.needs_assessment_agent import NeedsAssessmentAgent
from backend.agents.inventory_agent import InventoryAgent
from backend.agents.logistics_agent import LogisticsAgent
from backend.agents.fairness_auditor_agent import FairnessAuditorAgent
from backend.agents.relief_coordinator import ReliefCoordinator

__all__ = [
    "BaseAgent",
    "NeedsAssessmentAgent",
    "InventoryAgent",
    "LogisticsAgent",
    "FairnessAuditorAgent",
    "ReliefCoordinator",
]

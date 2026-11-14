"""
ReliefOps AI — Orchestrator module alias.
Re-exports ReliefCoordinator from backend.agents.relief_coordinator for backward and cross-module compatibility.

Academic Disclaimer:
Synthetic demonstration platform developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

from backend.agents.relief_coordinator import ReliefCoordinator

__all__ = ["ReliefCoordinator"]

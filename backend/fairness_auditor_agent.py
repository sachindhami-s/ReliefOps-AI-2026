"""
ReliefOps AI — Fairness Auditor Agent alias.
Re-exports FairnessAuditorAgent from backend.agents.fairness_auditor_agent for backward and root-level package compatibility.

Academic Disclaimer:
Synthetic demonstration platform developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

from backend.agents.fairness_auditor_agent import FairnessAuditorAgent

__all__ = ["FairnessAuditorAgent"]

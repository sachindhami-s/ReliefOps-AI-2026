"""
ReliefOps AI — Base Agent Architecture
Provides the abstract BaseAgent class with Microsoft Semantic Kernel integration,
Blackboard read/write hooks, structured logging, and lifecycle execution management.

Academic Disclaimer:
Synthetic demonstration agent developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, List, Optional
from semantic_kernel import Kernel


class BaseAgent(ABC):
    """
    Abstract base agent defining standardized lifecycle methods, Blackboard state
    access, structured event logging, and Microsoft Semantic Kernel integration.
    """

    def __init__(
        self,
        name: str,
        kernel: Optional[Kernel] = None,
        blackboard: Optional[Any] = None,
    ):
        """
        Initializes the agent with an identity, Semantic Kernel instance, and Blackboard reference.

        Args:
            name: Human-readable agent identifier (e.g. 'NeedsAssessmentAgent').
            kernel: Optional Microsoft Semantic Kernel instance. If None, instantiates a fresh Kernel.
            blackboard: Optional shared Blackboard reference (BlackboardManager or dictionary).
        """
        self.name = name
        self.kernel = kernel or Kernel()
        self.blackboard = blackboard
        self.logger = logging.getLogger(f"reliefops.agent.{self.name}")
        self.log_history: List[str] = []

    def log(self, message: str, level: str = "INFO") -> None:
        """Records a timestamped structured log entry."""
        log_entry = f"[{self.name}] {message}"
        self.log_history.append(log_entry)
        level_upper = level.upper()
        if level_upper == "ERROR":
            self.logger.error(log_entry)
        elif level_upper == "WARNING":
            self.logger.warning(log_entry)
        else:
            self.logger.info(log_entry)

    def read_section(self, section_name: str) -> Any:
        """
        Reads a named section from the shared Blackboard.
        Supports BlackboardManager instances (with .read()), dict-like objects, or None.
        """
        if self.blackboard is None:
            return None
        if hasattr(self.blackboard, "read"):
            return self.blackboard.read(section_name)
        if isinstance(self.blackboard, dict):
            return self.blackboard.get(section_name)
        if hasattr(self.blackboard, section_name):
            return getattr(self.blackboard, section_name)
        return None

    def write_section(self, section_name: str, data: Any) -> None:
        """
        Writes data to a named section of the shared Blackboard.
        Supports BlackboardManager instances (with .update()), dict-like objects, or direct attributes.
        """
        if self.blackboard is None:
            self.log(
                f"Blackboard not attached; buffering write to section '{section_name}' in memory.",
                level="WARNING",
            )
            return

        if isinstance(self.blackboard, dict):
            self.blackboard[section_name] = data
        elif hasattr(self.blackboard, "update"):
            try:
                self.blackboard.update(section_name, data, agent_name=self.name)
            except TypeError:
                self.blackboard.update(section_name, data)
        else:
            setattr(self.blackboard, section_name, data)

        self.log(f"Updated blackboard section '{section_name}'.")

    @abstractmethod
    def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes the agent's core decision-making cycle.
        Must be implemented by concrete subclasses.

        Args:
            context: Optional contextual parameters (overrides or supplements Blackboard state).

        Returns:
            Structured execution results dictionary.
        """
        pass

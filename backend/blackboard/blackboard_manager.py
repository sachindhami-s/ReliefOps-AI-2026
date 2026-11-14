"""
ReliefOps AI — Thread-Safe Blackboard Manager
Provides centralized in-memory shared state for multi-agent coordination with
optional persistent event auditing to the SQLite blackboard_events table.

Academic Disclaimer:
Synthetic demonstration platform developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import datetime
import json
import logging
import threading
from typing import Any, Dict, List, Optional
from backend.database.db_manager import DatabaseManager, default_db_manager

logger = logging.getLogger("reliefops.blackboard")


class BlackboardManager:
    """
    Central shared state repository implementing the Hayes-Roth Blackboard pattern.
    Thread-safe and capable of logging all section mutations to SQLite blackboard_events.
    """

    def __init__(self, db: Optional[DatabaseManager] = None):
        """
        Initializes an empty blackboard state with a thread lock.

        Args:
            db: Optional DatabaseManager for persisting blackboard events. If None, uses default_db_manager.
        """
        self._lock = threading.Lock()
        self._state: Dict[str, Any] = {}
        self._events: List[Dict[str, Any]] = []
        self._db = db or default_db_manager

    def read(self, section: str) -> Any:
        """
        Retrieves the current value of a blackboard section in a thread-safe manner.

        Args:
            section: Name of the blackboard section (e.g. 'disaster_context', 'zone_needs').

        Returns:
            The stored data, or None if the section has not been populated.
        """
        with self._lock:
            return self._state.get(section)

    def update(self, section: str, data: Any, agent_name: str = "System", plan_id: str = "PLAN-ACTIVE") -> None:
        """
        Updates a blackboard section, records the in-memory event, and writes an audit log to SQLite.

        Args:
            section: Target section name.
            data: Data payload to store.
            agent_name: Name of the agent performing the mutation.
            plan_id: Associated relief plan identifier for tracking.
        """
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._lock:
            self._state[section] = data
            event_record = {
                "plan_id": plan_id,
                "agent_name": agent_name,
                "action_type": "UPDATE",
                "target_section": section,
                "timestamp": timestamp,
            }
            self._events.append(event_record)

        # Persist event to SQLite blackboard_events table (fail-safe)
        try:
            payload_str = json.dumps(data) if not isinstance(data, str) else data
            self._db.execute_non_query(
                """
                INSERT INTO blackboard_events (plan_id, agent_name, action_type, target_section, payload_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (plan_id, agent_name, "UPDATE", section, payload_str, timestamp),
            )
        except Exception as exc:
            logger.warning(f"Could not persist blackboard event to database: {exc}")

    def get_snapshot(self) -> Dict[str, Any]:
        """Returns a shallow copy of the entire blackboard state."""
        with self._lock:
            return dict(self._state)

    def get_event_history(self) -> List[Dict[str, Any]]:
        """Returns a copy of all recorded in-memory events."""
        with self._lock:
            return list(self._events)

    def clear(self) -> None:
        """Resets the in-memory blackboard state and event history."""
        with self._lock:
            self._state.clear()
            self._events.clear()


# Default global blackboard instance for seamless coordinator access
default_blackboard = BlackboardManager()


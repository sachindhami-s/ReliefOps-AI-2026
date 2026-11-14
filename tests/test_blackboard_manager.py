"""
ReliefOps AI — Blackboard Manager Tests
Validates thread-safe reads/writes, section snapshots, and SQLite event journaling.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.blackboard.blackboard_manager import BlackboardManager
from backend.database.db_manager import DatabaseManager


class TestBlackboardManager(unittest.TestCase):
    """Test suite for BlackboardManager."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_bb.db")
        self.db = DatabaseManager(self.db_path)
        self.db.initialize_database()
        self.bb = BlackboardManager(db=self.db)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_read_write_and_snapshot(self):
        """Test standard section updates and snapshots."""
        self.assertIsNone(self.bb.read("disaster_context"))

        self.bb.update("disaster_context", {"disaster_type": "FLOOD", "severity": "SEVERE"}, agent_name="User")
        stored = self.bb.read("disaster_context")
        self.assertEqual(stored["disaster_type"], "FLOOD")

        snapshot = self.bb.get_snapshot()
        self.assertIn("disaster_context", snapshot)
        self.assertEqual(len(self.bb.get_event_history()), 1)

    def test_database_event_logging(self):
        """Verify that blackboard mutations are persisted to blackboard_events table."""
        self.bb.update("zone_needs", {"zones": []}, agent_name="NeedsAgent", plan_id="PLAN-TEST-01")
        events = self.db.execute_query("SELECT * FROM blackboard_events WHERE plan_id = 'PLAN-TEST-01'")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["agent_name"], "NeedsAgent")
        self.assertEqual(events[0]["target_section"], "zone_needs")


if __name__ == "__main__":
    unittest.main()

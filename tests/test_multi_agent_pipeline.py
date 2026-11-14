"""
ReliefOps AI — Multi-Agent End-to-End Coordination Pipeline Test
Validates that the complete multi-agent system runs sequentially on a realistic disaster scenario:
Disaster Context -> Needs Assessment (RAG) -> Inventory -> Logistics -> Coordinator -> Fairness Auditor -> SQLite Persistence
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.blackboard import BlackboardManager
from backend.database.db_manager import DatabaseManager
from backend.database.seeder import seed_database
from backend.agents.relief_coordinator import ReliefCoordinator


class TestMultiAgentPipeline(unittest.TestCase):
    """End-to-end test suite for the complete ReliefOps AI multi-agent workflow."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_pipeline.db")
        self.db = DatabaseManager(self.db_path)
        seed_database(self.db)
        self.bb = BlackboardManager(db=self.db)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_end_to_end_flood_relief_coordination(self):
        """Executes full coordination cycle on a 3-zone flood scenario."""
        coordinator = ReliefCoordinator(blackboard=self.bb, db=self.db)

        scenario_context = {
            "event_id": "EVT-2026-FL01",
            "disaster_type": "FLOOD",
            "severity_level": "SEVERE",
            "planning_days": 3,
            "zones": [
                {
                    "zone_id": "ZONE-MAJULI",
                    "name": "Majuli Riverine Sector",
                    "population": 45000,
                    "damage_level": 4,
                    "vulnerability_index": 0.88,
                    "medical_urgency": 0.85,
                    "access_status": "DEGRADED",
                    "latitude": 26.96,
                    "longitude": 94.22,
                },
                {
                    "zone_id": "ZONE-DHEMAJI",
                    "name": "Dhemaji Submerged Sector",
                    "population": 32000,
                    "damage_level": 5,
                    "vulnerability_index": 0.92,
                    "medical_urgency": 0.95,
                    "access_status": "BLOCKED",
                    "latitude": 27.48,
                    "longitude": 94.58,
                },
                {
                    "zone_id": "ZONE-NAGAON",
                    "name": "Nagaon Plains Area",
                    "population": 65000,
                    "damage_level": 2,
                    "vulnerability_index": 0.60,
                    "medical_urgency": 0.35,
                    "access_status": "OPEN",
                    "latitude": 26.35,
                    "longitude": 92.68,
                },
            ],
        }

        final_plan = coordinator.run_full_coordination_cycle(disaster_context=scenario_context)

        # 1. Verify Plan Generation
        self.assertIn(final_plan["status"], ["APPROVED", "APPROVED_WITH_SHORTAGES", "OVERALL_APPROVED", "WARNING_OVERRIDDEN"])
        self.assertGreater(final_plan["total_dispatches"], 0)

        # 2. Verify Blackboard State Sections
        snapshot = self.bb.get_snapshot()
        self.assertIn("disaster_context", snapshot)
        self.assertIn("zone_needs", snapshot)
        self.assertIn("sop_context", snapshot)
        self.assertIn("inventory_snapshot", snapshot)
        self.assertIn("logistics_matrix", snapshot)
        self.assertIn("allocation_draft", snapshot)
        self.assertIn("audit_verdict", snapshot)
        self.assertIn("final_allocation_plan", snapshot)

        # 3. Verify SOP guidelines retrieval
        sop_ctx = self.bb.read("sop_context")
        self.assertIn("chunks", sop_ctx)
        self.assertGreater(len(sop_ctx["chunks"]), 0)

        # 4. Verify ZPS ranking
        zone_needs = self.bb.read("zone_needs")
        zones = zone_needs if isinstance(zone_needs, list) else zone_needs.get("zones", [])
        self.assertEqual(len(zones), 3)
        # Dhemaji (dmg 5, vuln 0.92, med 0.95) should have higher ZPS than Nagaon (dmg 2, vuln 0.6, med 0.35)
        dhemaji = next(z for z in zones if z["zone_id"] == "ZONE-DHEMAJI")
        nagaon = next(z for z in zones if z["zone_id"] == "ZONE-NAGAON")
        self.assertGreater(dhemaji["zps"], nagaon["zps"])

        # 5. Verify Database Persistence
        db_plans = self.db.execute_query(f"SELECT * FROM allocation_plans WHERE plan_id = '{final_plan['plan_id']}'")
        self.assertEqual(len(db_plans), 1)

        db_items = self.db.execute_query(f"SELECT * FROM allocation_items WHERE plan_id = '{final_plan['plan_id']}'")
        self.assertGreater(len(db_items), 0)


if __name__ == "__main__":
    unittest.main()

"""
ReliefOps AI — Phase 3 Agent & Plugin Tests
Validates InventoryPlugin, LogisticsPlugin, FairnessPlugin, CoordinatorPlugin, and their corresponding agents.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.blackboard import BlackboardManager
from backend.database.db_manager import DatabaseManager
from backend.database.seeder import seed_database
from backend.plugins.inventory_plugin import InventoryPlugin
from backend.plugins.logistics_plugin import LogisticsPlugin
from backend.plugins.fairness_plugin import FairnessPlugin
from backend.plugins.coordinator_plugin import CoordinatorPlugin
from backend.agents.inventory_agent import InventoryAgent
from backend.agents.logistics_agent import LogisticsAgent
from backend.agents.fairness_auditor_agent import FairnessAuditorAgent


class TestPhase3AgentsAndPlugins(unittest.TestCase):
    """Unit tests for Phase 3 components."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_p3.db")
        self.db = DatabaseManager(self.db_path)
        seed_database(self.db)
        self.bb = BlackboardManager(db=self.db)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_inventory_plugin_and_agent(self):
        """Test InventoryPlugin stock retrieval and InventoryAgent execution."""
        plugin = InventoryPlugin(db=self.db)
        inv_raw = plugin.get_available_inventory()
        inv_data = json.loads(inv_raw)
        self.assertTrue(inv_data["success"])
        self.assertGreater(inv_data["total_warehouses"], 0)

        agent = InventoryAgent(blackboard=self.bb, plugin=plugin)
        res = agent.execute()
        self.assertEqual(res["status"], "SUCCESS")
        snapshot = self.bb.read("inventory_snapshot")
        self.assertIsNotNone(snapshot)
        self.assertIn("total_available", snapshot)

    def test_logistics_plugin_and_agent(self):
        """Test LogisticsPlugin haversine calculations and LogisticsAgent execution."""
        plugin = LogisticsPlugin()
        whs = [{"warehouse_id": "WH-1", "latitude": 26.18, "longitude": 91.73, "name": "Guwahati Depot"}]
        zones = [{"zone_id": "ZONE-1", "latitude": 26.96, "longitude": 94.22, "name": "Majuli Sector", "access_status": "DEGRADED"}]

        res_raw = plugin.calculate_distance_matrix(whs, zones)
        matrix = json.loads(res_raw)
        self.assertTrue(matrix["success"])
        self.assertEqual(len(matrix["matrix"]), 1)
        eff_km = matrix["matrix"][0]["effective_km"]
        self.assertGreater(eff_km, 200.0)

        # Logistics Agent execution
        self.bb.update("zone_needs", {"zones": zones})
        self.bb.update("inventory_snapshot", {"warehouses": whs})
        agent = LogisticsAgent(blackboard=self.bb, plugin=plugin)
        exec_res = agent.execute()
        self.assertEqual(exec_res["status"], "SUCCESS")
        self.assertIsNotNone(self.bb.read("logistics_matrix"))

    def test_fairness_plugin_gini_and_agent(self):
        """Test Gini calculation, zero-allocation ban, and FairnessAuditorAgent."""
        plugin = FairnessPlugin()

        # Perfect equality: all zones get 50%
        perfect_eq = [0.5, 0.5, 0.5, 0.5]
        self.assertAlmostEqual(plugin.calculate_gini(perfect_eq), 0.0, places=3)

        # Extreme inequality: one zone gets 100%, others get 0
        extreme_ineq = [1.0, 0.0, 0.0, 0.0]
        self.assertGreater(plugin.calculate_gini(extreme_ineq), 0.5)

        # Test agent execution with mock data
        zones = [
            {"zone_id": "Z1", "zone_name": "Zone 1", "zps_score": 80.0, "demands": {"food_packs": 100}},
            {"zone_id": "Z2", "zone_name": "Zone 2", "zps_score": 60.0, "demands": {"food_packs": 100}},
        ]
        dispatches = [
            {"zone_id": "Z1", "resource_type": "FOOD_RATIONS", "allocated_qty": 50},
            {"zone_id": "Z2", "resource_type": "FOOD_RATIONS", "allocated_qty": 50},
        ]
        self.bb.update("zone_needs", {"zones": zones})
        self.bb.update("allocation_draft", {"dispatches": dispatches, "plan_id": "PLAN-T1"})

        agent = FairnessAuditorAgent(blackboard=self.bb, plugin=plugin, db=self.db)
        res = agent.execute()
        self.assertEqual(res["status"], "SUCCESS")
        verdict = self.bb.read("audit_verdict")
        self.assertEqual(verdict["verdict"], "APPROVED")


if __name__ == "__main__":
    unittest.main()

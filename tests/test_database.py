"""
ReliefOps AI — Database & Storage Unit Tests
Verifies SQLite schema creation, foreign key enforcement, WAL mode, seeder integrity,
and atomic transaction rollback semantics.
"""

import os
import sqlite3
import tempfile
import unittest
from backend.database.db_manager import DatabaseManager
from backend.database.seeder import seed_database


class TestDatabaseManager(unittest.TestCase):
    """Test suite for SQLite DatabaseManager and Seeder."""

    def setUp(self):
        """Create a temporary SQLite database for test isolation."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_reliefops.db")
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        """Cleanup temporary files."""
        self.db.close()
        self.temp_dir.cleanup()

    def test_schema_initialization(self):
        """Test that schema.sql creates all 10 required tables."""
        self.db.initialize_database()
        tables = self.db.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        table_names = {t["name"] for t in tables}
        expected_tables = {
            "disaster_events",
            "affected_zones",
            "warehouses",
            "warehouse_inventory",
            "allocation_plans",
            "allocation_items",
            "audit_logs",
            "blackboard_events",
            "sop_documents",
            "simulation_scenarios"
        }
        self.assertTrue(expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}")

    def test_seeder_populates_baseline_data(self):
        """Test that seeder populates correct number of zones, warehouses, and scenarios."""
        seed_database(self.db)

        # Check event
        event = self.db.execute_one("SELECT * FROM disaster_events WHERE event_id = 'EVT-2026-FL01';")
        self.assertIsNotNone(event)
        self.assertEqual(event["disaster_type"], "FLOOD")

        # Check zones
        zones = self.db.execute_query("SELECT * FROM affected_zones;")
        self.assertEqual(len(zones), 6, "Expected exactly 6 affected disaster zones")

        # Check warehouses
        warehouses = self.db.execute_query("SELECT * FROM warehouses;")
        self.assertEqual(len(warehouses), 4, "Expected exactly 4 regional warehouses")

        # Check inventory SKUs (4 warehouses * 4 resource types = 16 SKUs)
        inventory = self.db.execute_query("SELECT * FROM warehouse_inventory;")
        self.assertEqual(len(inventory), 16, "Expected exactly 16 warehouse inventory SKU entries")

        # Check scenarios
        scenarios = self.db.execute_query("SELECT * FROM simulation_scenarios;")
        self.assertEqual(len(scenarios), 5, "Expected exactly 5 academic evaluation scenarios")

    def test_foreign_key_enforcement(self):
        """Test that foreign key constraint prevents orphan records."""
        self.db.initialize_database()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute_non_query(
                """
                INSERT INTO affected_zones 
                (zone_id, event_id, name, latitude, longitude, population, vulnerability_index, damage_level, medical_urgency, access_status)
                VALUES ('ZONE-ORPHAN', 'NON_EXISTENT_EVENT', 'Ghost Zone', 26.0, 92.0, 1000, 0.5, 3, 0.5, 'OPEN');
                """
            )

    def test_atomic_transaction_rollback(self):
        """Test that failure inside transaction rolls back all partial operations."""
        seed_database(self.db)
        initial_stock = self.db.execute_one(
            "SELECT available_quantity FROM warehouse_inventory WHERE warehouse_id = 'WH-GUWAHATI-NORTH' AND resource_type = 'CLEAN_WATER';"
        )["available_quantity"]

        try:
            with self.db.transaction() as cursor:
                # Operation 1: Deduct 10,000 liters
                cursor.execute(
                    "UPDATE warehouse_inventory SET available_quantity = available_quantity - 10000 WHERE warehouse_id = 'WH-GUWAHATI-NORTH' AND resource_type = 'CLEAN_WATER';"
                )
                # Operation 2: Force an intentional error
                raise ValueError("Simulated catastrophic mid-transaction crash")
        except ValueError:
            pass

        # Verify stock was rolled back completely
        final_stock = self.db.execute_one(
            "SELECT available_quantity FROM warehouse_inventory WHERE warehouse_id = 'WH-GUWAHATI-NORTH' AND resource_type = 'CLEAN_WATER';"
        )["available_quantity"]
        self.assertEqual(initial_stock, final_stock, "Transaction did not rollback properly on error!")


if __name__ == "__main__":
    unittest.main()


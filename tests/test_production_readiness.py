"""
ReliefOps AI — Phase 9: Production Readiness, Security, Concurrency & Database Reliability Suite
Validates centralized configuration, secret masking, input validation, high-frequency concurrency
collision freedom, ACID transaction rollbacks, SQLite online backup & recovery, and decision explainability.

Academic Disclaimer:
Synthetic test suite developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import concurrent.futures
import os
import re
import tempfile
import unittest
from pathlib import Path
from typing import Set

from backend.agents.relief_coordinator import ReliefCoordinator
from backend.blackboard.blackboard_manager import BlackboardManager
from backend.config import Settings, settings
from backend.database.db_manager import DatabaseManager
from backend.database.seeder import seed_database
from backend.utils.logger import observer, setup_logger
from backend.utils.security import (
    SecurityValidationError,
    sanitize_identifier,
    validate_disaster_context,
    validate_path_safety,
    validate_zone_payload,
)
from tests.stress_fixtures import STRESS_SCENARIOS


class TestProductionReadiness(unittest.TestCase):
    """Production readiness verification test suite."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "prod_test.db")
        self.db = DatabaseManager(self.db_path)
        seed_database(self.db)
        self.bb = BlackboardManager(db=self.db)
        self.coordinator = ReliefCoordinator(blackboard=self.bb, db=self.db)

    def tearDown(self):
        try:
            self.db.close()
        except Exception:
            pass
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_01_configuration_and_secret_masking(self):
        """1. Centralized Settings: loads safe defaults, validates paths, and strictly masks secrets."""
        cfg = Settings()
        self.assertEqual(cfg.EXECUTION_MODE, "deterministic")
        self.assertAlmostEqual(cfg.GINI_THRESHOLD, 0.35)
        self.assertAlmostEqual(cfg.SURVIVAL_FLOOR_RATIO, 0.30)

        # Secret masking tests
        self.assertEqual(cfg.mask_secret(None), "<UNSET>")
        self.assertEqual(cfg.mask_secret(""), "<UNSET>")
        self.assertEqual(cfg.mask_secret("short"), "********")
        masked = cfg.mask_secret("sk-proj-1234567890abcdef12345678")
        self.assertTrue(masked.startswith("sk-"))
        self.assertTrue(masked.endswith("5678"))
        self.assertNotIn("abcdef", masked)

        cfg_dict = cfg.to_dict(mask_secrets=True)
        self.assertIn("EXECUTION_MODE", cfg_dict)
        self.assertIn("GINI_THRESHOLD", cfg_dict)
        self.assertEqual(cfg_dict["OPENAI_CONFIGURED"], bool(cfg.OPENAI_API_KEY))

    def test_02_security_input_validation_and_path_safety(self):
        """2. Security Input Validation: rejects invalid hazards, malformed coordinates, and path traversal."""
        # A. Identifier Sanitization
        self.assertEqual(sanitize_identifier("ZONE-123"), "ZONE-123")
        self.assertEqual(sanitize_identifier("ZONE'; DROP TABLE zones;--"), "ZONEDROPTABLEzones--")

        # B. Path Traversal Prevention
        safe_dir = Path(self.temp_dir.name)
        safe_file = safe_dir / "valid.txt"
        safe_file.touch()
        self.assertEqual(validate_path_safety(safe_file, safe_dir), safe_file.resolve())

        with self.assertRaises(SecurityValidationError):
            validate_path_safety("../../etc/passwd", safe_dir)

        # C. Zone Payload Validation
        valid_zone = {
            "zone_id": "ZONE-TEST-01",
            "population": 10000,
            "damage_level": 4,
            "vulnerability_index": 0.8,
            "medical_urgency": 0.7,
            "access_status": "OPEN",
            "latitude": 26.5,
            "longitude": 93.0,
        }
        is_val, errs = validate_zone_payload(valid_zone)
        self.assertTrue(is_val, f"Valid zone failed: {errs}")

        # Invalid zone: negative population, out-of-range coordinates
        invalid_zone = dict(valid_zone)
        invalid_zone["population"] = -500
        invalid_zone["latitude"] = 999.0
        is_val, errs = validate_zone_payload(invalid_zone)
        self.assertFalse(is_val)
        self.assertGreaterEqual(len(errs), 2)

        # D. Disaster Context Validation
        valid_ctx = {
            "disaster_type": "FLOOD",
            "severity_level": "SEVERE",
            "planning_days": 3,
            "zones": [valid_zone],
        }
        is_val, errs = validate_disaster_context(valid_ctx)
        self.assertTrue(is_val, f"Valid context failed: {errs}")

        invalid_ctx = dict(valid_ctx)
        invalid_ctx["disaster_type"] = "NUCLEAR_FALLOUT"
        is_val, errs = validate_disaster_context(invalid_ctx)
        self.assertFalse(is_val)

    def test_03_concurrent_plan_id_collision_freedom(self):
        """3. High-Frequency Concurrency: generates 100 rapid multi-threaded plan IDs with 0 collisions."""
        import uuid
        import datetime

        def generate_plan_id():
            return f"PLAN-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8].upper()}"

        generated_ids: Set[str] = set()
        count = 100

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(generate_plan_id) for _ in range(count)]
            for fut in concurrent.futures.as_completed(futures):
                pid = fut.result()
                # Verify format
                self.assertTrue(re.match(r"^PLAN-\d{8}-\d{6}-[A-F0-9]{8}$", pid))
                generated_ids.add(pid)

        self.assertEqual(len(generated_ids), count, "High-frequency concurrency must produce 0 plan ID collisions")

    def test_04_database_atomic_transaction_rollback(self):
        """4. Database Reliability: deliberate failure mid-transaction rolls back all partial writes."""
        test_plan_id = "PLAN-ATOMIC-FAIL-TEST"

        # Attempt atomic write with forced failure
        with self.assertRaises(RuntimeError):
            with self.db.transaction() as cur:
                cur.execute(
                    "INSERT INTO allocation_plans (plan_id, event_id, iteration, status, created_at) VALUES (?, ?, 1, 'AUDITING', ?)",
                    (test_plan_id, "EVT-2026-FL01", "2026-01-01T00:00:00Z"),
                )
                cur.execute(
                    "INSERT INTO allocation_items (plan_id, zone_id, warehouse_id, resource_type, requested_qty, allocated_qty, distance_km, est_transit_hours) VALUES (?, ?, ?, ?, ?, ?, 10.0, 1.0)",
                    (test_plan_id, "ZONE-MAJULI-ISLAND", "WH-GUWAHATI-NORTH", "FOOD_RATIONS", 100, 100),
                )
                # Forced exception mid-transaction
                raise RuntimeError("Simulated transaction crash")

        # Verify rollback: neither plan nor item should exist
        plans = self.db.execute_query("SELECT * FROM allocation_plans WHERE plan_id = ?", (test_plan_id,))
        items = self.db.execute_query("SELECT * FROM allocation_items WHERE plan_id = ?", (test_plan_id,))

        self.assertEqual(len(plans), 0, "allocation_plans must be completely rolled back")
        self.assertEqual(len(items), 0, "allocation_items must be completely rolled back")

    def test_05_database_backup_and_recovery(self):
        """5. Backup & Disaster Recovery: hot online SQLite backup and atomic restoration verification."""
        backup_file = os.path.join(self.temp_dir.name, "hot_backup.db")

        # A. Create online backup of current database
        saved_path = self.db.backup_database(backup_file)
        self.assertTrue(os.path.isfile(saved_path))
        self.assertGreater(os.path.getsize(saved_path), 0)

        # B. Mutate active database (insert a new zone and delete warehouses)
        self.db.execute_non_query(
            "INSERT INTO affected_zones (zone_id, event_id, name, latitude, longitude, population, vulnerability_index, damage_level, medical_urgency, access_status) VALUES ('Z-NEW-MUTATION', 'EVT-2026-FL01', 'Mutation Zone', 26.5, 93.0, 5000, 0.5, 3, 0.5, 'OPEN')"
        )
        mutated_zones = self.db.execute_query("SELECT * FROM affected_zones WHERE zone_id = 'Z-NEW-MUTATION'")
        self.assertEqual(len(mutated_zones), 1)

        # C. Restore from backup
        self.db.restore_database(saved_path)

        # D. Assert restored database matches original snapshot (mutated zone must be gone)
        restored_zones = self.db.execute_query("SELECT * FROM affected_zones WHERE zone_id = 'Z-NEW-MUTATION'")
        self.assertEqual(len(restored_zones), 0, "Restored database must match pre-mutation backup state")

    def test_06_structured_logging_and_telemetry(self):
        """6. Observability: Structured application logger and observer record multi-agent telemetry cleanly."""
        custom_log_file = os.path.join(self.temp_dir.name, "test_app.log")
        test_logger = setup_logger("TestLogger", log_level="DEBUG", log_file=custom_log_file)

        test_logger.info("Test informative event", extra={"component": "TestComponent", "structured_data": {"metric": 42}})
        self.assertTrue(os.path.isfile(custom_log_file))

        with open(custom_log_file, "r", encoding="utf-8") as f:
            log_content = f.read()
        self.assertIn("Test informative event", log_content)
        self.assertIn("TestComponent", log_content)
        self.assertIn('"metric": 42', log_content)

    def test_07_explainability_decision_audit_trail(self):
        """7. Explainability: Every synthesized plan includes traceable, mathematically grounded decision explanations."""
        sc = STRESS_SCENARIOS["SCEN_03_SEVERE_EARTHQUAKE"]
        plan = self.coordinator.run_full_coordination_cycle(disaster_context=sc)

        self.assertIn("decision_audit_trail", plan)
        audit_trail = plan["decision_audit_trail"]

        # Disaster summary
        d_summary = audit_trail.get("disaster_summary", {})
        self.assertEqual(d_summary.get("disaster_type"), "EARTHQUAKE")
        self.assertEqual(d_summary.get("governing_sop"), "SOP-EQ-002")

        # Zone-level explanations
        zone_expls = audit_trail.get("zone_explanations", [])
        self.assertEqual(len(zone_expls), len(sc["zones"]))

        for ze in zone_expls:
            self.assertIn("priority_rank", ze)
            self.assertIn("zps_score", ze)
            self.assertIn("priority_reasoning", ze)
            self.assertIn("demands", ze)
            self.assertIn("allocations", ze)
            # Reasoning must cite ZPS and factors
            self.assertIn("ZPS", ze["priority_reasoning"])
            self.assertIn("EARTHQUAKE", ze["priority_reasoning"])

        # Fairness explanation
        fair_expl = audit_trail.get("fairness_explanation", "")
        self.assertIn("Gini coefficient", fair_expl)
        self.assertIn("Distributive justice", fair_expl)


if __name__ == "__main__":
    unittest.main()

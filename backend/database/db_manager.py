"""
ReliefOps AI — Database Manager
Thread-safe, WAL-enabled SQLite persistence manager with atomic transaction support.
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple


class DatabaseManager:
    """Manages SQLite database connections, schema migrations, and atomic operations."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self, db_path: Optional[str] = None):
        """Initializes the database manager with standard SQLite settings."""
        if db_path is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            db_path = os.getenv("DATABASE_PATH", os.path.join(base_dir, "data", "reliefops.db"))

        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._local = threading.local()

    def get_connection(self) -> sqlite3.Connection:
        """Retrieves or creates a thread-local SQLite connection with WAL mode enabled."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0,
                isolation_level=None  # Enable autocommit mode by default; explicit transactions when needed
            )
            conn.row_factory = sqlite3.Row
            # Enable WAL mode and foreign key constraints
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            self._local.conn = conn
        return self._local.conn

    def initialize_database(self, schema_file: Optional[str] = None) -> None:
        """Executes the DDL schema script to initialize all required tables and indexes."""
        if schema_file is None:
            schema_file = os.path.join(os.path.dirname(__file__), "schema.sql")

        with open(schema_file, "r", encoding="utf-8") as f:
            ddl_script = f.read()

        conn = self.get_connection()
        with self._lock:
            conn.executescript(ddl_script)

    def execute_query(self, query: str, params: Tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
        """Executes a read query and returns rows as dictionaries."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def execute_one(self, query: str, params: Tuple[Any, ...] = ()) -> Optional[Dict[str, Any]]:
        """Executes a read query and returns the first row as a dictionary or None."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def execute_non_query(self, query: str, params: Tuple[Any, ...] = ()) -> int:
        """Executes an INSERT/UPDATE/DELETE query and returns the rowcount or lastrowid."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.lastrowid if cursor.lastrowid else cursor.rowcount

    def execute_batch(self, query: str, params_list: List[Tuple[Any, ...]]) -> int:
        """Executes an executemany operation."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.executemany(query, params_list)
        return cursor.rowcount

    @contextmanager
    def transaction(self):
        """Context manager providing an atomic ACID transaction block with automatic rollback."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE TRANSACTION;")
        try:
            yield cursor
            cursor.execute("COMMIT;")
        except Exception:
            cursor.execute("ROLLBACK;")
            raise

    def close(self) -> None:
        """Closes the current thread's connection."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None


# Module-level singleton instance for convenient access
default_db_manager = DatabaseManager()


import sqlite3
import tempfile
import unittest
from pathlib import Path

from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.db.schema import initialize_schema


class DatabaseSchemaTests(unittest.TestCase):
    def test_initialize_schema_creates_expected_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"

            with connect_sqlite(db_path) as connection:
                initialize_schema(connection)
                table_names = self._fetch_table_names(connection)

            self.assertIn("scan_runs", table_names)
            self.assertIn("scanned_files", table_names)
            self.assertIn("scanned_metadata", table_names)
            self.assertIn("plan_runs", table_names)
            self.assertIn("plan_items", table_names)
            self.assertIn("execution_runs", table_names)
            self.assertIn("operation_logs", table_names)
            self.assertIn("rollback_runs", table_names)
            self.assertIn("rollback_logs", table_names)
            self.assertIn("verify_runs", table_names)
            self.assertIn("verify_logs", table_names)

    def test_initialize_schema_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"

            with connect_sqlite(db_path) as connection:
                initialize_schema(connection)
                initialize_schema(connection)
                table_names = self._fetch_table_names(connection)

            self.assertEqual(
                {
                    "execution_runs",
                    "operation_logs",
                    "plan_items",
                    "plan_runs",
                    "rollback_logs",
                    "rollback_runs",
                    "scan_runs",
                    "scanned_files",
                    "scanned_metadata",
                    "verify_logs",
                    "verify_runs",
                },
                table_names,
            )

    @staticmethod
    def _fetch_table_names(connection: sqlite3.Connection) -> set[str]:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()
        return {row[0] for row in rows}


if __name__ == "__main__":
    unittest.main()

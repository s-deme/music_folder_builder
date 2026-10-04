import sqlite3
import tempfile
import unittest
from pathlib import Path

from music_folder_builder.infrastructure.db.connection import connect_sqlite


class ConnectionTests(unittest.TestCase):
    def test_commit_rollback_and_close(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.db"
            with connect_sqlite(path) as connection:
                connection.execute("CREATE TABLE items (value INTEGER)")
                connection.execute("INSERT INTO items VALUES (1)")
                self.assertEqual(1, connection.execute("PRAGMA foreign_keys").fetchone()[0])
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")
            with self.assertRaisesRegex(RuntimeError, "rollback"):
                with connect_sqlite(path) as failed_connection:
                    failed_connection.execute("INSERT INTO items VALUES (2)")
                    raise RuntimeError("rollback")
            with self.assertRaises(sqlite3.ProgrammingError):
                failed_connection.execute("SELECT 1")
            with connect_sqlite(path) as connection:
                self.assertEqual([1], [row[0] for row in connection.execute("SELECT value FROM items")])
            path.unlink()

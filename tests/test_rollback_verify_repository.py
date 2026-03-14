import tempfile
import unittest
from pathlib import Path

from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.db.rollback_verify_repository import RollbackVerifyRepository
from music_folder_builder.infrastructure.db.schema import initialize_schema


class RollbackVerifyRepositoryTests(unittest.TestCase):
    def test_fetch_rollback_verify_items_returns_successful_rollback_mutations_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"

            with connect_sqlite(db_path) as connection:
                initialize_schema(connection)
                rollback_run_id = self._seed_rollback_graph(connection)
                repository = RollbackVerifyRepository(connection)

                items = repository.fetch_rollback_verify_items(rollback_run_id=rollback_run_id)

            self.assertEqual(["rb-1", "rb-3"], [item.rollback_log_id for item in items])
            self.assertEqual([1, 3], [item.sequence_no for item in items])
            self.assertEqual(
                [
                    "source_present_target_absent",
                    "source_present_target_absent",
                ],
                [item.expected_state for item in items],
            )

    def test_fetch_rollback_verify_items_excludes_skip_and_failed_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"

            with connect_sqlite(db_path) as connection:
                initialize_schema(connection)
                rollback_run_id = self._seed_rollback_graph(connection)
                repository = RollbackVerifyRepository(connection)

                items = repository.fetch_rollback_verify_items(rollback_run_id=rollback_run_id)

            self.assertEqual(2, len(items))
            self.assertTrue(all(item.target_deleted for item in items))

    @staticmethod
    def _seed_rollback_graph(connection) -> str:
        connection.execute(
            """
            INSERT INTO scan_runs (id, source_root, started_at, finished_at, status, file_count, warning_count)
            VALUES ('scan-1', '/source', '2026-03-14T00:00:00+00:00', '2026-03-14T00:00:01+00:00', 'completed', 3, 0)
            """
        )
        for index in range(1, 4):
            connection.execute(
                """
                INSERT INTO scanned_files (
                    id, scan_run_id, source_path, source_root, extension, size_bytes, mtime_utc,
                    file_type, exclusion_reason, link_state
                ) VALUES (?, 'scan-1', ?, '/source', '.flac', 10, '2026-03-14T00:00:00+00:00', 'music', NULL, 'none')
                """,
                (f"file-{index}", f"/source/track{index}.flac"),
            )
        connection.execute(
            """
            INSERT INTO plan_runs (id, scan_run_id, started_at, finished_at, status, rule_profile, conflict_count, risk_count)
            VALUES ('plan-1', 'scan-1', '2026-03-14T00:00:02+00:00', '2026-03-14T00:00:03+00:00', 'completed', 'default', 0, 0)
            """
        )
        for index in range(1, 4):
            connection.execute(
                """
                INSERT INTO plan_items (
                    id, plan_run_id, file_id, action, target_path, target_path_sanitized, conflict_status, risk_status, reason
                ) VALUES (?, 'plan-1', ?, 'move', ?, ?, 'none', 'none', NULL)
                """,
                (
                    f"plan-item-{index}",
                    f"file-{index}",
                    f"D:/Music/Artist/Album/{index:02d}_track{index}.flac",
                    f"D:/Music/Artist/Album/{index:02d}_track{index}.flac",
                ),
            )
        connection.execute(
            """
            INSERT INTO execution_runs (
                id, plan_run_id, mode, started_at, finished_at, status,
                success_count, skipped_count, failed_count, risky_count
            ) VALUES (
                'execution-1', 'plan-1', 'apply', '2026-03-14T00:00:04+00:00', '2026-03-14T00:00:05+00:00',
                'completed', 3, 0, 0, 0
            )
            """
        )
        for index in range(1, 4):
            connection.execute(
                """
                INSERT INTO operation_logs (
                    id, execution_run_id, plan_item_id, sequence_no, source_path, target_path,
                    performed_action, result, error_message, source_deleted, created_at
                ) VALUES (?, 'execution-1', ?, ?, ?, ?, 'move', 'success', NULL, 1, '2026-03-14T00:00:05+00:00')
                """,
                (
                    f"op-{index}",
                    f"plan-item-{index}",
                    index,
                    f"/source/track{index}.flac",
                    f"D:/Music/Artist/Album/{index:02d}_track{index}.flac",
                ),
            )
        connection.execute(
            """
            INSERT INTO rollback_runs (
                id, execution_run_id, mode, started_at, finished_at, status,
                success_count, skipped_count, failed_count, risky_count
            ) VALUES (
                'rollback-1', 'execution-1', 'rollback', '2026-03-14T00:00:06+00:00', '2026-03-14T00:00:07+00:00',
                'partial', 2, 1, 0, 1
            )
            """
        )
        rows = [
            ("rb-1", "op-1", 1, "/source/track1.flac", "D:/Music/Artist/Album/01_track1.flac", "reverse_move", "success", None, 1),
            ("rb-2", "op-2", 2, "/source/track2.flac", "D:/Music/Artist/Album/02_track2.flac", "skip", "skipped", "source_already_exists", 0),
            ("rb-3", "op-3", 3, "/source/track3.flac", "D:/Music/Artist/Album/03_track3.flac", "reverse_copy", "success", None, 1),
        ]
        for row in rows:
            connection.execute(
                """
                INSERT INTO rollback_logs (
                    id, rollback_run_id, operation_log_id, sequence_no, source_path, target_path,
                    performed_action, result, error_message, target_deleted, created_at
                ) VALUES (?, 'rollback-1', ?, ?, ?, ?, ?, ?, ?, ?, '2026-03-14T00:00:07+00:00')
                """,
                row,
            )
        connection.commit()
        return "rollback-1"


if __name__ == "__main__":
    unittest.main()

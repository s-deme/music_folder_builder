import tempfile
import unittest
from pathlib import Path

from music_folder_builder.infrastructure.db.apply_verify_repository import ApplyVerifyRepository
from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.db.schema import initialize_schema


class ApplyVerifyRepositoryTests(unittest.TestCase):
    def test_fetch_apply_verify_items_returns_successful_apply_mutations_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"

            with connect_sqlite(db_path) as connection:
                initialize_schema(connection)
                execution_run_id = self._seed_execution_graph(connection)
                repository = ApplyVerifyRepository(connection)

                items = repository.fetch_apply_verify_items(execution_run_id=execution_run_id)

            self.assertEqual(["op-1", "op-3"], [item.operation_log_id for item in items])
            self.assertEqual([1, 3], [item.sequence_no for item in items])
            self.assertEqual(
                [
                    "target_present_source_absent",
                    "target_present_source_absent",
                ],
                [item.expected_state for item in items],
            )

    def test_fetch_apply_verify_items_excludes_skip_dry_run_and_failed_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"

            with connect_sqlite(db_path) as connection:
                initialize_schema(connection)
                execution_run_id = self._seed_execution_graph(connection)
                repository = ApplyVerifyRepository(connection)

                items = repository.fetch_apply_verify_items(execution_run_id=execution_run_id)

            self.assertEqual(2, len(items))
            self.assertTrue(all(item.source_deleted for item in items))

    @staticmethod
    def _seed_execution_graph(connection) -> str:
        connection.execute(
            """
            INSERT INTO scan_runs (id, source_root, started_at, finished_at, status, file_count, warning_count)
            VALUES ('scan-1', '/source', '2026-03-14T00:00:00+00:00', '2026-03-14T00:00:01+00:00', 'completed', 4, 0)
            """
        )
        for index in range(1, 5):
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
        for index in range(1, 5):
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
                'completed', 2, 1, 1, 0
            )
            """
        )
        rows = [
            ("op-1", "plan-item-1", 1, "/source/track1.flac", "D:/Music/Artist/Album/01_track1.flac", "move", "success", None, 1),
            ("op-2", "plan-item-2", 2, "/source/track2.flac", "D:/Music/Artist/Album/02_track2.flac", "skip", "skipped", "target_already_exists", 0),
            ("op-3", "plan-item-3", 3, "/source/track3.flac", "D:/Music/Artist/Album/03_track3.flac", "copy_delete", "success", None, 1),
            ("op-4", "plan-item-4", 4, "/source/track4.flac", "D:/Music/Artist/Album/04_track4.flac", "move", "failed", "source_missing", 0),
        ]
        for row in rows:
            connection.execute(
                """
                INSERT INTO operation_logs (
                    id, execution_run_id, plan_item_id, sequence_no, source_path, target_path,
                    performed_action, result, error_message, source_deleted, created_at
                ) VALUES (?, 'execution-1', ?, ?, ?, ?, ?, ?, ?, ?, '2026-03-14T00:00:05+00:00')
                """,
                row,
            )
        connection.execute(
            """
            INSERT INTO execution_runs (
                id, plan_run_id, mode, started_at, finished_at, status,
                success_count, skipped_count, failed_count, risky_count
            ) VALUES (
                'execution-2', 'plan-1', 'dry_run', '2026-03-14T00:00:06+00:00', '2026-03-14T00:00:07+00:00',
                'completed', 1, 0, 0, 0
            )
            """
        )
        connection.execute(
            """
            INSERT INTO operation_logs (
                id, execution_run_id, plan_item_id, sequence_no, source_path, target_path,
                performed_action, result, error_message, source_deleted, created_at
            ) VALUES (
                'op-5', 'execution-2', 'plan-item-1', 1, '/source/track1.flac', 'D:/Music/Artist/Album/01_track1.flac',
                'dry_run', 'success', NULL, 0, '2026-03-14T00:00:07+00:00'
            )
            """
        )
        connection.commit()
        return "execution-1"


if __name__ == "__main__":
    unittest.main()

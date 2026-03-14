import tempfile
import unittest
from pathlib import Path

from music_folder_builder.application.dto.rollback_request import RollbackRequest
from music_folder_builder.application.services.rollback_service import RollbackService
from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.db.schema import initialize_schema
from music_folder_builder.infrastructure.fs.mutation_gateway import FileMutationGateway


class RollbackServiceTests(unittest.TestCase):
    def test_dry_run_persists_rollback_run_and_logs_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            source_file = Path(tmp_dir) / "source.flac"
            target_file = Path(tmp_dir) / "target.flac"
            target_file.write_bytes(b"music")
            self._seed_apply_history(db_path, source_file, target_file)

            service = RollbackService()
            result = service.execute(
                RollbackRequest(
                    db_path=db_path,
                    execution_run_id="execution-1",
                    dry_run=True,
                )
            )

            self.assertEqual(2, result.success_count)
            self.assertTrue(target_file.exists())
            self.assertFalse(source_file.exists())

            with connect_sqlite(db_path) as connection:
                run_row = connection.execute(
                    """
                    SELECT execution_run_id, mode, status, success_count, failed_count
                    FROM rollback_runs
                    WHERE id = ?
                    """,
                    (result.rollback_run_id,),
                ).fetchone()
                self.assertEqual("execution-1", run_row["execution_run_id"])
                self.assertEqual("dry_run", run_row["mode"])
                self.assertEqual("completed", run_row["status"])
                self.assertEqual(2, run_row["success_count"])

                log_rows = connection.execute(
                    """
                    SELECT sequence_no, performed_action, result, target_deleted
                    FROM rollback_logs
                    WHERE rollback_run_id = ?
                    ORDER BY sequence_no DESC
                    """,
                    (result.rollback_run_id,),
                ).fetchall()
                self.assertEqual([2, 1], [row["sequence_no"] for row in log_rows])
                self.assertTrue(all(row["performed_action"] == "rollback_dry_run" for row in log_rows))
                self.assertTrue(all(row["result"] == "success" for row in log_rows))
                self.assertTrue(all(row["target_deleted"] == 0 for row in log_rows))

    def test_rollback_moves_file_back_on_same_volume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            source_file = Path(tmp_dir) / "source.flac"
            target_file = Path(tmp_dir) / "target.flac"
            target_file.write_bytes(b"music")
            self._seed_same_volume_only_history(db_path, source_file, target_file)

            service = RollbackService(file_mutation_gateway=FileMutationGateway())
            result = service.execute(
                RollbackRequest(
                    db_path=db_path,
                    execution_run_id="execution-1",
                    dry_run=False,
                )
            )

            self.assertEqual(1, result.success_count)
            self.assertTrue(source_file.exists())
            self.assertFalse(target_file.exists())
            self.assertEqual(b"music", source_file.read_bytes())

            with connect_sqlite(db_path) as connection:
                log_row = connection.execute(
                    """
                    SELECT performed_action, result, error_message, target_deleted
                    FROM rollback_logs
                    WHERE rollback_run_id = ?
                    """,
                    (result.rollback_run_id,),
                ).fetchone()
                self.assertEqual("reverse_move", log_row["performed_action"])
                self.assertEqual("success", log_row["result"])
                self.assertIsNone(log_row["error_message"])
                self.assertEqual(1, log_row["target_deleted"])

    def test_rollback_fails_when_target_is_missing_for_same_volume_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            source_file = Path(tmp_dir) / "source.flac"
            target_file = Path(tmp_dir) / "target.flac"
            self._seed_same_volume_only_history(db_path, source_file, target_file)

            service = RollbackService(file_mutation_gateway=FileMutationGateway())
            result = service.execute(
                RollbackRequest(
                    db_path=db_path,
                    execution_run_id="execution-1",
                    dry_run=False,
                )
            )

            self.assertEqual(1, result.failed_count)
            self.assertFalse(source_file.exists())

            with connect_sqlite(db_path) as connection:
                log_row = connection.execute(
                    """
                    SELECT performed_action, result, error_message, target_deleted
                    FROM rollback_logs
                    WHERE rollback_run_id = ?
                    """,
                    (result.rollback_run_id,),
                ).fetchone()
                self.assertEqual("reverse_move", log_row["performed_action"])
                self.assertEqual("failed", log_row["result"])
                self.assertEqual("target_missing", log_row["error_message"])
                self.assertEqual(0, log_row["target_deleted"])

    def test_rollback_skips_when_source_already_exists_for_same_volume_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            source_file = Path(tmp_dir) / "source.flac"
            target_file = Path(tmp_dir) / "target.flac"
            source_file.write_bytes(b"original")
            target_file.write_bytes(b"music")
            self._seed_same_volume_only_history(db_path, source_file, target_file)

            service = RollbackService(file_mutation_gateway=FileMutationGateway())
            result = service.execute(
                RollbackRequest(
                    db_path=db_path,
                    execution_run_id="execution-1",
                    dry_run=False,
                )
            )

            self.assertEqual(1, result.skipped_count)
            self.assertTrue(source_file.exists())
            self.assertTrue(target_file.exists())

            with connect_sqlite(db_path) as connection:
                log_row = connection.execute(
                    """
                    SELECT performed_action, result, error_message, target_deleted
                    FROM rollback_logs
                    WHERE rollback_run_id = ?
                    """,
                    (result.rollback_run_id,),
                ).fetchone()
                self.assertEqual("skip", log_row["performed_action"])
                self.assertEqual("skipped", log_row["result"])
                self.assertEqual("source_already_exists", log_row["error_message"])
                self.assertEqual(0, log_row["target_deleted"])

    def test_rollback_restores_file_for_cross_volume_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            source_file = Path(tmp_dir) / "source2.flac"
            target_file = Path(tmp_dir) / "target2.flac"
            target_file.write_bytes(b"music")
            self._seed_cross_volume_only_history(db_path, source_file, target_file)

            service = RollbackService(file_mutation_gateway=CrossVolumeGateway())
            result = service.execute(
                RollbackRequest(
                    db_path=db_path,
                    execution_run_id="execution-1",
                    dry_run=False,
                )
            )

            self.assertEqual(1, result.success_count)
            self.assertTrue(source_file.exists())
            self.assertFalse(target_file.exists())
            self.assertEqual(b"music", source_file.read_bytes())

            with connect_sqlite(db_path) as connection:
                log_row = connection.execute(
                    """
                    SELECT performed_action, result, error_message, target_deleted
                    FROM rollback_logs
                    WHERE rollback_run_id = ?
                    """,
                    (result.rollback_run_id,),
                ).fetchone()
                self.assertEqual("reverse_copy", log_row["performed_action"])
                self.assertEqual("success", log_row["result"])
                self.assertIsNone(log_row["error_message"])
                self.assertEqual(1, log_row["target_deleted"])

    def test_rollback_keeps_both_copies_when_cross_volume_verify_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            source_file = Path(tmp_dir) / "source2.flac"
            target_file = Path(tmp_dir) / "target2.flac"
            target_file.write_bytes(b"music")
            self._seed_cross_volume_only_history(db_path, source_file, target_file)

            service = RollbackService(file_mutation_gateway=CorruptingRollbackGateway())
            result = service.execute(
                RollbackRequest(
                    db_path=db_path,
                    execution_run_id="execution-1",
                    dry_run=False,
                )
            )

            self.assertEqual(1, result.failed_count)
            self.assertTrue(source_file.exists())
            self.assertTrue(target_file.exists())
            self.assertEqual(b"corrupt", source_file.read_bytes())
            self.assertEqual(b"music", target_file.read_bytes())

            with connect_sqlite(db_path) as connection:
                log_row = connection.execute(
                    """
                    SELECT performed_action, result, error_message, target_deleted
                    FROM rollback_logs
                    WHERE rollback_run_id = ?
                    """,
                    (result.rollback_run_id,),
                ).fetchone()
                self.assertEqual("reverse_copy", log_row["performed_action"])
                self.assertEqual("failed", log_row["result"])
                self.assertEqual("rollback_verify_failed", log_row["error_message"])
                self.assertEqual(0, log_row["target_deleted"])

    def test_rollback_skips_when_operation_was_already_rolled_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            source_file = Path(tmp_dir) / "source.flac"
            target_file = Path(tmp_dir) / "target.flac"
            target_file.write_bytes(b"music")
            self._seed_same_volume_only_history(db_path, source_file, target_file)

            service = RollbackService(file_mutation_gateway=FileMutationGateway())
            first_result = service.execute(
                RollbackRequest(
                    db_path=db_path,
                    execution_run_id="execution-1",
                    dry_run=False,
                )
            )
            self.assertEqual(1, first_result.success_count)

            second_result = service.execute(
                RollbackRequest(
                    db_path=db_path,
                    execution_run_id="execution-1",
                    dry_run=False,
                )
            )

            self.assertEqual(1, second_result.skipped_count)
            self.assertEqual(0, second_result.failed_count)
            self.assertTrue(source_file.exists())
            self.assertFalse(target_file.exists())

            with connect_sqlite(db_path) as connection:
                log_row = connection.execute(
                    """
                    SELECT performed_action, result, error_message
                    FROM rollback_logs
                    WHERE rollback_run_id = ?
                    """,
                    (second_result.rollback_run_id,),
                ).fetchone()
                self.assertEqual("skip", log_row["performed_action"])
                self.assertEqual("skipped", log_row["result"])
                self.assertEqual("already_rolled_back", log_row["error_message"])

    @staticmethod
    def _seed_apply_history(db_path: Path, source_file: Path, target_file: Path) -> None:
        with connect_sqlite(db_path) as connection:
            initialize_schema(connection)
            connection.execute(
                """
                INSERT INTO scan_runs (id, source_root, started_at, finished_at, status, file_count, warning_count)
                VALUES ('scan-1', '/source', '2026-03-14T00:00:00+00:00', '2026-03-14T00:00:01+00:00', 'completed', 2, 0)
                """
            )
            for index in range(1, 3):
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
            for index in range(1, 3):
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
                    'completed', 2, 0, 0, 0
                )
                """
            )
            rows = [
                ("op-1", "plan-item-1", 1, str(source_file), str(target_file), "move", "success", None, 1),
                ("op-2", "plan-item-2", 2, str(source_file.with_name("source2.flac")), str(target_file.with_name("target2.flac")), "copy_delete", "success", None, 1),
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
            connection.commit()

    @staticmethod
    def _seed_same_volume_only_history(db_path: Path, source_file: Path, target_file: Path) -> None:
        with connect_sqlite(db_path) as connection:
            initialize_schema(connection)
            connection.execute(
                """
                INSERT INTO scan_runs (id, source_root, started_at, finished_at, status, file_count, warning_count)
                VALUES ('scan-1', '/source', '2026-03-14T00:00:00+00:00', '2026-03-14T00:00:01+00:00', 'completed', 1, 0)
                """
            )
            connection.execute(
                """
                INSERT INTO scanned_files (
                    id, scan_run_id, source_path, source_root, extension, size_bytes, mtime_utc,
                    file_type, exclusion_reason, link_state
                ) VALUES ('file-1', 'scan-1', ?, '/source', '.flac', 10, '2026-03-14T00:00:00+00:00', 'music', NULL, 'none')
                """,
                (str(source_file),),
            )
            connection.execute(
                """
                INSERT INTO plan_runs (id, scan_run_id, started_at, finished_at, status, rule_profile, conflict_count, risk_count)
                VALUES ('plan-1', 'scan-1', '2026-03-14T00:00:02+00:00', '2026-03-14T00:00:03+00:00', 'completed', 'default', 0, 0)
                """
            )
            connection.execute(
                """
                INSERT INTO plan_items (
                    id, plan_run_id, file_id, action, target_path, target_path_sanitized, conflict_status, risk_status, reason
                ) VALUES ('plan-item-1', 'plan-1', 'file-1', 'move', ?, ?, 'none', 'none', NULL)
                """,
                (str(target_file), str(target_file)),
            )
            connection.execute(
                """
                INSERT INTO execution_runs (
                    id, plan_run_id, mode, started_at, finished_at, status,
                    success_count, skipped_count, failed_count, risky_count
                ) VALUES (
                    'execution-1', 'plan-1', 'apply', '2026-03-14T00:00:04+00:00', '2026-03-14T00:00:05+00:00',
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
                    'op-1', 'execution-1', 'plan-item-1', 1, ?, ?, 'move', 'success', NULL, 1, '2026-03-14T00:00:05+00:00'
                )
                """,
                (str(source_file), str(target_file)),
            )
            connection.commit()

    @staticmethod
    def _seed_cross_volume_only_history(db_path: Path, source_file: Path, target_file: Path) -> None:
        with connect_sqlite(db_path) as connection:
            initialize_schema(connection)
            connection.execute(
                """
                INSERT INTO scan_runs (id, source_root, started_at, finished_at, status, file_count, warning_count)
                VALUES ('scan-1', '/source', '2026-03-14T00:00:00+00:00', '2026-03-14T00:00:01+00:00', 'completed', 1, 0)
                """
            )
            connection.execute(
                """
                INSERT INTO scanned_files (
                    id, scan_run_id, source_path, source_root, extension, size_bytes, mtime_utc,
                    file_type, exclusion_reason, link_state
                ) VALUES ('file-2', 'scan-1', ?, '/source', '.flac', 10, '2026-03-14T00:00:00+00:00', 'music', NULL, 'none')
                """,
                (str(source_file),),
            )
            connection.execute(
                """
                INSERT INTO plan_runs (id, scan_run_id, started_at, finished_at, status, rule_profile, conflict_count, risk_count)
                VALUES ('plan-1', 'scan-1', '2026-03-14T00:00:02+00:00', '2026-03-14T00:00:03+00:00', 'completed', 'default', 0, 0)
                """
            )
            connection.execute(
                """
                INSERT INTO plan_items (
                    id, plan_run_id, file_id, action, target_path, target_path_sanitized, conflict_status, risk_status, reason
                ) VALUES ('plan-item-2', 'plan-1', 'file-2', 'move', ?, ?, 'none', 'none', NULL)
                """,
                (str(target_file), str(target_file)),
            )
            connection.execute(
                """
                INSERT INTO execution_runs (
                    id, plan_run_id, mode, started_at, finished_at, status,
                    success_count, skipped_count, failed_count, risky_count
                ) VALUES (
                    'execution-1', 'plan-1', 'apply', '2026-03-14T00:00:04+00:00', '2026-03-14T00:00:05+00:00',
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
                    'op-2', 'execution-1', 'plan-item-2', 2, ?, ?, 'copy_delete', 'success', NULL, 1, '2026-03-14T00:00:05+00:00'
                )
                """,
                (str(source_file), str(target_file)),
            )
            connection.commit()


if __name__ == "__main__":
    unittest.main()


class CrossVolumeGateway(FileMutationGateway):
    def same_volume(self, source: str | Path, target: str | Path) -> bool:
        return False


class CorruptingRollbackGateway(CrossVolumeGateway):
    def copy(self, source: str | Path, target: str | Path) -> None:
        target_path = Path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"corrupt")

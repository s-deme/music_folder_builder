import tempfile
import unittest
from pathlib import Path

from music_folder_builder.application.dto.verify_request import VerifyRequest
from music_folder_builder.application.services.verify_service import VerifyService
from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.db.schema import initialize_schema


class VerifyServiceTests(unittest.TestCase):
    def test_verify_apply_run_persists_verify_run_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            source_file = Path(tmp_dir) / "source.flac"
            target_file = Path(tmp_dir) / "target.flac"
            target_file.write_bytes(b"music")
            self._seed_apply_verify_graph(db_path, source_file, target_file)

            service = VerifyService()
            result = service.execute(VerifyRequest(db_path=db_path, execution_run_id="execution-1"))

            self.assertEqual(1, result.success_count)
            with connect_sqlite(db_path) as connection:
                run_row = connection.execute(
                    "SELECT execution_run_id, rollback_run_id, status, success_count, failed_count FROM verify_runs WHERE id = ?",
                    (result.verify_run_id,),
                ).fetchone()
                self.assertEqual("execution-1", run_row["execution_run_id"])
                self.assertIsNone(run_row["rollback_run_id"])
                self.assertEqual("completed", run_row["status"])
                self.assertEqual(1, run_row["success_count"])

                log_row = connection.execute(
                    "SELECT expected_state, actual_state, result, error_message FROM verify_logs WHERE verify_run_id = ?",
                    (result.verify_run_id,),
                ).fetchone()
                self.assertEqual("target_present_source_absent", log_row["expected_state"])
                self.assertEqual("source_exists=0;target_exists=1;target_size=5", log_row["actual_state"])
                self.assertEqual("success", log_row["result"])
                self.assertIsNone(log_row["error_message"])

    def test_verify_rollback_run_persists_verify_run_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            source_file = Path(tmp_dir) / "source.flac"
            target_file = Path(tmp_dir) / "target.flac"
            source_file.write_bytes(b"music")
            self._seed_rollback_verify_graph(db_path, source_file, target_file)

            service = VerifyService()
            result = service.execute(VerifyRequest(db_path=db_path, rollback_run_id="rollback-1"))

            self.assertEqual(1, result.success_count)
            with connect_sqlite(db_path) as connection:
                run_row = connection.execute(
                    "SELECT execution_run_id, rollback_run_id, status, success_count, failed_count FROM verify_runs WHERE id = ?",
                    (result.verify_run_id,),
                ).fetchone()
                self.assertIsNone(run_row["execution_run_id"])
                self.assertEqual("rollback-1", run_row["rollback_run_id"])
                self.assertEqual("completed", run_row["status"])

                log_row = connection.execute(
                    "SELECT expected_state, actual_state, result, error_message FROM verify_logs WHERE verify_run_id = ?",
                    (result.verify_run_id,),
                ).fetchone()
                self.assertEqual("source_present_target_absent", log_row["expected_state"])
                self.assertEqual("source_exists=1;target_exists=0;source_size=5", log_row["actual_state"])
                self.assertEqual("success", log_row["result"])
                self.assertIsNone(log_row["error_message"])

    def test_verify_apply_run_fails_when_expected_state_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            source_file = Path(tmp_dir) / "source.flac"
            target_file = Path(tmp_dir) / "target.flac"
            self._seed_apply_verify_graph(db_path, source_file, target_file)

            service = VerifyService()
            result = service.execute(VerifyRequest(db_path=db_path, execution_run_id="execution-1"))

            self.assertEqual(1, result.failed_count)
            with connect_sqlite(db_path) as connection:
                log_row = connection.execute(
                    "SELECT result, error_message FROM verify_logs WHERE verify_run_id = ?",
                    (result.verify_run_id,),
                ).fetchone()
                self.assertEqual("failed", log_row["result"])
                self.assertEqual("apply_expectation_mismatch", log_row["error_message"])

    def test_verify_apply_run_fails_on_size_mismatch_when_both_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            source_file = Path(tmp_dir) / "source.flac"
            target_file = Path(tmp_dir) / "target.flac"
            source_file.write_bytes(b"music")
            target_file.write_bytes(b"music-larger")
            self._seed_apply_verify_graph(
                db_path,
                source_file,
                target_file,
                source_deleted=False,
            )

            service = VerifyService()
            result = service.execute(VerifyRequest(db_path=db_path, execution_run_id="execution-1"))

            self.assertEqual(1, result.failed_count)
            with connect_sqlite(db_path) as connection:
                log_row = connection.execute(
                    "SELECT actual_state, result, error_message FROM verify_logs WHERE verify_run_id = ?",
                    (result.verify_run_id,),
                ).fetchone()
                self.assertEqual(
                    "source_exists=1;target_exists=1;source_size=5;target_size=12",
                    log_row["actual_state"],
                )
                self.assertEqual("failed", log_row["result"])
                self.assertEqual("size_mismatch", log_row["error_message"])

    @staticmethod
    def _seed_apply_verify_graph(
        db_path: Path, source_file: Path, target_file: Path, *, source_deleted: bool = True
    ) -> None:
        with connect_sqlite(db_path) as connection:
            initialize_schema(connection)
            connection.execute(
                "INSERT INTO scan_runs (id, source_root, started_at, finished_at, status, file_count, warning_count) VALUES ('scan-1', '/source', '2026-03-14T00:00:00+00:00', '2026-03-14T00:00:01+00:00', 'completed', 1, 0)"
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
                "INSERT INTO plan_runs (id, scan_run_id, started_at, finished_at, status, rule_profile, conflict_count, risk_count) VALUES ('plan-1', 'scan-1', '2026-03-14T00:00:02+00:00', '2026-03-14T00:00:03+00:00', 'completed', 'default', 0, 0)"
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
                "INSERT INTO execution_runs (id, plan_run_id, mode, started_at, finished_at, status, success_count, skipped_count, failed_count, risky_count) VALUES ('execution-1', 'plan-1', 'apply', '2026-03-14T00:00:04+00:00', '2026-03-14T00:00:05+00:00', 'completed', 1, 0, 0, 0)"
            )
            connection.execute(
                """
                INSERT INTO operation_logs (
                    id, execution_run_id, plan_item_id, sequence_no, source_path, target_path,
                    performed_action, result, error_message, source_deleted, created_at
                ) VALUES ('op-1', 'execution-1', 'plan-item-1', 1, ?, ?, 'move', 'success', NULL, 1, '2026-03-14T00:00:05+00:00')
                """,
                (str(source_file), str(target_file)),
            )
            connection.execute(
                "UPDATE operation_logs SET source_deleted = ? WHERE id = 'op-1'",
                (1 if source_deleted else 0,),
            )
            connection.commit()

    @staticmethod
    def _seed_rollback_verify_graph(db_path: Path, source_file: Path, target_file: Path) -> None:
        with connect_sqlite(db_path) as connection:
            initialize_schema(connection)
            connection.execute(
                "INSERT INTO scan_runs (id, source_root, started_at, finished_at, status, file_count, warning_count) VALUES ('scan-1', '/source', '2026-03-14T00:00:00+00:00', '2026-03-14T00:00:01+00:00', 'completed', 1, 0)"
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
                "INSERT INTO plan_runs (id, scan_run_id, started_at, finished_at, status, rule_profile, conflict_count, risk_count) VALUES ('plan-1', 'scan-1', '2026-03-14T00:00:02+00:00', '2026-03-14T00:00:03+00:00', 'completed', 'default', 0, 0)"
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
                "INSERT INTO execution_runs (id, plan_run_id, mode, started_at, finished_at, status, success_count, skipped_count, failed_count, risky_count) VALUES ('execution-1', 'plan-1', 'apply', '2026-03-14T00:00:04+00:00', '2026-03-14T00:00:05+00:00', 'completed', 1, 0, 0, 0)"
            )
            connection.execute(
                """
                INSERT INTO operation_logs (
                    id, execution_run_id, plan_item_id, sequence_no, source_path, target_path,
                    performed_action, result, error_message, source_deleted, created_at
                ) VALUES ('op-1', 'execution-1', 'plan-item-1', 1, ?, ?, 'move', 'success', NULL, 1, '2026-03-14T00:00:05+00:00')
                """,
                (str(source_file), str(target_file)),
            )
            connection.execute(
                "INSERT INTO rollback_runs (id, execution_run_id, mode, started_at, finished_at, status, success_count, skipped_count, failed_count, risky_count) VALUES ('rollback-1', 'execution-1', 'rollback', '2026-03-14T00:00:06+00:00', '2026-03-14T00:00:07+00:00', 'completed', 1, 0, 0, 0)"
            )
            connection.execute(
                """
                INSERT INTO rollback_logs (
                    id, rollback_run_id, operation_log_id, sequence_no, source_path, target_path,
                    performed_action, result, error_message, target_deleted, created_at
                ) VALUES ('rb-1', 'rollback-1', 'op-1', 1, ?, ?, 'reverse_move', 'success', NULL, 1, '2026-03-14T00:00:07+00:00')
                """,
                (str(source_file), str(target_file)),
            )
            connection.commit()


if __name__ == "__main__":
    unittest.main()

import io
import json
import tempfile
import unittest
from pathlib import Path

from music_folder_builder.cli.main import main
from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.db.schema import initialize_schema


class CliTests(unittest.TestCase):
    def test_returns_argument_error_without_subcommand(self) -> None:
        stdout = io.StringIO()
        exit_code = main([], stdout=stdout)
        self.assertEqual(2, exit_code)

    def test_scan_command_returns_success_and_writes_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            (root / "song.flac").write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"
            stdout = io.StringIO()

            exit_code = main(["scan", "--source", str(root), "--db", str(db_path)], stdout=stdout)

            self.assertEqual(0, exit_code)
            self.assertIn("scan_run_id=", stdout.getvalue())
            with connect_sqlite(db_path) as connection:
                count = connection.execute("SELECT COUNT(*) FROM scan_runs").fetchone()[0]
                self.assertEqual(1, count)

    def test_scan_command_can_emit_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            (root / "song.flac").write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"
            stdout = io.StringIO()

            exit_code = main(["--json", "scan", "--source", str(root), "--db", str(db_path)], stdout=stdout)

            self.assertEqual(0, exit_code)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(1, payload["files"])
            self.assertIsInstance(payload["warnings"], int)
            self.assertIn("scan_run_id", payload)

    def test_scan_command_can_read_source_and_db_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            (root / "song.flac").write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"
            config_path = Path(tmp_dir) / "local.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[scan]",
                        f'source = "{root}"',
                        f'db = "{db_path}"',
                    ]
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()

            exit_code = main(["--config", str(config_path), "scan"], stdout=stdout)

            self.assertEqual(0, exit_code)
            self.assertIn("scan_run_id=", stdout.getvalue())
            with connect_sqlite(db_path) as connection:
                count = connection.execute("SELECT COUNT(*) FROM scan_runs").fetchone()[0]
                self.assertEqual(1, count)

    def test_plan_command_returns_risk_code_when_risk_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            (root / "VeryLongSongTitleForRisk.flac").write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            scan_stdout = io.StringIO()
            scan_exit = main(["scan", "--source", str(root), "--db", str(db_path)], stdout=scan_stdout)
            self.assertEqual(0, scan_exit)

            with connect_sqlite(db_path) as connection:
                scan_run_id = connection.execute(
                    "SELECT id FROM scan_runs ORDER BY started_at DESC LIMIT 1"
                ).fetchone()[0]

            plan_stdout = io.StringIO()
            plan_exit = main(
                [
                    "plan",
                    "--db",
                    str(db_path),
                    "--scan-run-id",
                    scan_run_id,
                    "--library-root",
                    "D:/Music",
                    "--max-path-length",
                    "20",
                ],
                stdout=plan_stdout,
            )

            self.assertEqual(3, plan_exit)
            self.assertIn("risks=1", plan_stdout.getvalue())

    def test_plan_command_can_read_library_root_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            (root / "song.flac").write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"
            config_path = Path(tmp_dir) / "local.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[scan]",
                        f'source = "{root}"',
                        f'db = "{db_path}"',
                        "[plan]",
                        f'db = "{db_path}"',
                        'library_root = "D:/Music"',
                    ]
                ),
                encoding="utf-8",
            )

            scan_stdout = io.StringIO()
            scan_exit = main(["--config", str(config_path), "scan"], stdout=scan_stdout)
            self.assertEqual(0, scan_exit)

            with connect_sqlite(db_path) as connection:
                scan_run_id = connection.execute(
                    "SELECT id FROM scan_runs ORDER BY started_at DESC LIMIT 1"
                ).fetchone()[0]

            plan_stdout = io.StringIO()
            plan_exit = main(
                [
                    "--config",
                    str(config_path),
                    "plan",
                    "--scan-run-id",
                    scan_run_id,
                ],
                stdout=plan_stdout,
            )

            self.assertEqual(0, plan_exit)
            self.assertIn("plan_run_id=", plan_stdout.getvalue())

    def test_apply_command_can_read_db_from_config_and_run_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            (root / "song.flac").write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"
            config_path = Path(tmp_dir) / "local.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[scan]",
                        f'source = "{root}"',
                        f'db = "{db_path}"',
                        "[plan]",
                        f'db = "{db_path}"',
                        'library_root = "D:/Music"',
                        "[apply]",
                        f'db = "{db_path}"',
                        "dry_run = true",
                    ]
                ),
                encoding="utf-8",
            )

            scan_stdout = io.StringIO()
            self.assertEqual(0, main(["--config", str(config_path), "scan"], stdout=scan_stdout))

            with connect_sqlite(db_path) as connection:
                scan_run_id = connection.execute(
                    "SELECT id FROM scan_runs ORDER BY started_at DESC LIMIT 1"
                ).fetchone()[0]

            plan_stdout = io.StringIO()
            self.assertEqual(
                0,
                main(
                    [
                        "--config",
                        str(config_path),
                        "plan",
                        "--scan-run-id",
                        scan_run_id,
                    ],
                    stdout=plan_stdout,
                ),
            )

            with connect_sqlite(db_path) as connection:
                plan_run_id = connection.execute(
                    "SELECT id FROM plan_runs ORDER BY started_at DESC LIMIT 1"
                ).fetchone()[0]

            apply_stdout = io.StringIO()
            apply_exit = main(
                [
                    "--config",
                    str(config_path),
                    "apply",
                    "--plan-run-id",
                    plan_run_id,
                ],
                stdout=apply_stdout,
            )

            self.assertEqual(0, apply_exit)
            self.assertIn("execution_run_id=", apply_stdout.getvalue())
            self.assertIn("mode=dry_run", apply_stdout.getvalue())

    def test_apply_command_returns_risk_code_when_failures_occur(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            source_file = root / "song.flac"
            source_file.write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            scan_stdout = io.StringIO()
            self.assertEqual(0, main(["scan", "--source", str(root), "--db", str(db_path)], stdout=scan_stdout))

            with connect_sqlite(db_path) as connection:
                scan_run_id = connection.execute(
                    "SELECT id FROM scan_runs ORDER BY started_at DESC LIMIT 1"
                ).fetchone()[0]

            plan_stdout = io.StringIO()
            self.assertEqual(
                0,
                main(
                    [
                        "plan",
                        "--db",
                        str(db_path),
                        "--scan-run-id",
                        scan_run_id,
                        "--library-root",
                        "D:/Music",
                    ],
                    stdout=plan_stdout,
                ),
            )

            source_file.unlink()

            with connect_sqlite(db_path) as connection:
                plan_run_id = connection.execute(
                    "SELECT id FROM plan_runs ORDER BY started_at DESC LIMIT 1"
                ).fetchone()[0]

            apply_stdout = io.StringIO()
            apply_exit = main(
                [
                    "apply",
                    "--db",
                    str(db_path),
                    "--plan-run-id",
                    plan_run_id,
                ],
                stdout=apply_stdout,
            )

            self.assertEqual(3, apply_exit)
            self.assertIn("failures=1", apply_stdout.getvalue())

    def test_rollback_command_can_read_db_from_config_and_run_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            config_path = Path(tmp_dir) / "local.toml"
            self._seed_rollback_cli_graph(db_path, source_exists=False, target_exists=True)
            config_path.write_text(
                "\n".join(
                    [
                        "[rollback]",
                        f'db = "{db_path}"',
                        "dry_run = true",
                    ]
                ),
                encoding="utf-8",
            )

            rollback_stdout = io.StringIO()
            rollback_exit = main(
                [
                    "--config",
                    str(config_path),
                    "rollback",
                    "--execution-run-id",
                    "execution-1",
                ],
                stdout=rollback_stdout,
            )

            self.assertEqual(0, rollback_exit)
            self.assertIn("rollback_run_id=", rollback_stdout.getvalue())
            self.assertIn("mode=dry_run", rollback_stdout.getvalue())

    def test_rollback_command_returns_risk_code_when_failures_occur(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            self._seed_rollback_cli_graph(db_path, source_exists=False, target_exists=False)

            rollback_stdout = io.StringIO()
            rollback_exit = main(
                [
                    "rollback",
                    "--db",
                    str(db_path),
                    "--execution-run-id",
                    "execution-1",
                ],
                stdout=rollback_stdout,
            )

            self.assertEqual(3, rollback_exit)
            self.assertIn("failures=1", rollback_stdout.getvalue())

    def test_verify_command_can_read_execution_run_id_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            config_path = Path(tmp_dir) / "local.toml"
            self._seed_verify_execution_graph(db_path, target_exists=True)
            config_path.write_text(
                "\n".join(
                    [
                        "[verify]",
                        f'db = "{db_path}"',
                        'execution_run_id = "execution-1"',
                    ]
                ),
                encoding="utf-8",
            )

            verify_stdout = io.StringIO()
            verify_exit = main(["--config", str(config_path), "verify"], stdout=verify_stdout)

            self.assertEqual(0, verify_exit)
            self.assertIn("verify_run_id=", verify_stdout.getvalue())
            self.assertIn("mode=execution", verify_stdout.getvalue())

    def test_verify_command_can_verify_rollback_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            self._seed_verify_rollback_graph(db_path, source_exists=True)

            verify_stdout = io.StringIO()
            verify_exit = main(
                ["verify", "--db", str(db_path), "--rollback-run-id", "rollback-1"],
                stdout=verify_stdout,
            )

            self.assertEqual(0, verify_exit)
            self.assertIn("mode=rollback", verify_stdout.getvalue())

    def test_verify_command_rejects_both_execution_and_rollback_ids(self) -> None:
        stdout = io.StringIO()
        exit_code = main(
            [
                "verify",
                "--db",
                "/tmp/state.db",
                "--execution-run-id",
                "execution-1",
                "--rollback-run-id",
                "rollback-1",
            ],
            stdout=stdout,
        )
        self.assertEqual(2, exit_code)
        self.assertIn("exactly one", stdout.getvalue())

    def test_verify_command_returns_risk_code_when_mismatch_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            self._seed_verify_execution_graph(db_path, target_exists=False)

            verify_stdout = io.StringIO()
            verify_exit = main(
                ["verify", "--db", str(db_path), "--execution-run-id", "execution-1"],
                stdout=verify_stdout,
            )

            self.assertEqual(3, verify_exit)
            self.assertIn("failures=1", verify_stdout.getvalue())

    def test_verify_command_can_emit_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "state.db"
            self._seed_verify_execution_graph(db_path, target_exists=True)

            verify_stdout = io.StringIO()
            verify_exit = main(
                ["--json", "verify", "--db", str(db_path), "--execution-run-id", "execution-1"],
                stdout=verify_stdout,
            )

            self.assertEqual(0, verify_exit)
            payload = json.loads(verify_stdout.getvalue())
            self.assertEqual("execution", payload["mode"])
            self.assertEqual(1, payload["successes"])
            self.assertEqual(0, payload["failures"])
            self.assertIn("verify_run_id", payload)

    @staticmethod
    def _seed_rollback_cli_graph(db_path: Path, *, source_exists: bool, target_exists: bool) -> None:
        source_file = db_path.parent / "source.flac"
        target_file = db_path.parent / "target.flac"
        if source_exists:
            source_file.write_bytes(b"source")
        if target_exists:
            target_file.write_bytes(b"target")

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
    def _seed_verify_execution_graph(db_path: Path, *, target_exists: bool) -> None:
        source_file = db_path.parent / "verify-source.flac"
        target_file = db_path.parent / "verify-target.flac"
        if target_exists:
            target_file.write_bytes(b"target")

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
            connection.commit()

    @staticmethod
    def _seed_verify_rollback_graph(db_path: Path, *, source_exists: bool) -> None:
        source_file = db_path.parent / "verify-rb-source.flac"
        target_file = db_path.parent / "verify-rb-target.flac"
        if source_exists:
            source_file.write_bytes(b"restored")

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

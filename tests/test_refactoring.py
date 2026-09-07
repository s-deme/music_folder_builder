import sqlite3
import unittest
from itertools import product
from pathlib import Path
from unittest.mock import patch

from music_folder_builder.application.dto.apply_request import ApplyRequest
from music_folder_builder.application.dto.rollback_request import RollbackRequest
from music_folder_builder.application.services.apply_service import ApplyService
from music_folder_builder.application.services.rollback_service import RollbackService
from music_folder_builder.infrastructure.db.schema import initialize_schema
from music_folder_builder.infrastructure.fs.mutation_gateway import FileMutationGateway


class RecordingGateway(FileMutationGateway):
    # Simulates cross-volume and copy-verification failures without touching a library.
    def __init__(self, source_exists, target_exists, same_volume, equal_sizes):
        self.present = {"source": source_exists, "target": target_exists}
        self.same = same_volume
        self.equal = equal_sizes
        self.operations = []

    def exists(self, path):
        return self.present[str(path)]

    def same_volume(self, source, target):
        return self.same

    def size(self, path):
        return 10 if self.equal or str(path) == "source" else 20

    def move(self, source, target):
        self.operations.append(("move", str(source), str(target)))

    def copy(self, source, target):
        self.operations.append(("copy", str(source), str(target)))

    def delete(self, path):
        self.operations.append(("delete", str(path)))


class RefactoringTests(unittest.TestCase):
    def test_verify_expectation_matrix(self):
        from music_folder_builder.application.services.verify_service import _expectation_error

        for primary, counterpart, deleted, source_size, target_size in product(
            (False, True), (False, True), (False, True), (None, 10, 20), (None, 10, 20)
        ):
            expected = None
            if not primary or (deleted and counterpart):
                expected = "expectation_mismatch"
            elif counterpart and source_size is not None and target_size is not None:
                if source_size != target_size:
                    expected = "size_mismatch"
            with self.subTest(state=(primary, counterpart, deleted, source_size, target_size)):
                self.assertEqual(
                    expected,
                    _expectation_error(
                        primary_exists=primary,
                        counterpart_exists=counterpart,
                        counterpart_deleted=deleted,
                        source_size=source_size,
                        target_size=target_size,
                        mismatch_reason="expectation_mismatch",
                    ),
                )

    def test_refresh_after_delete_preserves_order_and_unknown_label(self):
        from music_folder_builder.gui.app import MusicFolderBuilderApp

        app = object.__new__(MusicFolderBuilderApp)
        names = ("scan", "plan", "execution", "rollback", "verify", "log")
        labels = ("読み取り履歴", "整理予定履歴", "整理実行履歴", "元に戻し履歴", "確認履歴")
        calls = []
        for name in names:
            setattr(app, f"_refresh_{name}_views", lambda name=name: calls.append(name))
        for index, label in enumerate(labels):
            calls.clear()
            app._refresh_views_after_delete(label)
            self.assertEqual(list(names[index:]), calls)
        calls.clear()
        app._refresh_views_after_delete("unknown")
        self.assertEqual([], calls)

    def test_active_progress_preserves_priority_and_stops_at_first_match(self):
        from music_folder_builder.gui.query_service import ActiveProgress, GuiQueryService

        service = GuiQueryService("unused")
        names = ("scan", "plan", "execution", "rollback", "verify")
        found = ActiveProgress("scan", "run", 1, None, "")
        for found_index in range(6):
            calls = []
            for index, name in enumerate(names):

                def probe(index=index, name=name):
                    calls.append(name)
                    return found if index == found_index else None

                setattr(service, f"_find_active_{name}_progress", probe)
            self.assertIs(found if found_index < 5 else None, service.find_active_progress())
            self.assertEqual(list(names[: found_index + 1]), calls)

    def test_filename_fallback_and_duplicate_suffix_remain_identical(self):
        from music_folder_builder.domain.policies.organization_rules import OrganizationRules
        from music_folder_builder.infrastructure.db.scan_repository import PlannedScanRecord

        record = PlannedScanRecord(
            "file",
            "source.flac",
            "root",
            "source",
            ".flac",
            None,
            None,
            None,
            None,
            None,
            None,
        )
        for template, filename in (
            ("", "source.flac"),
            ("{missing}", "source.flac"),
            ("{source_stem}{extension}", "source.flac"),
        ):
            rules = OrganizationRules(filename_template=template)
            regular = rules.build_target_path(library_root="D:/Music", record=record)
            self.assertEqual(filename, regular.name)
            for suffix, expected in (("", filename), ("_{source_stem}", "source_source.flac")):
                duplicate = rules.build_duplicate_target_path(
                    library_root="D:/Music",
                    record=record,
                    duplicate_suffix_template=suffix,
                )
                self.assertEqual(regular.parent, duplicate.parent)
                self.assertEqual(expected, duplicate.name)

    def test_apply_and_rollback_preserve_decisions_logs_and_counts(self):
        for rollback, dry_run, already_done, skip, source, target, same, equal in product(
            (False, True), repeat=8
        ):
            case = (rollback, dry_run, already_done, skip, source, target, same, equal)
            with self.subTest(case=case):
                connection = sqlite3.connect(":memory:")
                connection.row_factory = sqlite3.Row
                try:
                    initialize_schema(connection)
                    connection.execute(
                        "INSERT INTO scan_runs VALUES ('scan', '', '', NULL, '', 0, 0)"
                    )
                    connection.execute(
                        "INSERT INTO scanned_files VALUES "
                        "('file', 'scan', 'source', '', '', 10, '', 'music', NULL, '')"
                    )
                    connection.execute(
                        "INSERT INTO plan_runs VALUES ('plan', 'scan', '', NULL, '', '', 0, 0)"
                    )
                    connection.execute(
                        "INSERT INTO plan_items VALUES "
                        "('item', 'plan', 'file', ?, 'target', 'target', '', '', 'planned_skip')",
                        ("skip" if skip else "move",),
                    )
                    connection.execute(
                        "INSERT INTO execution_runs VALUES "
                        "('execution', 'plan', 'apply', '', NULL, '', 0, 0, 0, 0)"
                    )
                    if rollback or already_done:
                        connection.execute(
                            "INSERT INTO operation_logs VALUES "
                            "('operation', 'execution', 'item', 1, 'source', 'target', "
                            "?, 'success', NULL, 1, '')",
                            ("move" if same else "copy_delete",),
                        )
                    if rollback and already_done:
                        connection.execute(
                            "INSERT INTO rollback_runs VALUES "
                            "('previous', 'execution', 'rollback', '', NULL, '', 0, 0, 0, 0)"
                        )
                        connection.execute(
                            "INSERT INTO rollback_logs VALUES "
                            "('previous_log', 'previous', 'operation', 1, 'source', 'target', "
                            "'reverse_move', 'success', NULL, 1, '')"
                        )
                    connection.commit()
                    gateway = RecordingGateway(source, target, same, equal)
                    stage = "rollback" if rollback else "apply"
                    service = RollbackService if rollback else ApplyService
                    request = (
                        RollbackRequest(Path("unused"), "execution", dry_run)
                        if rollback
                        else ApplyRequest(Path("unused"), "plan", dry_run)
                    )
                    with patch(
                        f"music_folder_builder.application.services.{stage}_service.connect_sqlite",
                        return_value=connection,
                    ):
                        result = service(file_mutation_gateway=gateway, batch_size=1).execute(
                            request
                        )
                    expected, operations = self.expected(
                        rollback, dry_run, already_done, skip, source, target, same, equal
                    )
                    action, status, error, deleted, risky = expected
                    table = "rollback_logs" if rollback else "operation_logs"
                    run_column = "rollback_run_id" if rollback else "execution_run_id"
                    deleted_column = "target_deleted" if rollback else "source_deleted"
                    run_id = getattr(result, run_column)
                    row = connection.execute(
                        f"SELECT performed_action, result, error_message, {deleted_column} "
                        f"FROM {table} WHERE {run_column} = ?",
                        (run_id,),
                    ).fetchone()
                    self.assertEqual((action, status, error, int(deleted)), tuple(row))
                    self.assertEqual(
                        (status == "success", status == "skipped", status == "failed", risky),
                        (
                            result.success_count,
                            result.skipped_count,
                            result.failed_count,
                            result.risky_count,
                        ),
                    )
                    self.assertEqual(operations, gateway.operations)
                finally:
                    connection.close()

    @staticmethod
    def expected(rollback, dry_run, already_done, skip, source, target, same, equal):
        if not rollback and skip:
            return ("skip", "skipped", "planned_skip", False, True), []
        if dry_run:
            action = "rollback_dry_run" if rollback else "dry_run"
            return (action, "success", None, False, False), []
        if already_done:
            error = "already_rolled_back" if rollback else "already_applied"
            return ("skip", "skipped", error, False, False), []
        origin, destination = ("target", "source") if rollback else ("source", "target")
        action = ("reverse_move" if same else "reverse_copy") if rollback else "move"
        if not (target if rollback else source):
            return (action, "failed", f"{origin}_missing", False, False), []
        if source if rollback else target:
            return ("skip", "skipped", f"{destination}_already_exists", False, True), []
        if same:
            return (action, "success", None, True, False), [("move", origin, destination)]
        operations = [("copy", origin, destination)]
        action = "reverse_copy" if rollback else "copy"
        if not equal:
            error = "rollback_verify_failed" if rollback else "cross_volume_verify_failed"
            return (action, "failed", error, False, False), operations
        operations.append(("delete", origin))
        return (
            "reverse_copy" if rollback else "copy_delete",
            "success",
            None,
            True,
            False,
        ), operations


if __name__ == "__main__":
    unittest.main()

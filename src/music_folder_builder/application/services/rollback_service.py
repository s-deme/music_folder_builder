from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection
from uuid import uuid4

from music_folder_builder.application.dto.mutation_result import MutationResult
from music_folder_builder.application.dto.rollback_request import RollbackRequest
from music_folder_builder.application.dto.rollback_result import RollbackResult
from music_folder_builder.infrastructure.db.apply_history_repository import (
    ApplyHistoryRepository,
    RollbackItemRecord,
)
from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.db.rollback_log_repository import RollbackLogRepository
from music_folder_builder.infrastructure.db.rollback_run_repository import RollbackRunRepository
from music_folder_builder.infrastructure.db.schema import initialize_schema
from music_folder_builder.infrastructure.fs.mutation_gateway import FileMutationGateway
from music_folder_builder.infrastructure.fs.path_safety import validate_path


class RollbackService:
    _DEFAULT_BATCH_SIZE = 250

    def __init__(
        self,
        *,
        file_mutation_gateway: FileMutationGateway | None = None,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> None:
        self._file_mutation_gateway = file_mutation_gateway or FileMutationGateway()
        self._batch_size = batch_size

    def execute(self, request: RollbackRequest) -> RollbackResult:
        rollback_run_id = str(uuid4())
        success_count = 0
        skipped_count = 0
        failed_count = 0
        risky_count = 0

        with connect_sqlite(request.db_path) as connection:
            initialize_schema(connection)
            history_repository = ApplyHistoryRepository(connection)
            rollback_run_repository = RollbackRunRepository(connection)
            rollback_log_repository = RollbackLogRepository(connection)

            rollback_run_repository.create_rollback_run(
                rollback_run_id=rollback_run_id,
                execution_run_id=request.execution_run_id,
                mode="dry_run" if request.dry_run else "rollback",
                started_at=_utc_now(),
            )

            items = history_repository.fetch_rollback_items(
                execution_run_id=request.execution_run_id
            )
            successful_operation_ids = (
                rollback_log_repository.fetch_successful_rollback_operation_ids(
                    operation_log_ids=[item.operation_log_id for item in items]
                )
            )
            rollback_log_rows: list[tuple[object, ...]] = []

            for item in items:
                outcome = self._process_item(
                    item,
                    dry_run=request.dry_run,
                    already_processed=item.operation_log_id in successful_operation_ids,
                )
                success_count += outcome.result == "success"
                skipped_count += outcome.result == "skipped"
                failed_count += outcome.result == "failed"
                risky_count += outcome.risky
                rollback_log_rows.append(
                    _rollback_log_row(
                        rollback_run_id=rollback_run_id,
                        operation_log_id=item.operation_log_id,
                        sequence_no=item.sequence_no,
                        source_path=item.source_path,
                        target_path=item.target_path,
                        performed_action=outcome.performed_action,
                        result=outcome.result,
                        error_message=outcome.error_message,
                        target_deleted=outcome.deleted,
                    )
                )
                self._flush_rollback_log_batch(
                    connection, rollback_log_repository, rollback_log_rows
                )

            self._flush_rollback_log_batch(
                connection, rollback_log_repository, rollback_log_rows, force=True
            )

            rollback_run_repository.complete_rollback_run(
                rollback_run_id=rollback_run_id,
                finished_at=_utc_now(),
                success_count=success_count,
                skipped_count=skipped_count,
                failed_count=failed_count,
                risky_count=risky_count,
            )

        return RollbackResult(
            rollback_run_id=rollback_run_id,
            success_count=success_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            risky_count=risky_count,
        )

    def _process_item(
        self,
        item: RollbackItemRecord,
        *,
        dry_run: bool,
        already_processed: bool,
    ) -> MutationResult:
        if dry_run:
            return MutationResult("rollback_dry_run", "success")
        if already_processed:
            return MutationResult("skip", "skipped", "already_rolled_back")

        source_path = Path(item.source_path)
        target_path = Path(item.target_path)
        if not item.source_root or not item.target_root:
            return MutationResult("skip", "failed", "plan_root_missing; regenerate the plan", risky=True)
        try:
            validate_path(source_path, Path(item.source_root))
            validate_path(target_path, Path(item.target_root))
        except (OSError, ValueError) as error:
            return MutationResult("skip", "failed", str(error), risky=True)
        if item.performed_action not in ("move", "copy_delete"):
            return MutationResult("skip", "failed", "rollback_not_implemented")
        action = "reverse_move" if item.performed_action == "move" else "reverse_copy"
        if not self._file_mutation_gateway.exists(target_path):
            return MutationResult(action, "failed", "target_missing")
        if self._file_mutation_gateway.exists(source_path):
            return MutationResult("skip", "skipped", "source_already_exists", risky=True)
        try:
            with self._file_mutation_gateway.guarded_paths(
                target_path, source_path, Path(item.target_root), Path(item.source_root)
            ):
                if item.performed_action == "move":
                    self._file_mutation_gateway.move(target_path, source_path)
                    return MutationResult(action, "success", deleted=True)

                self._file_mutation_gateway.copy(target_path, source_path)
                if self._file_mutation_gateway.size(source_path) != self._file_mutation_gateway.size(
                    target_path
                ):
                    return MutationResult(action, "failed", "rollback_verify_failed")
                self._file_mutation_gateway.delete(target_path)
                return MutationResult(action, "success", deleted=True)
        except FileExistsError:
            return MutationResult("skip", "skipped", "destination_already_exists", risky=True)
        except (OSError, ValueError) as error:
            return MutationResult("skip", "failed", str(error), risky=True)

    def _flush_rollback_log_batch(
        self,
        connection: Connection,
        rollback_log_repository: RollbackLogRepository,
        rows: list[tuple[object, ...]],
        *,
        force: bool = False,
    ) -> None:
        if not rows:
            return
        if not force and len(rows) < self._batch_size:
            return
        rollback_log_repository.insert_rollback_logs_batch(rows=rows)
        connection.commit()
        rows.clear()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _rollback_log_row(
    *,
    rollback_run_id: str,
    operation_log_id: str,
    sequence_no: int,
    source_path: str,
    target_path: str,
    performed_action: str,
    result: str,
    error_message: str | None,
    target_deleted: bool,
) -> tuple[object, ...]:
    return (
        str(uuid4()),
        rollback_run_id,
        operation_log_id,
        sequence_no,
        source_path,
        target_path,
        performed_action,
        result,
        error_message,
        1 if target_deleted else 0,
        _utc_now(),
    )

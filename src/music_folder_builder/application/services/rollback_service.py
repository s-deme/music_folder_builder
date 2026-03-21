from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from music_folder_builder.application.dto.rollback_request import RollbackRequest
from music_folder_builder.application.dto.rollback_result import RollbackResult
from music_folder_builder.infrastructure.db.apply_history_repository import ApplyHistoryRepository
from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.db.rollback_log_repository import RollbackLogRepository
from music_folder_builder.infrastructure.db.rollback_run_repository import RollbackRunRepository
from music_folder_builder.infrastructure.db.schema import initialize_schema
from music_folder_builder.infrastructure.fs.mutation_gateway import FileMutationGateway


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

            items = history_repository.fetch_rollback_items(execution_run_id=request.execution_run_id)
            successful_operation_ids = rollback_log_repository.fetch_successful_rollback_operation_ids(
                operation_log_ids=[item.operation_log_id for item in items]
            )
            rollback_log_rows: list[tuple[object, ...]] = []

            for item in items:
                if request.dry_run:
                    success_count += 1
                    rollback_log_rows.append(
                        _rollback_log_row(
                            rollback_run_id=rollback_run_id,
                            operation_log_id=item.operation_log_id,
                            sequence_no=item.sequence_no,
                            source_path=item.source_path,
                            target_path=item.target_path,
                            performed_action="rollback_dry_run",
                            result="success",
                            error_message=None,
                            target_deleted=False,
                        )
                    )
                    self._flush_rollback_log_batch(connection, rollback_log_repository, rollback_log_rows)
                    continue

                if item.operation_log_id in successful_operation_ids:
                    skipped_count += 1
                    rollback_log_rows.append(
                        _rollback_log_row(
                            rollback_run_id=rollback_run_id,
                            operation_log_id=item.operation_log_id,
                            sequence_no=item.sequence_no,
                            source_path=item.source_path,
                            target_path=item.target_path,
                            performed_action="skip",
                            result="skipped",
                            error_message="already_rolled_back",
                            target_deleted=False,
                        )
                    )
                    self._flush_rollback_log_batch(connection, rollback_log_repository, rollback_log_rows)
                    continue

                source_path = Path(item.source_path)
                target_path = Path(item.target_path)

                if item.performed_action == "move":
                    if not self._file_mutation_gateway.exists(target_path):
                        failed_count += 1
                        rollback_log_rows.append(
                            _rollback_log_row(
                                rollback_run_id=rollback_run_id,
                                operation_log_id=item.operation_log_id,
                                sequence_no=item.sequence_no,
                                source_path=item.source_path,
                                target_path=item.target_path,
                                performed_action="reverse_move",
                                result="failed",
                                error_message="target_missing",
                                target_deleted=False,
                            )
                        )
                        self._flush_rollback_log_batch(connection, rollback_log_repository, rollback_log_rows)
                        continue

                    if self._file_mutation_gateway.exists(source_path):
                        skipped_count += 1
                        risky_count += 1
                        rollback_log_rows.append(
                            _rollback_log_row(
                                rollback_run_id=rollback_run_id,
                                operation_log_id=item.operation_log_id,
                                sequence_no=item.sequence_no,
                                source_path=item.source_path,
                                target_path=item.target_path,
                                performed_action="skip",
                                result="skipped",
                                error_message="source_already_exists",
                                target_deleted=False,
                            )
                        )
                        self._flush_rollback_log_batch(connection, rollback_log_repository, rollback_log_rows)
                        continue

                    self._file_mutation_gateway.move(target_path, source_path)
                    success_count += 1
                    rollback_log_rows.append(
                        _rollback_log_row(
                            rollback_run_id=rollback_run_id,
                            operation_log_id=item.operation_log_id,
                            sequence_no=item.sequence_no,
                            source_path=item.source_path,
                            target_path=item.target_path,
                            performed_action="reverse_move",
                            result="success",
                            error_message=None,
                            target_deleted=True,
                        )
                    )
                    self._flush_rollback_log_batch(connection, rollback_log_repository, rollback_log_rows)
                    continue

                if item.performed_action == "copy_delete":
                    if not self._file_mutation_gateway.exists(target_path):
                        failed_count += 1
                        rollback_log_rows.append(
                            _rollback_log_row(
                                rollback_run_id=rollback_run_id,
                                operation_log_id=item.operation_log_id,
                                sequence_no=item.sequence_no,
                                source_path=item.source_path,
                                target_path=item.target_path,
                                performed_action="reverse_copy",
                                result="failed",
                                error_message="target_missing",
                                target_deleted=False,
                            )
                        )
                        self._flush_rollback_log_batch(connection, rollback_log_repository, rollback_log_rows)
                        continue

                    if self._file_mutation_gateway.exists(source_path):
                        skipped_count += 1
                        risky_count += 1
                        rollback_log_rows.append(
                            _rollback_log_row(
                                rollback_run_id=rollback_run_id,
                                operation_log_id=item.operation_log_id,
                                sequence_no=item.sequence_no,
                                source_path=item.source_path,
                                target_path=item.target_path,
                                performed_action="skip",
                                result="skipped",
                                error_message="source_already_exists",
                                target_deleted=False,
                            )
                        )
                        self._flush_rollback_log_batch(connection, rollback_log_repository, rollback_log_rows)
                        continue

                    self._file_mutation_gateway.copy(target_path, source_path)
                    if self._file_mutation_gateway.size(source_path) != self._file_mutation_gateway.size(
                        target_path
                    ):
                        failed_count += 1
                        rollback_log_rows.append(
                            _rollback_log_row(
                                rollback_run_id=rollback_run_id,
                                operation_log_id=item.operation_log_id,
                                sequence_no=item.sequence_no,
                                source_path=item.source_path,
                                target_path=item.target_path,
                                performed_action="reverse_copy",
                                result="failed",
                                error_message="rollback_verify_failed",
                                target_deleted=False,
                            )
                        )
                        self._flush_rollback_log_batch(connection, rollback_log_repository, rollback_log_rows)
                        continue

                    self._file_mutation_gateway.delete(target_path)
                    success_count += 1
                    rollback_log_rows.append(
                        _rollback_log_row(
                            rollback_run_id=rollback_run_id,
                            operation_log_id=item.operation_log_id,
                            sequence_no=item.sequence_no,
                            source_path=item.source_path,
                            target_path=item.target_path,
                            performed_action="reverse_copy",
                            result="success",
                            error_message=None,
                            target_deleted=True,
                        )
                    )
                    self._flush_rollback_log_batch(connection, rollback_log_repository, rollback_log_rows)
                    continue

                failed_count += 1
                rollback_log_rows.append(
                    _rollback_log_row(
                        rollback_run_id=rollback_run_id,
                        operation_log_id=item.operation_log_id,
                        sequence_no=item.sequence_no,
                        source_path=item.source_path,
                        target_path=item.target_path,
                        performed_action="skip",
                        result="failed",
                        error_message="rollback_not_implemented",
                        target_deleted=False,
                    )
                )
                self._flush_rollback_log_batch(connection, rollback_log_repository, rollback_log_rows)

            self._flush_rollback_log_batch(connection, rollback_log_repository, rollback_log_rows, force=True)

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

    def _flush_rollback_log_batch(
        self,
        connection: object,
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

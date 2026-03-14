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
    def __init__(self, *, file_mutation_gateway: FileMutationGateway | None = None) -> None:
        self._file_mutation_gateway = file_mutation_gateway or FileMutationGateway()

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

            for item in history_repository.fetch_rollback_items(execution_run_id=request.execution_run_id):
                if request.dry_run:
                    success_count += 1
                    rollback_log_repository.insert_rollback_log(
                        rollback_log_id=str(uuid4()),
                        rollback_run_id=rollback_run_id,
                        operation_log_id=item.operation_log_id,
                        sequence_no=item.sequence_no,
                        source_path=item.source_path,
                        target_path=item.target_path,
                        performed_action="rollback_dry_run",
                        result="success",
                        error_message=None,
                        target_deleted=False,
                        created_at=_utc_now(),
                    )
                    continue

                if rollback_log_repository.has_successful_rollback(
                    operation_log_id=item.operation_log_id
                ):
                    skipped_count += 1
                    rollback_log_repository.insert_rollback_log(
                        rollback_log_id=str(uuid4()),
                        rollback_run_id=rollback_run_id,
                        operation_log_id=item.operation_log_id,
                        sequence_no=item.sequence_no,
                        source_path=item.source_path,
                        target_path=item.target_path,
                        performed_action="skip",
                        result="skipped",
                        error_message="already_rolled_back",
                        target_deleted=False,
                        created_at=_utc_now(),
                    )
                    continue

                source_path = Path(item.source_path)
                target_path = Path(item.target_path)

                if item.performed_action == "move":
                    if not self._file_mutation_gateway.exists(target_path):
                        failed_count += 1
                        rollback_log_repository.insert_rollback_log(
                            rollback_log_id=str(uuid4()),
                            rollback_run_id=rollback_run_id,
                            operation_log_id=item.operation_log_id,
                            sequence_no=item.sequence_no,
                            source_path=item.source_path,
                            target_path=item.target_path,
                            performed_action="reverse_move",
                            result="failed",
                            error_message="target_missing",
                            target_deleted=False,
                            created_at=_utc_now(),
                        )
                        continue

                    if self._file_mutation_gateway.exists(source_path):
                        skipped_count += 1
                        risky_count += 1
                        rollback_log_repository.insert_rollback_log(
                            rollback_log_id=str(uuid4()),
                            rollback_run_id=rollback_run_id,
                            operation_log_id=item.operation_log_id,
                            sequence_no=item.sequence_no,
                            source_path=item.source_path,
                            target_path=item.target_path,
                            performed_action="skip",
                            result="skipped",
                            error_message="source_already_exists",
                            target_deleted=False,
                            created_at=_utc_now(),
                        )
                        continue

                    self._file_mutation_gateway.move(target_path, source_path)
                    success_count += 1
                    rollback_log_repository.insert_rollback_log(
                        rollback_log_id=str(uuid4()),
                        rollback_run_id=rollback_run_id,
                        operation_log_id=item.operation_log_id,
                        sequence_no=item.sequence_no,
                        source_path=item.source_path,
                        target_path=item.target_path,
                        performed_action="reverse_move",
                        result="success",
                        error_message=None,
                        target_deleted=True,
                        created_at=_utc_now(),
                    )
                    continue

                if item.performed_action == "copy_delete":
                    if not self._file_mutation_gateway.exists(target_path):
                        failed_count += 1
                        rollback_log_repository.insert_rollback_log(
                            rollback_log_id=str(uuid4()),
                            rollback_run_id=rollback_run_id,
                            operation_log_id=item.operation_log_id,
                            sequence_no=item.sequence_no,
                            source_path=item.source_path,
                            target_path=item.target_path,
                            performed_action="reverse_copy",
                            result="failed",
                            error_message="target_missing",
                            target_deleted=False,
                            created_at=_utc_now(),
                        )
                        continue

                    if self._file_mutation_gateway.exists(source_path):
                        skipped_count += 1
                        risky_count += 1
                        rollback_log_repository.insert_rollback_log(
                            rollback_log_id=str(uuid4()),
                            rollback_run_id=rollback_run_id,
                            operation_log_id=item.operation_log_id,
                            sequence_no=item.sequence_no,
                            source_path=item.source_path,
                            target_path=item.target_path,
                            performed_action="skip",
                            result="skipped",
                            error_message="source_already_exists",
                            target_deleted=False,
                            created_at=_utc_now(),
                        )
                        continue

                    self._file_mutation_gateway.copy(target_path, source_path)
                    if self._file_mutation_gateway.size(source_path) != self._file_mutation_gateway.size(
                        target_path
                    ):
                        failed_count += 1
                        rollback_log_repository.insert_rollback_log(
                            rollback_log_id=str(uuid4()),
                            rollback_run_id=rollback_run_id,
                            operation_log_id=item.operation_log_id,
                            sequence_no=item.sequence_no,
                            source_path=item.source_path,
                            target_path=item.target_path,
                            performed_action="reverse_copy",
                            result="failed",
                            error_message="rollback_verify_failed",
                            target_deleted=False,
                            created_at=_utc_now(),
                        )
                        continue

                    self._file_mutation_gateway.delete(target_path)
                    success_count += 1
                    rollback_log_repository.insert_rollback_log(
                        rollback_log_id=str(uuid4()),
                        rollback_run_id=rollback_run_id,
                        operation_log_id=item.operation_log_id,
                        sequence_no=item.sequence_no,
                        source_path=item.source_path,
                        target_path=item.target_path,
                        performed_action="reverse_copy",
                        result="success",
                        error_message=None,
                        target_deleted=True,
                        created_at=_utc_now(),
                    )
                    continue

                failed_count += 1
                rollback_log_repository.insert_rollback_log(
                    rollback_log_id=str(uuid4()),
                    rollback_run_id=rollback_run_id,
                    operation_log_id=item.operation_log_id,
                    sequence_no=item.sequence_no,
                    source_path=item.source_path,
                    target_path=item.target_path,
                    performed_action="skip",
                    result="failed",
                    error_message="rollback_not_implemented",
                    target_deleted=False,
                    created_at=_utc_now(),
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


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()

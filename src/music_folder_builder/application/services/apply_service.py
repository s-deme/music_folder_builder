from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection
from uuid import uuid4

from music_folder_builder.application.dto.apply_request import ApplyRequest
from music_folder_builder.application.dto.apply_result import ApplyResult
from music_folder_builder.application.dto.mutation_result import MutationResult
from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.db.execution_repository import ExecutionRepository
from music_folder_builder.infrastructure.db.operation_log_repository import OperationLogRepository
from music_folder_builder.infrastructure.db.plan_query_repository import (
    ApplyPlanItemRecord,
    PlanQueryRepository,
)
from music_folder_builder.infrastructure.db.schema import initialize_schema
from music_folder_builder.infrastructure.fs.mutation_gateway import FileMutationGateway


class ApplyService:
    _DEFAULT_BATCH_SIZE = 250

    def __init__(
        self,
        *,
        file_mutation_gateway: FileMutationGateway | None = None,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> None:
        self._file_mutation_gateway = file_mutation_gateway or FileMutationGateway()
        self._batch_size = batch_size

    def execute(self, request: ApplyRequest) -> ApplyResult:
        execution_run_id = str(uuid4())
        success_count = 0
        skipped_count = 0
        failed_count = 0
        risky_count = 0

        with connect_sqlite(request.db_path) as connection:
            initialize_schema(connection)
            execution_repository = ExecutionRepository(connection)
            operation_log_repository = OperationLogRepository(connection)
            plan_query_repository = PlanQueryRepository(connection)

            execution_repository.create_execution_run(
                execution_run_id=execution_run_id,
                plan_run_id=request.plan_run_id,
                mode="dry_run" if request.dry_run else "apply",
                started_at=_utc_now(),
            )

            items = plan_query_repository.fetch_apply_items(plan_run_id=request.plan_run_id)
            successful_plan_item_ids = (
                operation_log_repository.fetch_successful_apply_plan_item_ids(
                    plan_item_ids=[item.plan_item_id for item in items]
                )
            )
            operation_log_rows: list[tuple[object, ...]] = []

            for index, item in enumerate(items, start=1):
                outcome = self._process_item(
                    item,
                    dry_run=request.dry_run,
                    already_processed=item.plan_item_id in successful_plan_item_ids,
                )
                success_count += outcome.result == "success"
                skipped_count += outcome.result == "skipped"
                failed_count += outcome.result == "failed"
                risky_count += outcome.risky
                operation_log_rows.append(
                    _operation_log_row(
                        execution_run_id=execution_run_id,
                        plan_item_id=item.plan_item_id,
                        sequence_no=index,
                        source_path=item.source_path,
                        target_path=item.target_path,
                        performed_action=outcome.performed_action,
                        result=outcome.result,
                        error_message=outcome.error_message,
                        source_deleted=outcome.deleted,
                    )
                )
                self._flush_operation_log_batch(
                    connection, operation_log_repository, operation_log_rows
                )

            self._flush_operation_log_batch(
                connection, operation_log_repository, operation_log_rows, force=True
            )

            execution_repository.complete_execution_run(
                execution_run_id=execution_run_id,
                finished_at=_utc_now(),
                success_count=success_count,
                skipped_count=skipped_count,
                failed_count=failed_count,
                risky_count=risky_count,
            )

        return ApplyResult(
            execution_run_id=execution_run_id,
            success_count=success_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            risky_count=risky_count,
        )

    def _process_item(
        self,
        item: ApplyPlanItemRecord,
        *,
        dry_run: bool,
        already_processed: bool,
    ) -> MutationResult:
        if item.action == "skip":
            return MutationResult("skip", "skipped", item.reason, risky=True)
        if dry_run:
            return MutationResult("dry_run", "success")
        if already_processed:
            return MutationResult("skip", "skipped", "already_applied")

        source_path = Path(item.source_path)
        target_path = Path(item.target_path)
        if not self._file_mutation_gateway.exists(source_path):
            return MutationResult("move", "failed", "source_missing")
        if self._file_mutation_gateway.exists(target_path):
            return MutationResult("skip", "skipped", "target_already_exists", risky=True)
        if self._file_mutation_gateway.same_volume(source_path, target_path):
            self._file_mutation_gateway.move(source_path, target_path)
            return MutationResult("move", "success", deleted=True)

        self._file_mutation_gateway.copy(source_path, target_path)
        if self._file_mutation_gateway.size(source_path) != self._file_mutation_gateway.size(
            target_path
        ):
            return MutationResult("copy", "failed", "cross_volume_verify_failed")
        self._file_mutation_gateway.delete(source_path)
        return MutationResult("copy_delete", "success", deleted=True)

    def _flush_operation_log_batch(
        self,
        connection: Connection,
        operation_log_repository: OperationLogRepository,
        rows: list[tuple[object, ...]],
        *,
        force: bool = False,
    ) -> None:
        if not rows:
            return
        if not force and len(rows) < self._batch_size:
            return
        operation_log_repository.insert_operation_logs_batch(rows=rows)
        connection.commit()
        rows.clear()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _operation_log_row(
    *,
    execution_run_id: str,
    plan_item_id: str,
    sequence_no: int,
    source_path: str,
    target_path: str | None,
    performed_action: str,
    result: str,
    error_message: str | None,
    source_deleted: bool,
) -> tuple[object, ...]:
    return (
        str(uuid4()),
        execution_run_id,
        plan_item_id,
        sequence_no,
        source_path,
        target_path or "",
        performed_action,
        result,
        error_message,
        1 if source_deleted else 0,
        _utc_now(),
    )

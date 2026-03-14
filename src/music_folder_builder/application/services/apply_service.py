from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from music_folder_builder.application.dto.apply_request import ApplyRequest
from music_folder_builder.application.dto.apply_result import ApplyResult
from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.db.execution_repository import ExecutionRepository
from music_folder_builder.infrastructure.db.operation_log_repository import OperationLogRepository
from music_folder_builder.infrastructure.db.plan_query_repository import PlanQueryRepository
from music_folder_builder.infrastructure.db.schema import initialize_schema
from music_folder_builder.infrastructure.fs.mutation_gateway import FileMutationGateway


class ApplyService:
    def __init__(self, *, file_mutation_gateway: FileMutationGateway | None = None) -> None:
        self._file_mutation_gateway = file_mutation_gateway or FileMutationGateway()

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

            for index, item in enumerate(
                plan_query_repository.fetch_apply_items(plan_run_id=request.plan_run_id),
                start=1,
            ):
                if item.action == "skip":
                    skipped_count += 1
                    risky_count += 1
                    operation_log_repository.insert_operation_log(
                        operation_log_id=str(uuid4()),
                        execution_run_id=execution_run_id,
                        plan_item_id=item.plan_item_id,
                        sequence_no=index,
                        source_path=item.source_path,
                        target_path=item.target_path,
                        performed_action="skip",
                        result="skipped",
                        error_message=item.reason,
                        source_deleted=False,
                        created_at=_utc_now(),
                    )
                    continue

                if request.dry_run:
                    success_count += 1
                    operation_log_repository.insert_operation_log(
                        operation_log_id=str(uuid4()),
                        execution_run_id=execution_run_id,
                        plan_item_id=item.plan_item_id,
                        sequence_no=index,
                        source_path=item.source_path,
                        target_path=item.target_path,
                        performed_action="dry_run",
                        result="success",
                        error_message=None,
                        source_deleted=False,
                        created_at=_utc_now(),
                    )
                    continue

                if operation_log_repository.has_successful_apply(plan_item_id=item.plan_item_id):
                    skipped_count += 1
                    operation_log_repository.insert_operation_log(
                        operation_log_id=str(uuid4()),
                        execution_run_id=execution_run_id,
                        plan_item_id=item.plan_item_id,
                        sequence_no=index,
                        source_path=item.source_path,
                        target_path=item.target_path,
                        performed_action="skip",
                        result="skipped",
                        error_message="already_applied",
                        source_deleted=False,
                        created_at=_utc_now(),
                    )
                    continue

                source_path = Path(item.source_path)
                target_path = Path(item.target_path)

                if not self._file_mutation_gateway.exists(source_path):
                    failed_count += 1
                    operation_log_repository.insert_operation_log(
                        operation_log_id=str(uuid4()),
                        execution_run_id=execution_run_id,
                        plan_item_id=item.plan_item_id,
                        sequence_no=index,
                        source_path=item.source_path,
                        target_path=item.target_path,
                        performed_action="move",
                        result="failed",
                        error_message="source_missing",
                        source_deleted=False,
                        created_at=_utc_now(),
                    )
                    continue

                if self._file_mutation_gateway.exists(target_path):
                    skipped_count += 1
                    risky_count += 1
                    operation_log_repository.insert_operation_log(
                        operation_log_id=str(uuid4()),
                        execution_run_id=execution_run_id,
                        plan_item_id=item.plan_item_id,
                        sequence_no=index,
                        source_path=item.source_path,
                        target_path=item.target_path,
                        performed_action="skip",
                        result="skipped",
                        error_message="target_already_exists",
                        source_deleted=False,
                        created_at=_utc_now(),
                    )
                    continue

                if self._file_mutation_gateway.same_volume(source_path, target_path):
                    self._file_mutation_gateway.move(source_path, target_path)
                    success_count += 1
                    operation_log_repository.insert_operation_log(
                        operation_log_id=str(uuid4()),
                        execution_run_id=execution_run_id,
                        plan_item_id=item.plan_item_id,
                        sequence_no=index,
                        source_path=item.source_path,
                        target_path=item.target_path,
                        performed_action="move",
                        result="success",
                        error_message=None,
                        source_deleted=True,
                        created_at=_utc_now(),
                    )
                    continue

                self._file_mutation_gateway.copy(source_path, target_path)
                if self._file_mutation_gateway.size(source_path) != self._file_mutation_gateway.size(
                    target_path
                ):
                    failed_count += 1
                    operation_log_repository.insert_operation_log(
                        operation_log_id=str(uuid4()),
                        execution_run_id=execution_run_id,
                        plan_item_id=item.plan_item_id,
                        sequence_no=index,
                        source_path=item.source_path,
                        target_path=item.target_path,
                        performed_action="copy",
                        result="failed",
                        error_message="cross_volume_verify_failed",
                        source_deleted=False,
                        created_at=_utc_now(),
                    )
                    continue

                self._file_mutation_gateway.delete(source_path)
                success_count += 1
                operation_log_repository.insert_operation_log(
                    operation_log_id=str(uuid4()),
                    execution_run_id=execution_run_id,
                    plan_item_id=item.plan_item_id,
                    sequence_no=index,
                    source_path=item.source_path,
                    target_path=item.target_path,
                    performed_action="copy_delete",
                    result="success",
                    error_message=None,
                    source_deleted=True,
                    created_at=_utc_now(),
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


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()

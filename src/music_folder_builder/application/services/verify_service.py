from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from music_folder_builder.application.dto.verify_request import VerifyRequest
from music_folder_builder.application.dto.verify_result import VerifyResult
from music_folder_builder.infrastructure.db.apply_verify_repository import ApplyVerifyRepository
from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.db.rollback_verify_repository import RollbackVerifyRepository
from music_folder_builder.infrastructure.db.schema import initialize_schema
from music_folder_builder.infrastructure.db.verify_log_repository import VerifyLogRepository
from music_folder_builder.infrastructure.db.verify_run_repository import VerifyRunRepository
from music_folder_builder.infrastructure.fs.state_gateway import FileStateGateway


class VerifyService:
    def __init__(self, *, file_state_gateway: FileStateGateway | None = None) -> None:
        self._file_state_gateway = file_state_gateway or FileStateGateway()

    def execute(self, request: VerifyRequest) -> VerifyResult:
        verify_run_id = str(uuid4())
        success_count = 0
        skipped_count = 0
        failed_count = 0
        risky_count = 0

        if bool(request.execution_run_id) == bool(request.rollback_run_id):
            raise ValueError("verify requires exactly one of execution_run_id or rollback_run_id")

        with connect_sqlite(request.db_path) as connection:
            initialize_schema(connection)
            apply_verify_repository = ApplyVerifyRepository(connection)
            rollback_verify_repository = RollbackVerifyRepository(connection)
            verify_run_repository = VerifyRunRepository(connection)
            verify_log_repository = VerifyLogRepository(connection)

            verify_run_repository.create_verify_run(
                verify_run_id=verify_run_id,
                execution_run_id=request.execution_run_id,
                rollback_run_id=request.rollback_run_id,
                started_at=_utc_now(),
            )

            if request.execution_run_id:
                items = apply_verify_repository.fetch_apply_verify_items(
                    execution_run_id=request.execution_run_id
                )
                for item in items:
                    target_exists = self._file_state_gateway.exists(item.target_path)
                    source_exists = self._file_state_gateway.exists(item.source_path)
                    source_size, target_size = _read_sizes(
                        self._file_state_gateway,
                        source_path=item.source_path,
                        target_path=item.target_path,
                        source_exists=source_exists,
                        target_exists=target_exists,
                    )
                    actual_state = _render_actual_state(
                        source_exists=source_exists,
                        target_exists=target_exists,
                        source_size=source_size,
                        target_size=target_size,
                    )
                    if target_exists and (not item.source_deleted or not source_exists):
                        if (
                            source_exists
                            and source_size is not None
                            and target_size is not None
                            and source_size != target_size
                        ):
                            failed_count += 1
                            result = "failed"
                            error_message = "size_mismatch"
                        else:
                            success_count += 1
                            result = "success"
                            error_message = None
                    else:
                        failed_count += 1
                        result = "failed"
                        error_message = "apply_expectation_mismatch"
                    verify_log_repository.insert_verify_log(
                        verify_log_id=str(uuid4()),
                        verify_run_id=verify_run_id,
                        operation_log_id=item.operation_log_id,
                        rollback_log_id=None,
                        sequence_no=item.sequence_no,
                        subject_path=item.target_path,
                        counterpart_path=item.source_path,
                        expected_state=item.expected_state,
                        actual_state=actual_state,
                        result=result,
                        error_message=error_message,
                        created_at=_utc_now(),
                    )
            else:
                items = rollback_verify_repository.fetch_rollback_verify_items(
                    rollback_run_id=request.rollback_run_id or ""
                )
                for item in items:
                    source_exists = self._file_state_gateway.exists(item.source_path)
                    target_exists = self._file_state_gateway.exists(item.target_path)
                    source_size, target_size = _read_sizes(
                        self._file_state_gateway,
                        source_path=item.source_path,
                        target_path=item.target_path,
                        source_exists=source_exists,
                        target_exists=target_exists,
                    )
                    actual_state = _render_actual_state(
                        source_exists=source_exists,
                        target_exists=target_exists,
                        source_size=source_size,
                        target_size=target_size,
                    )
                    if source_exists and (not item.target_deleted or not target_exists):
                        if (
                            target_exists
                            and source_size is not None
                            and target_size is not None
                            and source_size != target_size
                        ):
                            failed_count += 1
                            result = "failed"
                            error_message = "size_mismatch"
                        else:
                            success_count += 1
                            result = "success"
                            error_message = None
                    else:
                        failed_count += 1
                        result = "failed"
                        error_message = "rollback_expectation_mismatch"
                    verify_log_repository.insert_verify_log(
                        verify_log_id=str(uuid4()),
                        verify_run_id=verify_run_id,
                        operation_log_id=None,
                        rollback_log_id=item.rollback_log_id,
                        sequence_no=item.sequence_no,
                        subject_path=item.source_path,
                        counterpart_path=item.target_path,
                        expected_state=item.expected_state,
                        actual_state=actual_state,
                        result=result,
                        error_message=error_message,
                        created_at=_utc_now(),
                    )

            verify_run_repository.complete_verify_run(
                verify_run_id=verify_run_id,
                finished_at=_utc_now(),
                success_count=success_count,
                skipped_count=skipped_count,
                failed_count=failed_count,
                risky_count=risky_count,
            )

        return VerifyResult(
            verify_run_id=verify_run_id,
            success_count=success_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            risky_count=risky_count,
        )


def _read_sizes(
    file_state_gateway: FileStateGateway,
    *,
    source_path: str,
    target_path: str,
    source_exists: bool,
    target_exists: bool,
) -> tuple[int | None, int | None]:
    source_size = file_state_gateway.size(source_path) if source_exists else None
    target_size = file_state_gateway.size(target_path) if target_exists else None
    return source_size, target_size


def _render_actual_state(
    *,
    source_exists: bool,
    target_exists: bool,
    source_size: int | None,
    target_size: int | None,
) -> str:
    parts = [
        f"source_exists={int(source_exists)}",
        f"target_exists={int(target_exists)}",
    ]
    if source_size is not None:
        parts.append(f"source_size={source_size}")
    if target_size is not None:
        parts.append(f"target_size={target_size}")
    return ";".join(parts)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()

from __future__ import annotations

import sqlite3


class VerifyLogRepository:
    _INSERT_VERIFY_LOG_SQL = """
        INSERT INTO verify_logs (
            id, verify_run_id, operation_log_id, rollback_log_id, sequence_no,
            subject_path, counterpart_path, expected_state, actual_state, result,
            error_message, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def insert_verify_log(
        self,
        *,
        verify_log_id: str,
        verify_run_id: str,
        operation_log_id: str | None,
        rollback_log_id: str | None,
        sequence_no: int,
        subject_path: str,
        counterpart_path: str | None,
        expected_state: str,
        actual_state: str,
        result: str,
        error_message: str | None,
        created_at: str,
    ) -> None:
        self._connection.execute(
            self._INSERT_VERIFY_LOG_SQL,
            (
                verify_log_id,
                verify_run_id,
                operation_log_id,
                rollback_log_id,
                sequence_no,
                subject_path,
                counterpart_path,
                expected_state,
                actual_state,
                result,
                error_message,
                created_at,
            ),
        )

    def insert_verify_logs_batch(self, *, rows: list[tuple[object, ...]]) -> None:
        self._connection.executemany(self._INSERT_VERIFY_LOG_SQL, rows)

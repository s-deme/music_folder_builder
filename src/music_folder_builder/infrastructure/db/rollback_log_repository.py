from __future__ import annotations

import sqlite3


class RollbackLogRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def insert_rollback_log(
        self,
        *,
        rollback_log_id: str,
        rollback_run_id: str,
        operation_log_id: str,
        sequence_no: int,
        source_path: str,
        target_path: str,
        performed_action: str,
        result: str,
        error_message: str | None,
        target_deleted: bool,
        created_at: str,
    ) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO rollback_logs (
                    id, rollback_run_id, operation_log_id, sequence_no, source_path, target_path,
                    performed_action, result, error_message, target_deleted, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rollback_log_id,
                    rollback_run_id,
                    operation_log_id,
                    sequence_no,
                    source_path,
                    target_path,
                    performed_action,
                    result,
                    error_message,
                    1 if target_deleted else 0,
                    created_at,
                ),
            )

    def has_successful_rollback(self, *, operation_log_id: str) -> bool:
        row = self._connection.execute(
            """
            SELECT 1
            FROM rollback_logs
            WHERE operation_log_id = ?
              AND result = 'success'
            LIMIT 1
            """,
            (operation_log_id,),
        ).fetchone()
        return row is not None

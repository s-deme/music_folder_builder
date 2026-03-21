from __future__ import annotations

import sqlite3


class RollbackLogRepository:
    _INSERT_ROLLBACK_LOG_SQL = """
        INSERT INTO rollback_logs (
            id, rollback_run_id, operation_log_id, sequence_no, source_path, target_path,
            performed_action, result, error_message, target_deleted, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

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
        self._connection.execute(
            self._INSERT_ROLLBACK_LOG_SQL,
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

    def insert_rollback_logs_batch(self, *, rows: list[tuple[object, ...]]) -> None:
        self._connection.executemany(self._INSERT_ROLLBACK_LOG_SQL, rows)

    def has_successful_rollback(self, *, operation_log_id: str) -> bool:
        row = self._connection.execute(
            """
            SELECT 1
            FROM rollback_logs AS rl
            JOIN rollback_runs AS rr ON rr.id = rl.rollback_run_id
            WHERE rl.operation_log_id = ?
              AND rl.result = 'success'
              AND rr.mode = 'rollback'
            LIMIT 1
            """,
            (operation_log_id,),
        ).fetchone()
        return row is not None

    def fetch_successful_rollback_operation_ids(self, *, operation_log_ids: list[str]) -> set[str]:
        if not operation_log_ids:
            return set()
        placeholders = ",".join("?" for _ in operation_log_ids)
        rows = self._connection.execute(
            f"""
            SELECT DISTINCT rl.operation_log_id
            FROM rollback_logs AS rl
            JOIN rollback_runs AS rr ON rr.id = rl.rollback_run_id
            WHERE rl.operation_log_id IN ({placeholders})
              AND rl.result = 'success'
              AND rr.mode = 'rollback'
            """,
            tuple(operation_log_ids),
        ).fetchall()
        return {row["operation_log_id"] for row in rows}

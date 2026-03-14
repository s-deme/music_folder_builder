from __future__ import annotations

import sqlite3


class OperationLogRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def insert_operation_log(
        self,
        *,
        operation_log_id: str,
        execution_run_id: str,
        plan_item_id: str,
        sequence_no: int,
        source_path: str,
        target_path: str,
        performed_action: str,
        result: str,
        error_message: str | None,
        source_deleted: bool,
        created_at: str,
    ) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO operation_logs (
                    id, execution_run_id, plan_item_id, sequence_no, source_path, target_path,
                    performed_action, result, error_message, source_deleted, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operation_log_id,
                    execution_run_id,
                    plan_item_id,
                    sequence_no,
                    source_path,
                    target_path,
                    performed_action,
                    result,
                    error_message,
                    1 if source_deleted else 0,
                    created_at,
                ),
            )

    def has_successful_apply(self, *, plan_item_id: str) -> bool:
        row = self._connection.execute(
            """
            SELECT 1
            FROM operation_logs AS ol
            JOIN execution_runs AS er ON er.id = ol.execution_run_id
            WHERE ol.plan_item_id = ?
              AND ol.result = 'success'
              AND er.mode = 'apply'
            LIMIT 1
            """,
            (plan_item_id,),
        ).fetchone()
        return row is not None

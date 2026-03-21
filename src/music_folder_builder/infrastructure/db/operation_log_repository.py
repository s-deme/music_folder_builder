from __future__ import annotations

import sqlite3


class OperationLogRepository:
    _INSERT_OPERATION_LOG_SQL = """
        INSERT INTO operation_logs (
            id, execution_run_id, plan_item_id, sequence_no, source_path, target_path,
            performed_action, result, error_message, source_deleted, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

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
        self._connection.execute(
            self._INSERT_OPERATION_LOG_SQL,
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

    def insert_operation_logs_batch(self, *, rows: list[tuple[object, ...]]) -> None:
        self._connection.executemany(self._INSERT_OPERATION_LOG_SQL, rows)

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

    def fetch_successful_apply_plan_item_ids(self, *, plan_item_ids: list[str]) -> set[str]:
        if not plan_item_ids:
            return set()
        placeholders = ",".join("?" for _ in plan_item_ids)
        rows = self._connection.execute(
            f"""
            SELECT DISTINCT ol.plan_item_id
            FROM operation_logs AS ol
            JOIN execution_runs AS er ON er.id = ol.execution_run_id
            WHERE ol.plan_item_id IN ({placeholders})
              AND ol.result = 'success'
              AND er.mode = 'apply'
            """,
            tuple(plan_item_ids),
        ).fetchall()
        return {row["plan_item_id"] for row in rows}

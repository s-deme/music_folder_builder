from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RollbackItemRecord:
    operation_log_id: str
    plan_item_id: str
    sequence_no: int
    source_path: str
    target_path: str
    performed_action: str
    result: str


class ApplyHistoryRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def fetch_rollback_items(self, *, execution_run_id: str) -> list[RollbackItemRecord]:
        rows = self._connection.execute(
            """
            SELECT
                ol.id AS operation_log_id,
                ol.plan_item_id AS plan_item_id,
                ol.sequence_no AS sequence_no,
                ol.source_path AS source_path,
                ol.target_path AS target_path,
                ol.performed_action AS performed_action,
                ol.result AS result
            FROM operation_logs AS ol
            JOIN execution_runs AS er ON er.id = ol.execution_run_id
            WHERE ol.execution_run_id = ?
              AND er.mode = 'apply'
              AND ol.result = 'success'
              AND ol.performed_action IN ('move', 'copy_delete')
            ORDER BY ol.sequence_no DESC
            """,
            (execution_run_id,),
        ).fetchall()
        return [
            RollbackItemRecord(
                operation_log_id=row["operation_log_id"],
                plan_item_id=row["plan_item_id"],
                sequence_no=row["sequence_no"],
                source_path=row["source_path"],
                target_path=row["target_path"],
                performed_action=row["performed_action"],
                result=row["result"],
            )
            for row in rows
        ]

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApplyVerifyItemRecord:
    operation_log_id: str
    sequence_no: int
    source_path: str
    target_path: str
    expected_state: str
    source_deleted: bool


class ApplyVerifyRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def fetch_apply_verify_items(self, *, execution_run_id: str) -> list[ApplyVerifyItemRecord]:
        rows = self._connection.execute(
            """
            SELECT
                ol.id AS operation_log_id,
                ol.sequence_no AS sequence_no,
                ol.source_path AS source_path,
                ol.target_path AS target_path,
                ol.source_deleted AS source_deleted
            FROM operation_logs AS ol
            JOIN execution_runs AS er ON er.id = ol.execution_run_id
            WHERE ol.execution_run_id = ?
              AND er.mode = 'apply'
              AND ol.result = 'success'
              AND ol.performed_action IN ('move', 'copy_delete')
            ORDER BY ol.sequence_no ASC
            """,
            (execution_run_id,),
        ).fetchall()
        return [
            ApplyVerifyItemRecord(
                operation_log_id=row["operation_log_id"],
                sequence_no=row["sequence_no"],
                source_path=row["source_path"],
                target_path=row["target_path"],
                expected_state="target_present_source_absent"
                if row["source_deleted"]
                else "target_present_source_present",
                source_deleted=bool(row["source_deleted"]),
            )
            for row in rows
        ]

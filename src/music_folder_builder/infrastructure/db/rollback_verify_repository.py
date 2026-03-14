from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RollbackVerifyItemRecord:
    rollback_log_id: str
    sequence_no: int
    source_path: str
    target_path: str
    expected_state: str
    target_deleted: bool


class RollbackVerifyRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def fetch_rollback_verify_items(self, *, rollback_run_id: str) -> list[RollbackVerifyItemRecord]:
        rows = self._connection.execute(
            """
            SELECT
                rl.id AS rollback_log_id,
                rl.sequence_no AS sequence_no,
                rl.source_path AS source_path,
                rl.target_path AS target_path,
                rl.target_deleted AS target_deleted
            FROM rollback_logs AS rl
            WHERE rl.rollback_run_id = ?
              AND rl.result = 'success'
              AND rl.performed_action IN ('reverse_move', 'reverse_copy')
            ORDER BY rl.sequence_no ASC
            """,
            (rollback_run_id,),
        ).fetchall()
        return [
            RollbackVerifyItemRecord(
                rollback_log_id=row["rollback_log_id"],
                sequence_no=row["sequence_no"],
                source_path=row["source_path"],
                target_path=row["target_path"],
                expected_state="source_present_target_absent"
                if row["target_deleted"]
                else "source_present_target_present",
                target_deleted=bool(row["target_deleted"]),
            )
            for row in rows
        ]

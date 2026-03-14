from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApplyPlanItemRecord:
    plan_item_id: str
    source_path: str
    target_path: str
    action: str
    reason: str | None


class PlanQueryRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def fetch_apply_items(self, *, plan_run_id: str) -> list[ApplyPlanItemRecord]:
        rows = self._connection.execute(
            """
            SELECT
                p.id AS plan_item_id,
                f.source_path AS source_path,
                p.target_path_sanitized AS target_path,
                p.action AS action,
                p.reason AS reason
            FROM plan_items AS p
            JOIN scanned_files AS f ON f.id = p.file_id
            WHERE p.plan_run_id = ?
            ORDER BY f.source_path
            """,
            (plan_run_id,),
        ).fetchall()
        return [
            ApplyPlanItemRecord(
                plan_item_id=row["plan_item_id"],
                source_path=row["source_path"],
                target_path=row["target_path"],
                action=row["action"],
                reason=row["reason"],
            )
            for row in rows
        ]

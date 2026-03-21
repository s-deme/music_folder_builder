from __future__ import annotations

import sqlite3


class PlanRepository:
    _INSERT_PLAN_ITEM_SQL = """
        INSERT INTO plan_items (
            id, plan_run_id, file_id, action, target_path, target_path_sanitized,
            conflict_status, risk_status, reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def insert_plan_item(
        self,
        *,
        plan_item_id: str,
        plan_run_id: str,
        file_id: str,
        action: str,
        target_path: str | None,
        target_path_sanitized: str | None,
        conflict_status: str,
        risk_status: str,
        reason: str | None,
    ) -> None:
        self._connection.execute(
            self._INSERT_PLAN_ITEM_SQL,
            (
                plan_item_id,
                plan_run_id,
                file_id,
                action,
                target_path,
                target_path_sanitized,
                conflict_status,
                risk_status,
                reason,
            ),
        )

    def insert_plan_items_batch(self, *, rows: list[tuple[object, ...]]) -> None:
        self._connection.executemany(self._INSERT_PLAN_ITEM_SQL, rows)

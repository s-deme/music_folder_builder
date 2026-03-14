from __future__ import annotations

import sqlite3
from pathlib import Path


class RunRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_scan_run(self, *, scan_run_id: str, source_root: Path, started_at: str) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO scan_runs (id, source_root, started_at, status, file_count, warning_count)
                VALUES (?, ?, ?, 'running', 0, 0)
                """,
                (scan_run_id, str(source_root), started_at),
            )

    def complete_scan_run(
        self,
        *,
        scan_run_id: str,
        finished_at: str,
        file_count: int,
        warning_count: int,
    ) -> None:
        with self._connection:
            self._connection.execute(
                """
                UPDATE scan_runs
                SET finished_at = ?, status = 'completed', file_count = ?, warning_count = ?
                WHERE id = ?
                """,
                (finished_at, file_count, warning_count, scan_run_id),
            )

    def create_plan_run(self, *, plan_run_id: str, scan_run_id: str, started_at: str) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO plan_runs (
                    id, scan_run_id, started_at, status, rule_profile, conflict_count, risk_count
                ) VALUES (?, ?, ?, 'running', 'default', 0, 0)
                """,
                (plan_run_id, scan_run_id, started_at),
            )

    def complete_plan_run(
        self,
        *,
        plan_run_id: str,
        finished_at: str,
        conflict_count: int,
        risk_count: int,
    ) -> None:
        with self._connection:
            self._connection.execute(
                """
                UPDATE plan_runs
                SET finished_at = ?, status = 'completed', conflict_count = ?, risk_count = ?
                WHERE id = ?
                """,
                (finished_at, conflict_count, risk_count, plan_run_id),
            )

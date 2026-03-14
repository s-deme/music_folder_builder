from __future__ import annotations

import sqlite3


class ExecutionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_execution_run(self, *, execution_run_id: str, plan_run_id: str, mode: str, started_at: str) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO execution_runs (
                    id, plan_run_id, mode, started_at, status,
                    success_count, skipped_count, failed_count, risky_count
                ) VALUES (?, ?, ?, ?, 'running', 0, 0, 0, 0)
                """,
                (execution_run_id, plan_run_id, mode, started_at),
            )

    def complete_execution_run(
        self,
        *,
        execution_run_id: str,
        finished_at: str,
        success_count: int,
        skipped_count: int,
        failed_count: int,
        risky_count: int,
    ) -> None:
        status = "completed" if failed_count == 0 else "partial"
        with self._connection:
            self._connection.execute(
                """
                UPDATE execution_runs
                SET finished_at = ?, status = ?, success_count = ?, skipped_count = ?, failed_count = ?, risky_count = ?
                WHERE id = ?
                """,
                (
                    finished_at,
                    status,
                    success_count,
                    skipped_count,
                    failed_count,
                    risky_count,
                    execution_run_id,
                ),
            )

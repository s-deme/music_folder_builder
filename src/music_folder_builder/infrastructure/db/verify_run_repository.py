from __future__ import annotations

import sqlite3


class VerifyRunRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_verify_run(
        self,
        *,
        verify_run_id: str,
        execution_run_id: str | None,
        rollback_run_id: str | None,
        started_at: str,
    ) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO verify_runs (
                    id, execution_run_id, rollback_run_id, started_at, status,
                    success_count, skipped_count, failed_count, risky_count
                ) VALUES (?, ?, ?, ?, 'running', 0, 0, 0, 0)
                """,
                (verify_run_id, execution_run_id, rollback_run_id, started_at),
            )

    def complete_verify_run(
        self,
        *,
        verify_run_id: str,
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
                UPDATE verify_runs
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
                    verify_run_id,
                ),
            )

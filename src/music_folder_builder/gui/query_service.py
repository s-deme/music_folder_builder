from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.db.schema import initialize_schema


@dataclass(frozen=True, slots=True)
class RunRow:
    run_id: str
    status: str
    started_at: str
    finished_at: str | None
    primary_count: int
    secondary_count: int
    detail: str


@dataclass(frozen=True, slots=True)
class PlanItemRow:
    plan_item_id: str
    source_path: str
    target_path: str | None
    action: str
    conflict_status: str
    risk_status: str
    reason: str | None
    artist: str | None
    album: str | None
    title: str | None


@dataclass(frozen=True, slots=True)
class LogRow:
    sequence_no: int
    source_path: str
    target_path: str
    action: str
    result: str
    error_message: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class VerifyLogRow:
    sequence_no: int
    subject_path: str
    counterpart_path: str | None
    expected_state: str
    actual_state: str
    result: str
    error_message: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class ActiveProgress:
    stage: str
    run_id: str
    processed: int
    total: int | None
    detail: str


class GuiQueryService:
    _COMPANION_IMAGE_EXTENSIONS = (".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp")

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def list_scan_runs(self, *, limit: int = 20) -> list[RunRow]:
        rows = self._fetchall(
            """
            SELECT id, status, started_at, finished_at, file_count, warning_count, source_root
            FROM scan_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [
            RunRow(
                run_id=row["id"],
                status=row["status"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                primary_count=row["file_count"],
                secondary_count=row["warning_count"],
                detail=row["source_root"],
            )
            for row in rows
        ]

    def list_plan_runs(self, *, limit: int = 20) -> list[RunRow]:
        rows = self._fetchall(
            """
            SELECT
                p.id,
                p.status,
                p.started_at,
                p.finished_at,
                COUNT(i.id) AS item_count,
                p.risk_count,
                p.scan_run_id
            FROM plan_runs AS p
            LEFT JOIN plan_items AS i ON i.plan_run_id = p.id
            GROUP BY p.id, p.status, p.started_at, p.finished_at, p.risk_count, p.scan_run_id
            ORDER BY p.started_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [
            RunRow(
                run_id=row["id"],
                status=row["status"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                primary_count=row["item_count"],
                secondary_count=row["risk_count"],
                detail=f"scan={row['scan_run_id']}",
            )
            for row in rows
        ]

    def list_execution_runs(self, *, limit: int = 20) -> list[RunRow]:
        rows = self._fetchall(
            """
            SELECT
                id,
                status,
                started_at,
                finished_at,
                success_count,
                failed_count,
                mode
            FROM execution_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [
            RunRow(
                run_id=row["id"],
                status=row["status"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                primary_count=row["success_count"],
                secondary_count=row["failed_count"],
                detail=row["mode"],
            )
            for row in rows
        ]

    def list_rollback_runs(self, *, limit: int = 20) -> list[RunRow]:
        rows = self._fetchall(
            """
            SELECT
                id,
                status,
                started_at,
                finished_at,
                success_count,
                failed_count,
                mode
            FROM rollback_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [
            RunRow(
                run_id=row["id"],
                status=row["status"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                primary_count=row["success_count"],
                secondary_count=row["failed_count"],
                detail=row["mode"],
            )
            for row in rows
        ]

    def list_verify_runs(self, *, limit: int = 20) -> list[RunRow]:
        rows = self._fetchall(
            """
            SELECT
                id,
                status,
                started_at,
                finished_at,
                success_count,
                failed_count,
                CASE
                    WHEN execution_run_id IS NOT NULL THEN 'execution'
                    ELSE 'rollback'
                END AS mode
            FROM verify_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [
            RunRow(
                run_id=row["id"],
                status=row["status"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                primary_count=row["success_count"],
                secondary_count=row["failed_count"],
                detail=row["mode"],
            )
            for row in rows
        ]

    def list_plan_items(
        self,
        *,
        plan_run_id: str,
        warnings_only: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[PlanItemRow]:
        query = """
            SELECT
                p.id AS plan_item_id,
                f.source_path,
                p.target_path_sanitized,
                p.action,
                p.conflict_status,
                p.risk_status,
                p.reason,
                m.artist,
                m.album,
                m.title
            FROM plan_items AS p
            JOIN scanned_files AS f ON f.id = p.file_id
            LEFT JOIN scanned_metadata AS m ON m.file_id = f.id
            WHERE p.plan_run_id = ?
        """
        params: tuple[object, ...] = (plan_run_id,)
        if warnings_only:
            query = f"{query}\n  AND (p.conflict_status != 'none' OR p.risk_status != 'none')"
        query = f"{query}\nORDER BY f.source_path"
        if limit is not None:
            query = f"{query}\nLIMIT ? OFFSET ?"
            params = (plan_run_id, limit, offset)
        rows = self._fetchall(query, params)
        return [
            PlanItemRow(
                plan_item_id=row["plan_item_id"],
                source_path=row["source_path"],
                target_path=row["target_path_sanitized"],
                action=row["action"],
                conflict_status=row["conflict_status"],
                risk_status=row["risk_status"],
                reason=row["reason"],
                artist=row["artist"],
                album=row["album"],
                title=row["title"],
            )
            for row in rows
        ]

    def count_plan_items(self, *, plan_run_id: str, warnings_only: bool = False) -> int:
        query = "SELECT COUNT(*) AS count FROM plan_items WHERE plan_run_id = ?"
        if warnings_only:
            query = f"{query} AND (conflict_status != 'none' OR risk_status != 'none')"
        row = self._fetchone(query, (plan_run_id,))
        return int(row["count"]) if row is not None else 0

    def list_operation_logs(
        self, *, execution_run_id: str, limit: int | None = None, offset: int = 0
    ) -> list[LogRow]:
        query = """
            SELECT sequence_no, source_path, target_path, performed_action, result, error_message, created_at
            FROM operation_logs
            WHERE execution_run_id = ?
            ORDER BY sequence_no
        """
        params: tuple[object, ...] = (execution_run_id,)
        if limit is not None:
            query = f"{query}\nLIMIT ? OFFSET ?"
            params = (execution_run_id, limit, offset)
        rows = self._fetchall(query, params)
        return [
            LogRow(
                sequence_no=row["sequence_no"],
                source_path=row["source_path"],
                target_path=row["target_path"],
                action=row["performed_action"],
                result=row["result"],
                error_message=row["error_message"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def count_operation_logs(self, *, execution_run_id: str) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS count FROM operation_logs WHERE execution_run_id = ?",
            (execution_run_id,),
        )
        return int(row["count"]) if row is not None else 0

    def list_rollback_logs(self, *, rollback_run_id: str, limit: int | None = None, offset: int = 0) -> list[LogRow]:
        query = """
            SELECT sequence_no, source_path, target_path, performed_action, result, error_message, created_at
            FROM rollback_logs
            WHERE rollback_run_id = ?
            ORDER BY sequence_no
        """
        params: tuple[object, ...] = (rollback_run_id,)
        if limit is not None:
            query = f"{query}\nLIMIT ? OFFSET ?"
            params = (rollback_run_id, limit, offset)
        rows = self._fetchall(query, params)
        return [
            LogRow(
                sequence_no=row["sequence_no"],
                source_path=row["source_path"],
                target_path=row["target_path"],
                action=row["performed_action"],
                result=row["result"],
                error_message=row["error_message"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def count_rollback_logs(self, *, rollback_run_id: str) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS count FROM rollback_logs WHERE rollback_run_id = ?",
            (rollback_run_id,),
        )
        return int(row["count"]) if row is not None else 0

    def list_verify_logs(self, *, verify_run_id: str, limit: int | None = None, offset: int = 0) -> list[VerifyLogRow]:
        query = """
            SELECT
                sequence_no,
                subject_path,
                counterpart_path,
                expected_state,
                actual_state,
                result,
                error_message,
                created_at
            FROM verify_logs
            WHERE verify_run_id = ?
            ORDER BY sequence_no
        """
        params: tuple[object, ...] = (verify_run_id,)
        if limit is not None:
            query = f"{query}\nLIMIT ? OFFSET ?"
            params = (verify_run_id, limit, offset)
        rows = self._fetchall(query, params)
        return [
            VerifyLogRow(
                sequence_no=row["sequence_no"],
                subject_path=row["subject_path"],
                counterpart_path=row["counterpart_path"],
                expected_state=row["expected_state"],
                actual_state=row["actual_state"],
                result=row["result"],
                error_message=row["error_message"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def count_verify_logs(self, *, verify_run_id: str) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS count FROM verify_logs WHERE verify_run_id = ?",
            (verify_run_id,),
        )
        return int(row["count"]) if row is not None else 0

    def find_active_progress(self) -> ActiveProgress | None:
        progress = self._find_active_scan_progress()
        if progress is not None:
            return progress
        progress = self._find_active_plan_progress()
        if progress is not None:
            return progress
        progress = self._find_active_execution_progress()
        if progress is not None:
            return progress
        progress = self._find_active_rollback_progress()
        if progress is not None:
            return progress
        return self._find_active_verify_progress()

    def _find_active_scan_progress(self) -> ActiveProgress | None:
        row = self._fetchone(
            """
            SELECT id, source_root
            FROM scan_runs
            WHERE status = 'running'
            ORDER BY started_at DESC
            LIMIT 1
            """
        )
        if row is None:
            return None
        processed_row = self._fetchone(
            "SELECT COUNT(*) AS count FROM scanned_files WHERE scan_run_id = ?",
            (row["id"],),
        )
        return ActiveProgress(
            stage="scan",
            run_id=row["id"],
            processed=processed_row["count"],
            total=None,
            detail=row["source_root"],
        )

    def delete_scan_run(self, *, scan_run_id: str) -> None:
        with connect_sqlite(self._db_path) as connection:
            initialize_schema(connection)
            plan_rows = connection.execute(
                "SELECT id FROM plan_runs WHERE scan_run_id = ?",
                (scan_run_id,),
            ).fetchall()
            for row in plan_rows:
                self._delete_plan_run(connection, plan_run_id=row["id"])

            file_rows = connection.execute(
                "SELECT id FROM scanned_files WHERE scan_run_id = ?",
                (scan_run_id,),
            ).fetchall()
            file_ids = [row["id"] for row in file_rows]
            if file_ids:
                placeholders = ",".join("?" for _ in file_ids)
                connection.execute(
                    f"DELETE FROM scanned_metadata WHERE file_id IN ({placeholders})",
                    tuple(file_ids),
                )
            connection.execute("DELETE FROM scanned_files WHERE scan_run_id = ?", (scan_run_id,))
            connection.execute("DELETE FROM scan_runs WHERE id = ?", (scan_run_id,))
            connection.commit()

    def delete_plan_run(self, *, plan_run_id: str) -> None:
        with connect_sqlite(self._db_path) as connection:
            initialize_schema(connection)
            self._delete_plan_run(connection, plan_run_id=plan_run_id)
            connection.commit()

    def delete_execution_run(self, *, execution_run_id: str) -> None:
        with connect_sqlite(self._db_path) as connection:
            initialize_schema(connection)
            self._delete_execution_run(connection, execution_run_id=execution_run_id)
            connection.commit()

    def delete_rollback_run(self, *, rollback_run_id: str) -> None:
        with connect_sqlite(self._db_path) as connection:
            initialize_schema(connection)
            self._delete_rollback_run(connection, rollback_run_id=rollback_run_id)
            connection.commit()

    def delete_verify_run(self, *, verify_run_id: str) -> None:
        with connect_sqlite(self._db_path) as connection:
            initialize_schema(connection)
            self._delete_verify_run(connection, verify_run_id=verify_run_id)
            connection.commit()

    def _find_active_plan_progress(self) -> ActiveProgress | None:
        row = self._fetchone(
            """
            SELECT id, scan_run_id
            FROM plan_runs
            WHERE status = 'running'
            ORDER BY started_at DESC
            LIMIT 1
            """
        )
        if row is None:
            return None
        processed = self._fetchone(
            "SELECT COUNT(*) AS count FROM plan_items WHERE plan_run_id = ?",
            (row["id"],),
        )["count"]
        placeholders = ", ".join("?" for _ in self._COMPANION_IMAGE_EXTENSIONS)
        total = self._fetchone(
            f"""
            SELECT COUNT(*) AS count
            FROM scanned_files
            WHERE scan_run_id = ?
              AND (
                file_type = 'music'
                OR (file_type = 'unsupported' AND extension IN ({placeholders}))
              )
            """,
            (row["scan_run_id"], *self._COMPANION_IMAGE_EXTENSIONS),
        )["count"]
        return ActiveProgress(
            stage="plan",
            run_id=row["id"],
            processed=processed,
            total=total,
            detail=f"scan={row['scan_run_id']}",
        )

    def _find_active_execution_progress(self) -> ActiveProgress | None:
        row = self._fetchone(
            """
            SELECT id, plan_run_id, mode
            FROM execution_runs
            WHERE status = 'running'
            ORDER BY started_at DESC
            LIMIT 1
            """
        )
        if row is None:
            return None
        processed = self._fetchone(
            "SELECT COUNT(*) AS count FROM operation_logs WHERE execution_run_id = ?",
            (row["id"],),
        )["count"]
        total = self._fetchone(
            "SELECT COUNT(*) AS count FROM plan_items WHERE plan_run_id = ?",
            (row["plan_run_id"],),
        )["count"]
        return ActiveProgress(
            stage="apply",
            run_id=row["id"],
            processed=processed,
            total=total,
            detail=row["mode"],
        )

    def _find_active_rollback_progress(self) -> ActiveProgress | None:
        row = self._fetchone(
            """
            SELECT id, execution_run_id, mode
            FROM rollback_runs
            WHERE status = 'running'
            ORDER BY started_at DESC
            LIMIT 1
            """
        )
        if row is None:
            return None
        processed = self._fetchone(
            "SELECT COUNT(*) AS count FROM rollback_logs WHERE rollback_run_id = ?",
            (row["id"],),
        )["count"]
        total = self._fetchone(
            """
            SELECT COUNT(*) AS count
            FROM operation_logs AS ol
            JOIN execution_runs AS er ON er.id = ol.execution_run_id
            WHERE ol.execution_run_id = ?
              AND er.mode = 'apply'
              AND ol.result = 'success'
              AND ol.performed_action IN ('move', 'copy_delete')
            """,
            (row["execution_run_id"],),
        )["count"]
        return ActiveProgress(
            stage="rollback",
            run_id=row["id"],
            processed=processed,
            total=total,
            detail=row["mode"],
        )

    def _find_active_verify_progress(self) -> ActiveProgress | None:
        row = self._fetchone(
            """
            SELECT id, execution_run_id, rollback_run_id
            FROM verify_runs
            WHERE status = 'running'
            ORDER BY started_at DESC
            LIMIT 1
            """
        )
        if row is None:
            return None
        processed = self._fetchone(
            "SELECT COUNT(*) AS count FROM verify_logs WHERE verify_run_id = ?",
            (row["id"],),
        )["count"]
        if row["execution_run_id"] is not None:
            total = self._fetchone(
                "SELECT COUNT(*) AS count FROM operation_logs WHERE execution_run_id = ?",
                (row["execution_run_id"],),
            )["count"]
            detail = "execution"
        else:
            total = self._fetchone(
                "SELECT COUNT(*) AS count FROM rollback_logs WHERE rollback_run_id = ?",
                (row["rollback_run_id"],),
            )["count"]
            detail = "rollback"
        return ActiveProgress(
            stage="verify",
            run_id=row["id"],
            processed=processed,
            total=total,
            detail=detail,
        )

    def _fetchall(self, query: str, params: tuple[object, ...] = ()) -> list[dict[str, object]]:
        with connect_sqlite(self._db_path) as connection:
            initialize_schema(connection)
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def _fetchone(self, query: str, params: tuple[object, ...] = ()) -> dict[str, object] | None:
        with connect_sqlite(self._db_path) as connection:
            initialize_schema(connection)
            row = connection.execute(query, params).fetchone()
        return None if row is None else dict(row)

    def _delete_plan_run(self, connection: object, *, plan_run_id: str) -> None:
        execution_rows = connection.execute(
            "SELECT id FROM execution_runs WHERE plan_run_id = ?",
            (plan_run_id,),
        ).fetchall()
        for row in execution_rows:
            self._delete_execution_run(connection, execution_run_id=row["id"])
        connection.execute("DELETE FROM plan_items WHERE plan_run_id = ?", (plan_run_id,))
        connection.execute("DELETE FROM plan_runs WHERE id = ?", (plan_run_id,))

    def _delete_execution_run(self, connection: object, *, execution_run_id: str) -> None:
        verify_rows = connection.execute(
            "SELECT id FROM verify_runs WHERE execution_run_id = ?",
            (execution_run_id,),
        ).fetchall()
        for row in verify_rows:
            self._delete_verify_run(connection, verify_run_id=row["id"])

        rollback_rows = connection.execute(
            "SELECT id FROM rollback_runs WHERE execution_run_id = ?",
            (execution_run_id,),
        ).fetchall()
        for row in rollback_rows:
            self._delete_rollback_run(connection, rollback_run_id=row["id"])

        connection.execute("DELETE FROM operation_logs WHERE execution_run_id = ?", (execution_run_id,))
        connection.execute("DELETE FROM execution_runs WHERE id = ?", (execution_run_id,))

    def _delete_rollback_run(self, connection: object, *, rollback_run_id: str) -> None:
        verify_rows = connection.execute(
            "SELECT id FROM verify_runs WHERE rollback_run_id = ?",
            (rollback_run_id,),
        ).fetchall()
        for row in verify_rows:
            self._delete_verify_run(connection, verify_run_id=row["id"])

        connection.execute("DELETE FROM rollback_logs WHERE rollback_run_id = ?", (rollback_run_id,))
        connection.execute("DELETE FROM rollback_runs WHERE id = ?", (rollback_run_id,))

    def _delete_verify_run(self, connection: object, *, verify_run_id: str) -> None:
        connection.execute("DELETE FROM verify_logs WHERE verify_run_id = ?", (verify_run_id,))
        connection.execute("DELETE FROM verify_runs WHERE id = ?", (verify_run_id,))

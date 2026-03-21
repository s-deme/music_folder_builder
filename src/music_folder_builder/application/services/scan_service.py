from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from music_folder_builder.application.dto.scan_request import ScanRequest
from music_folder_builder.application.dto.scan_result import ScanResult
from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.db.run_repository import RunRepository
from music_folder_builder.infrastructure.db.scan_repository import ScanRepository
from music_folder_builder.infrastructure.db.schema import initialize_schema
from music_folder_builder.infrastructure.fs.walker import FileWalker
from music_folder_builder.infrastructure.metadata.reader import MetadataReadResult, MetadataReader


class ScanService:
    _DEFAULT_BATCH_SIZE = 250

    def __init__(
        self,
        *,
        walker: FileWalker | None = None,
        metadata_reader: MetadataReader | None = None,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> None:
        self._walker = walker or FileWalker()
        self._metadata_reader = metadata_reader or MetadataReader()
        self._batch_size = batch_size

    def execute(self, request: ScanRequest) -> ScanResult:
        scan_run_id = str(uuid4())
        warning_count = 0
        file_count = 0

        with connect_sqlite(request.db_path) as connection:
            initialize_schema(connection)
            run_repository = RunRepository(connection)
            scan_repository = ScanRepository(connection)

            run_repository.create_scan_run(
                scan_run_id=scan_run_id,
                source_root=request.source_root,
                started_at=_utc_now(),
            )

            scanned_file_rows: list[tuple[object, ...]] = []
            scanned_metadata_rows: list[tuple[object, ...]] = []
            for file_info in self._walker.walk(request.source_root):
                file_count += 1
                file_id = str(uuid4())
                stat_result = file_info.path.lstat()
                scanned_file_rows.append(
                    (
                        file_id,
                        scan_run_id,
                        str(file_info.path),
                        str(request.source_root),
                        file_info.extension,
                        stat_result.st_size,
                        datetime.fromtimestamp(stat_result.st_mtime, UTC).isoformat(),
                        file_info.file_type,
                        None if file_info.file_type == "music" else file_info.file_type,
                        file_info.link_state,
                    )
                )

                if file_info.file_type == "music":
                    try:
                        metadata_result = self._metadata_reader.read(file_info.path)
                    except Exception as error:
                        warning_count += 1
                        metadata_result = MetadataReadResult(
                            metadata_status="error",
                            metadata_error=str(error),
                        )
                    scanned_metadata_rows.append(
                        (
                            file_id,
                            metadata_result.artist,
                            metadata_result.album_artist,
                            metadata_result.album,
                            metadata_result.title,
                            metadata_result.track_no,
                            metadata_result.disc_no,
                            metadata_result.year,
                            metadata_result.metadata_status,
                            metadata_result.metadata_error,
                        )
                    )

                if len(scanned_file_rows) >= self._batch_size:
                    self._flush_scan_batch(
                        connection,
                        scan_repository,
                        scanned_file_rows=scanned_file_rows,
                        scanned_metadata_rows=scanned_metadata_rows,
                    )

            self._flush_scan_batch(
                connection,
                scan_repository,
                scanned_file_rows=scanned_file_rows,
                scanned_metadata_rows=scanned_metadata_rows,
            )

            run_repository.complete_scan_run(
                scan_run_id=scan_run_id,
                finished_at=_utc_now(),
                file_count=file_count,
                warning_count=warning_count,
            )

        return ScanResult(
            scan_run_id=scan_run_id,
            file_count=file_count,
            warning_count=warning_count,
        )

    def _flush_scan_batch(
        self,
        connection: object,
        scan_repository: ScanRepository,
        *,
        scanned_file_rows: list[tuple[object, ...]],
        scanned_metadata_rows: list[tuple[object, ...]],
    ) -> None:
        if not scanned_file_rows:
            return
        scan_repository.insert_scanned_files_batch(rows=scanned_file_rows)
        if scanned_metadata_rows:
            scan_repository.insert_scanned_metadata_batch(rows=scanned_metadata_rows)
        connection.commit()
        scanned_file_rows.clear()
        scanned_metadata_rows.clear()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()

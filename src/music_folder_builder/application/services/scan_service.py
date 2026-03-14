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
    def __init__(
        self,
        *,
        walker: FileWalker | None = None,
        metadata_reader: MetadataReader | None = None,
    ) -> None:
        self._walker = walker or FileWalker()
        self._metadata_reader = metadata_reader or MetadataReader()

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

            for file_info in self._walker.walk(request.source_root):
                file_count += 1
                file_id = str(uuid4())
                stat_result = file_info.path.lstat()
                scan_repository.insert_scanned_file(
                    file_id=file_id,
                    scan_run_id=scan_run_id,
                    source_path=file_info.path,
                    source_root=request.source_root,
                    extension=file_info.extension,
                    size_bytes=stat_result.st_size,
                    mtime_utc=datetime.fromtimestamp(stat_result.st_mtime, UTC).isoformat(),
                    file_type=file_info.file_type,
                    exclusion_reason=None if file_info.file_type == "music" else file_info.file_type,
                    link_state=file_info.link_state,
                )

                if file_info.file_type != "music":
                    continue

                try:
                    metadata_result = self._metadata_reader.read(file_info.path)
                except Exception as error:
                    warning_count += 1
                    metadata_result = MetadataReadResult(
                        metadata_status="error",
                        metadata_error=str(error),
                    )

                scan_repository.insert_scanned_metadata(file_id=file_id, metadata=metadata_result)

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


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()

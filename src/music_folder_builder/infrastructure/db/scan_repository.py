from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from music_folder_builder.infrastructure.metadata.reader import MetadataReadResult


@dataclass(frozen=True, slots=True)
class PlannedScanRecord:
    file_id: str
    source_path: str
    source_root: str
    source_stem: str
    extension: str
    artist: str | None
    album_artist: str | None
    album: str | None
    title: str | None
    track_no: int | None
    disc_no: int | None


@dataclass(frozen=True, slots=True)
class CompanionAssetRecord:
    file_id: str
    source_path: str
    extension: str


class ScanRepository:
    _INSERT_SCANNED_FILE_SQL = """
        INSERT INTO scanned_files (
            id, scan_run_id, source_path, source_root, extension, size_bytes,
            mtime_utc, file_type, exclusion_reason, link_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    _INSERT_SCANNED_METADATA_SQL = """
        INSERT INTO scanned_metadata (
            file_id, artist, album_artist, album, title, track_no, disc_no,
            year, metadata_status, metadata_error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def insert_scanned_file(
        self,
        *,
        file_id: str,
        scan_run_id: str,
        source_path: Path,
        source_root: Path,
        extension: str,
        size_bytes: int,
        mtime_utc: str,
        file_type: str,
        exclusion_reason: str | None,
        link_state: str,
    ) -> None:
        self._connection.execute(
            self._INSERT_SCANNED_FILE_SQL,
            (
                file_id,
                scan_run_id,
                str(source_path),
                str(source_root),
                extension,
                size_bytes,
                mtime_utc,
                file_type,
                exclusion_reason,
                link_state,
            ),
        )

    def insert_scanned_metadata(self, *, file_id: str, metadata: MetadataReadResult) -> None:
        self._connection.execute(
            self._INSERT_SCANNED_METADATA_SQL,
            (
                file_id,
                metadata.artist,
                metadata.album_artist,
                metadata.album,
                metadata.title,
                metadata.track_no,
                metadata.disc_no,
                metadata.year,
                metadata.metadata_status,
                metadata.metadata_error,
            ),
        )

    def insert_scanned_files_batch(self, *, rows: list[tuple[object, ...]]) -> None:
        self._connection.executemany(self._INSERT_SCANNED_FILE_SQL, rows)

    def insert_scanned_metadata_batch(self, *, rows: list[tuple[object, ...]]) -> None:
        self._connection.executemany(self._INSERT_SCANNED_METADATA_SQL, rows)

    def fetch_plan_records(self, *, scan_run_id: str) -> list[PlannedScanRecord]:
        rows = self._connection.execute(
            """
            SELECT
                f.id AS file_id,
                f.source_path AS source_path,
                f.source_root AS source_root,
                f.extension AS extension,
                m.artist AS artist,
                m.album_artist AS album_artist,
                m.album AS album,
                m.title AS title,
                m.track_no AS track_no,
                m.disc_no AS disc_no
            FROM scanned_files AS f
            LEFT JOIN scanned_metadata AS m ON m.file_id = f.id
            WHERE f.scan_run_id = ? AND f.file_type = 'music'
            ORDER BY f.source_path
            """,
            (scan_run_id,),
        ).fetchall()

        return [self._to_planned_scan_record(row) for row in rows]

    def fetch_companion_asset_records(
        self,
        *,
        scan_run_id: str,
        extensions: set[str],
    ) -> list[CompanionAssetRecord]:
        normalized_extensions = tuple(sorted(extension.lower() for extension in extensions))
        if not normalized_extensions:
            return []
        placeholders = ", ".join("?" for _ in normalized_extensions)
        rows = self._connection.execute(
            f"""
            SELECT
                f.id AS file_id,
                f.source_path AS source_path,
                f.extension AS extension
            FROM scanned_files AS f
            WHERE f.scan_run_id = ?
              AND f.file_type = 'unsupported'
              AND f.extension IN ({placeholders})
            ORDER BY f.source_path
            """,
            (scan_run_id, *normalized_extensions),
        ).fetchall()
        return [
            CompanionAssetRecord(
                file_id=row["file_id"],
                source_path=row["source_path"],
                extension=row["extension"],
            )
            for row in rows
        ]

    @staticmethod
    def _to_planned_scan_record(row: sqlite3.Row) -> PlannedScanRecord:
        return PlannedScanRecord(
            file_id=row["file_id"],
            source_path=row["source_path"],
            source_root=row["source_root"],
            source_stem=Path(row["source_path"]).stem,
            extension=row["extension"],
            artist=row["artist"],
            album_artist=row["album_artist"],
            album=row["album"],
            title=row["title"],
            track_no=row["track_no"],
            disc_no=row["disc_no"],
        )

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from music_folder_builder.infrastructure.metadata.reader import MetadataReadResult


@dataclass(frozen=True, slots=True)
class PlannedScanRecord:
    file_id: str
    source_path: str
    source_stem: str
    extension: str
    artist: str | None
    album_artist: str | None
    album: str | None
    title: str | None
    track_no: int | None
    disc_no: int | None


class ScanRepository:
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
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO scanned_files (
                    id, scan_run_id, source_path, source_root, extension, size_bytes,
                    mtime_utc, file_type, exclusion_reason, link_state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
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
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO scanned_metadata (
                    file_id, artist, album_artist, album, title, track_no, disc_no,
                    year, metadata_status, metadata_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
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

    def fetch_plan_records(self, *, scan_run_id: str) -> list[PlannedScanRecord]:
        rows = self._connection.execute(
            """
            SELECT
                f.id AS file_id,
                f.source_path AS source_path,
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

    @staticmethod
    def _to_planned_scan_record(row: sqlite3.Row) -> PlannedScanRecord:
        return PlannedScanRecord(
            file_id=row["file_id"],
            source_path=row["source_path"],
            source_stem=Path(row["source_path"]).stem,
            extension=row["extension"],
            artist=row["artist"],
            album_artist=row["album_artist"],
            album=row["album"],
            title=row["title"],
            track_no=row["track_no"],
            disc_no=row["disc_no"],
        )

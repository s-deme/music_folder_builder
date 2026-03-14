from __future__ import annotations

from pathlib import PureWindowsPath

from music_folder_builder.infrastructure.db.scan_repository import PlannedScanRecord


class OrganizationRules:
    def build_target_path(self, *, library_root: str, record: PlannedScanRecord) -> PureWindowsPath:
        artist = record.album_artist or record.artist or "Unknown Artist"
        album = record.album or "Unknown Album"
        title = record.title or record.source_stem or "Unknown Title"
        filename = (
            f"{record.track_no:02d}_{title}{record.extension}"
            if record.track_no is not None
            else f"{title}{record.extension}"
        )

        path = PureWindowsPath(library_root) / artist / album
        if record.disc_no is not None:
            path = path / f"{record.disc_no:02d}"
        return path / filename

from __future__ import annotations

import re
from pathlib import PureWindowsPath

from music_folder_builder.infrastructure.db.scan_repository import PlannedScanRecord


class OrganizationRules:
    _OPTIONAL_BLOCK_PATTERN = re.compile(r"\[([^\[\]]*)\]")
    _FIELD_PATTERN = re.compile(r"\{([a-z_]+)(?::([^}]+))?\}")

    def __init__(
        self,
        *,
        artist_dir_template: str = "{album_artist}",
        album_dir_template: str = "{album}",
        disc_dir_template: str = "[{disc_no:02d}]",
        filename_template: str = "[{track_no:02d}_]{title}{extension}",
    ) -> None:
        self._artist_dir_template = artist_dir_template
        self._album_dir_template = album_dir_template
        self._disc_dir_template = disc_dir_template
        self._filename_template = filename_template

    def build_target_path(self, *, library_root: str, record: PlannedScanRecord) -> PureWindowsPath:
        values = {
            "artist": record.artist or "Unknown Artist",
            "album_artist": record.album_artist or record.artist or "Unknown Artist",
            "album": record.album or "Unknown Album",
            "title": record.title or record.source_stem or "Unknown Title",
            "source_stem": record.source_stem,
            "track_no": record.track_no,
            "disc_no": record.disc_no,
            "year": None,
            "extension": record.extension,
        }

        artist_dir = self._render_template(self._artist_dir_template, values).strip() or "Unknown Artist"
        album_dir = self._render_template(self._album_dir_template, values).strip() or "Unknown Album"
        disc_dir = self._render_template(self._disc_dir_template, values).strip()
        filename = self._render_template(self._filename_template, values).strip()
        if not filename:
            filename = f"{values['title']}{record.extension}"

        path = PureWindowsPath(library_root) / artist_dir / album_dir
        if disc_dir:
            path = path / disc_dir
        return path / filename

    def _render_template(self, template: str, values: dict[str, object | None]) -> str:
        rendered = template
        while True:
            match = self._OPTIONAL_BLOCK_PATTERN.search(rendered)
            if match is None:
                break
            block_text = match.group(1)
            block_rendered, used_value = self._render_fields(block_text, values)
            replacement = block_rendered if used_value else ""
            rendered = rendered[: match.start()] + replacement + rendered[match.end() :]

        final_text, _ = self._render_fields(rendered, values)
        return final_text

    def _render_fields(self, template: str, values: dict[str, object | None]) -> tuple[str, bool]:
        used_value = False

        def replace(match: re.Match[str]) -> str:
            nonlocal used_value
            field_name = match.group(1)
            format_spec = match.group(2)
            value = values.get(field_name)
            if value in (None, ""):
                return ""
            used_value = True
            if format_spec:
                try:
                    return format(value, format_spec)
                except (TypeError, ValueError):
                    return str(value)
            return str(value)

        return self._FIELD_PATTERN.sub(replace, template), used_value

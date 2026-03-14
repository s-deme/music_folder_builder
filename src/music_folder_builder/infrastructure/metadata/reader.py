from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class MetadataReadResult:
    artist: str | None = None
    album_artist: str | None = None
    album: str | None = None
    title: str | None = None
    track_no: int | None = None
    disc_no: int | None = None
    year: int | None = None
    metadata_status: str = "missing"
    metadata_error: str | None = None


class MetadataReader:
    def read(self, path: Path) -> MetadataReadResult:
        audio = _load_mutagen_file(path)
        if audio is None:
            return MetadataReadResult(
                title=path.stem,
                metadata_status="error",
                metadata_error="unsupported_or_unreadable_file",
            )
        return self._build_result(path, getattr(audio, "tags", audio) or {})

    def _build_result(self, path: Path, tags: Any) -> MetadataReadResult:
        artist = _extract_text(tags, "artist", "TPE1")
        album_artist = _extract_text(tags, "albumartist", "TPE2")
        album = _extract_text(tags, "album", "TALB")
        title = _extract_text(tags, "title", "TIT2") or path.stem
        track_no = _extract_number(tags, "tracknumber", "TRCK")
        disc_no = _extract_number(tags, "discnumber", "TPOS")
        year = _extract_year(tags, "date", "TDRC")

        populated_count = sum(
            value is not None and value != ""
            for value in (artist, album_artist, album, title, track_no, disc_no, year)
        )
        metadata_status = "ok" if populated_count > 1 else "partial"

        return MetadataReadResult(
            artist=artist,
            album_artist=album_artist,
            album=album,
            title=title,
            track_no=track_no,
            disc_no=disc_no,
            year=year,
            metadata_status=metadata_status,
        )


def _load_mutagen_file(path: Path) -> Any:
    from mutagen import File

    return File(path)


def _extract_text(tags: Any, *keys: str) -> str | None:
    for key in keys:
        raw_value = _lookup_tag(tags, key)
        text = _normalize_tag_text(raw_value)
        if text:
            return text
    return None


def _extract_number(tags: Any, *keys: str) -> int | None:
    text = _extract_text(tags, *keys)
    if not text:
        return None
    head = text.split("/", maxsplit=1)[0].strip()
    digits = "".join(character for character in head if character.isdigit())
    return int(digits) if digits else None


def _extract_year(tags: Any, *keys: str) -> int | None:
    text = _extract_text(tags, *keys)
    if not text:
        return None
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) < 4:
        return None
    return int(digits[:4])


def _lookup_tag(tags: Any, key: str) -> Any:
    if hasattr(tags, "get"):
        return tags.get(key)
    return None


def _normalize_tag_text(raw_value: Any) -> str | None:
    if raw_value is None:
        return None
    if hasattr(raw_value, "text"):
        values = raw_value.text
    else:
        values = raw_value

    if isinstance(values, (list, tuple)):
        if not values:
            return None
        value = values[0]
    else:
        value = values

    text = str(value).strip()
    return text or None

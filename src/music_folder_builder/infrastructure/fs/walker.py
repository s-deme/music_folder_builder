from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from music_folder_builder.infrastructure.fs.file_info import FileInfo


class FileWalker:
    def __init__(
        self,
        supported_extensions: set[str] | None = None,
        *,
        follow_links: bool = False,
    ) -> None:
        self._supported_extensions = {
            extension.lower() for extension in (supported_extensions or {".flac", ".mp3", ".m4a", ".ogg"})
        }
        self._follow_links = follow_links

    def walk(self, root: str | Path) -> Iterable[FileInfo]:
        root_path = Path(root)

        for current_root, dir_names, file_names in os.walk(root_path, followlinks=self._follow_links):
            current_path = Path(current_root)

            if not self._follow_links:
                yield from self._prune_symlink_directories(current_path, dir_names)

            for file_name in sorted(file_names):
                path = current_path / file_name

                if path.is_symlink() and not self._follow_links:
                    yield FileInfo(
                        path=path,
                        extension=path.suffix.lower(),
                        file_type="ignored",
                        link_state="reparse_skipped",
                    )
                    continue

                yield FileInfo(
                    path=path,
                    extension=path.suffix.lower(),
                    file_type=self._classify_file(path),
                    link_state="normal",
                )

    def _classify_file(self, path: Path) -> str:
        if path.suffix.lower() in self._supported_extensions:
            return "music"
        return "unsupported"

    def _prune_symlink_directories(self, current_path: Path, dir_names: list[str]) -> Iterable[FileInfo]:
        symlink_directories = []
        remaining_directories = []

        for dir_name in dir_names:
            path = current_path / dir_name
            if path.is_symlink():
                symlink_directories.append(
                    FileInfo(
                        path=path,
                        extension=path.suffix.lower(),
                        file_type="ignored",
                        link_state="reparse_skipped",
                    )
                )
            else:
                remaining_directories.append(dir_name)

        dir_names[:] = remaining_directories
        return symlink_directories

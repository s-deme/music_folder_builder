from __future__ import annotations

from pathlib import Path


class FileStateGateway:
    def exists(self, path: str | Path) -> bool:
        return Path(path).exists()

    def size(self, path: str | Path) -> int:
        return Path(path).stat().st_size

from __future__ import annotations

import shutil
from pathlib import Path


class FileMutationGateway:
    def exists(self, path: str | Path) -> bool:
        return Path(path).exists()

    def move(self, source: str | Path, target: str | Path) -> None:
        target_path = Path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target_path))

    def copy(self, source: str | Path, target: str | Path) -> None:
        target_path = Path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(target_path))

    def delete(self, path: str | Path) -> None:
        Path(path).unlink()

    def size(self, path: str | Path) -> int:
        return Path(path).stat().st_size

    def same_volume(self, source: str | Path, target: str | Path) -> bool:
        source_path = Path(source)
        target_path = Path(target)

        source_anchor = source_path.anchor or source_path.parts[0]
        target_anchor = target_path.anchor or target_path.parts[0]
        return source_anchor == target_anchor

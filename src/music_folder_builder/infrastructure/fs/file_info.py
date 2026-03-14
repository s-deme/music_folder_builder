from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FileInfo:
    path: Path
    extension: str
    file_type: str
    link_state: str

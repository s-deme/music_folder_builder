from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RollbackRequest:
    db_path: Path
    execution_run_id: str
    dry_run: bool = False

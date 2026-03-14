from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ApplyRequest:
    db_path: Path
    plan_run_id: str
    dry_run: bool = False

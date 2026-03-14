from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VerifyRequest:
    db_path: Path
    execution_run_id: str | None = None
    rollback_run_id: str | None = None

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PlanRequest:
    db_path: Path
    scan_run_id: str
    library_root: Path
    use_source_image_filename: bool = False
    duplicate_suffix_template: str = ""

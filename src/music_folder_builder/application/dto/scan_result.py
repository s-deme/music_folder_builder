from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScanResult:
    scan_run_id: str
    file_count: int
    warning_count: int

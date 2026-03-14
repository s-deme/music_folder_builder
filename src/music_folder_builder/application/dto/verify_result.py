from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VerifyResult:
    verify_run_id: str
    success_count: int
    skipped_count: int
    failed_count: int
    risky_count: int

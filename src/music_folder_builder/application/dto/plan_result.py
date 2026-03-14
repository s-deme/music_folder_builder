from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlanResult:
    plan_run_id: str
    item_count: int
    conflict_count: int
    risk_count: int

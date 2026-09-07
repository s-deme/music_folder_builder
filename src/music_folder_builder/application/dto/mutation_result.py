from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MutationResult:
    performed_action: str
    result: str
    error_message: str | None = None
    deleted: bool = False
    risky: bool = False

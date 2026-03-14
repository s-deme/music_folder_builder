from __future__ import annotations

from dataclasses import dataclass
from pathlib import PureWindowsPath


@dataclass(frozen=True, slots=True)
class PathRisk:
    status: str
    reason: str | None


class PathPolicy:
    def __init__(self, *, max_component_length: int = 80, max_path_length: int = 240) -> None:
        self._max_component_length = max_component_length
        self._max_path_length = max_path_length

    def assess(self, path: PureWindowsPath) -> PathRisk:
        if any(len(component) > self._max_component_length for component in path.parts):
            return PathRisk("invalid_target", "component_too_long")

        rendered = str(path)
        if len(rendered) > self._max_path_length:
            return PathRisk("path_too_long", "path_length_exceeded")

        return PathRisk("none", None)

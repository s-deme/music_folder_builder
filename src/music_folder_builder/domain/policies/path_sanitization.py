from __future__ import annotations

from pathlib import PureWindowsPath


INVALID_WINDOWS_CHARS = '<>:"/\\|?*'
RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class PathSanitizer:
    def __init__(self, replacement: str = "_") -> None:
        self._replacement = replacement
        self._translation = str.maketrans({char: replacement for char in INVALID_WINDOWS_CHARS})

    def sanitize_component(self, component: str) -> str:
        sanitized = component.translate(self._translation).rstrip(" .")
        if not sanitized:
            sanitized = self._replacement

        if sanitized.upper() in RESERVED_WINDOWS_NAMES:
            sanitized = f"{self._replacement}{sanitized}"

        return sanitized

    def sanitize_path(self, path: PureWindowsPath) -> PureWindowsPath:
        sanitized_parts: list[str] = []

        for index, part in enumerate(path.parts):
            if index == 0 and path.anchor and part == path.anchor:
                sanitized_parts.append(part)
                continue

            sanitized_parts.append(self.sanitize_component(part))

        return PureWindowsPath(*sanitized_parts)

from __future__ import annotations

from pathlib import Path
from typing import Any

import json
import tomllib


def load_config(config_path: str | Path | None) -> dict[str, Any]:
    if not config_path:
        return {}

    path = Path(config_path)
    if not path.exists():
        return {}

    with path.open("rb") as file:
        return tomllib.load(file)


def get_command_config(config: dict[str, Any], command_name: str) -> dict[str, Any]:
    section = config.get(command_name, {})
    if isinstance(section, dict):
        return section
    return {}


def save_config(config_path: str | Path, config: dict[str, Any]) -> None:
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    for section_name, section_value in config.items():
        if not isinstance(section_value, dict):
            continue
        lines.append(f"[{section_name}]")
        for key, value in section_value.items():
            lines.append(f"{key} = {_render_toml_value(value)}")
        lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _render_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return '""'
    return json.dumps(str(value), ensure_ascii=False)

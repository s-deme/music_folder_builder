from __future__ import annotations

from pathlib import Path
from typing import Any

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

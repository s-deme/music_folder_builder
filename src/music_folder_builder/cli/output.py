from __future__ import annotations

import json
from typing import Any, TextIO


def write_output(stdout: TextIO, payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return

    stdout.write(" ".join(f"{key}={value}" for key, value in payload.items()) + "\n")

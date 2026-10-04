from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect_sqlite(database_path: str | Path) -> Iterator[sqlite3.Connection]:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            yield connection
    finally:
        connection.close()

from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLiteStore:
    """SQLite connection boundary for one Fireworks world instance."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def check(self) -> None:
        with self.connect() as connection:
            connection.execute("SELECT 1")

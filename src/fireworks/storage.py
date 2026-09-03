from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLiteStore:
    """Small SQLite boundary for Fireworks infrastructure.

    Game-world schema deliberately does not live here yet. The storage model remains
    an open design decision.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path)

    def check(self) -> None:
        with self.connect() as connection:
            connection.execute("SELECT 1")

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from .storage import SQLiteStore


def create_app(database_path: str | Path | None = None) -> FastAPI:
    path = Path(
        database_path
        if database_path is not None
        else os.environ.get("FIREWORKS_DB_PATH", "data/fireworks.sqlite3")
    )
    store = SQLiteStore(path)

    application = FastAPI(title="Project Fireworks")
    application.state.store = store

    @application.get("/health")
    def health() -> dict[str, str]:
        store.check()
        return {"status": "ok"}

    return application


app = create_app()

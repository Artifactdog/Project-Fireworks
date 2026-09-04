from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .play import GreenStarOpeningService
from .storage import SQLiteStore
from .world import EntityNotFoundError


class PlayInput(BaseModel):
    character_id: str
    text: str


def create_app(database_path: str | Path | None = None) -> FastAPI:
    path = Path(
        database_path
        if database_path is not None
        else os.environ.get("FIREWORKS_DB_PATH", "data/fireworks.sqlite3")
    )
    store = SQLiteStore(path)

    application = FastAPI(title="Project Fireworks")
    application.state.store = store
    application.state.play_service = None

    def play_service() -> GreenStarOpeningService:
        service = application.state.play_service
        if service is None:
            service = GreenStarOpeningService(store)
            application.state.play_service = service
        return service

    @application.get("/health")
    def health() -> dict[str, str]:
        store.check()
        return {"status": "ok"}

    @application.post("/play/start")
    def start_play() -> dict[str, object]:
        return play_service().start().to_mapping()

    @application.get("/play/{character_id}")
    def resume_play(character_id: str) -> dict[str, object]:
        try:
            return play_service().resume(character_id).to_mapping()
        except EntityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.post("/play/input")
    def submit_play_input(request: PlayInput) -> dict[str, object]:
        try:
            return play_service().submit(request.character_id, request.text).to_mapping()
        except EntityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return application


app = create_app()

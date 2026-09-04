from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .actions import ActionEngine
from .content.green_star import (
    GREEN_STAR_MAIN_BAR_ID,
    GREEN_STAR_RESTROOM_ID,
    OPENING_COPY,
    seed_green_star,
)
from .core_game import build_core_action_registry, build_core_type_registry
from .director import (
    ActionRef,
    DirectorActionGateway,
    DirectorActionProposal,
    DirectorActionScope,
)
from .storage import SQLiteStore
from .world import EpistemicWorldRepository, EntityNotFoundError


class OpeningPhase(StrEnum):
    APPEARANCE = "appearance"
    NAME = "name"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class PlayResponse:
    character_id: str
    phase: OpeningPhase
    text: str
    prompt: str | None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "character_id": self.character_id,
            "phase": self.phase.value,
            "text": self.text,
            "prompt": self.prompt,
        }


class DeterministicOpeningDirector:
    """Zero-cost deterministic Director for the first canonical opening slice."""

    @staticmethod
    def proposal_for(phase: OpeningPhase, player_text: str) -> DirectorActionProposal:
        text = player_text.strip()
        if not text:
            raise ValueError("Player input must not be empty.")

        if phase is OpeningPhase.APPEARANCE:
            return DirectorActionProposal(
                action_type="character.establish_appearance",
                schema_version=1,
                arguments={"description": text},
            )
        if phase is OpeningPhase.NAME:
            return DirectorActionProposal(
                action_type="character.establish_name",
                schema_version=1,
                arguments={"name": text},
            )
        raise ValueError("Character creation is already complete.")


class GreenStarOpeningService:
    """First canonical playable flow, intentionally limited to character establishment."""

    def __init__(self, store: SQLiteStore) -> None:
        self.type_registry = build_core_type_registry()
        self.action_registry = build_core_action_registry()
        self.world = EpistemicWorldRepository(store, self.type_registry)
        self.engine = ActionEngine(self.world)
        self.gateway = DirectorActionGateway(self.action_registry, self.engine)
        self.director = DeterministicOpeningDirector()
        seed_green_star(self.world)

    def start(self) -> PlayResponse:
        character = self.world.create_entity()
        self.world.set_component(character.entity_id, "core.physical", {})
        self.world.add_relation(
            "core.physical_location",
            character.entity_id,
            GREEN_STAR_MAIN_BAR_ID,
        )

        movement_scope = DirectorActionScope(
            actor_entity_id=character.entity_id,
            allowed_actions=frozenset({ActionRef("core.move", 1)}),
        )
        self.gateway.execute(
            DirectorActionProposal(
                action_type="core.move",
                schema_version=1,
                arguments={"destination_entity_id": GREEN_STAR_RESTROOM_ID},
            ),
            movement_scope,
        )

        return PlayResponse(
            character_id=character.entity_id,
            phase=OpeningPhase.APPEARANCE,
            text=OPENING_COPY.intro,
            prompt=OPENING_COPY.appearance_prompt,
        )

    def resume(self, character_id: str) -> PlayResponse:
        phase = self.phase(character_id)
        if phase is OpeningPhase.APPEARANCE:
            return PlayResponse(
                character_id=character_id,
                phase=phase,
                text="",
                prompt=OPENING_COPY.appearance_prompt,
            )
        if phase is OpeningPhase.NAME:
            appearance = self.world.component(character_id, "character.appearance")
            description = appearance.payload["description"] if appearance is not None else ""
            return PlayResponse(
                character_id=character_id,
                phase=phase,
                text=description,
                prompt=OPENING_COPY.name_prompt,
            )

        identity = self.world.component(character_id, "character.identity")
        name = identity.payload["name"] if identity is not None else ""
        return PlayResponse(
            character_id=character_id,
            phase=phase,
            text=OPENING_COPY.completion_template.format(name=name),
            prompt=None,
        )

    def submit(self, character_id: str, player_text: str) -> PlayResponse:
        phase = self.phase(character_id)
        proposal = self.director.proposal_for(phase, player_text)

        if phase is OpeningPhase.APPEARANCE:
            allowed = ActionRef("character.establish_appearance", 1)
        elif phase is OpeningPhase.NAME:
            allowed = ActionRef("character.establish_name", 1)
        else:
            raise ValueError("Character creation is already complete.")

        scope = DirectorActionScope(
            actor_entity_id=character_id,
            allowed_actions=frozenset({allowed}),
        )
        result = self.gateway.execute(proposal, scope)

        if phase is OpeningPhase.APPEARANCE:
            return PlayResponse(
                character_id=character_id,
                phase=OpeningPhase.NAME,
                text=result["description"],
                prompt=OPENING_COPY.name_prompt,
            )

        return PlayResponse(
            character_id=character_id,
            phase=OpeningPhase.COMPLETE,
            text=OPENING_COPY.completion_template.format(name=result["name"]),
            prompt=None,
        )

    def phase(self, character_id: str) -> OpeningPhase:
        if not self.world.entity_exists(character_id):
            raise EntityNotFoundError(f"Entity {character_id!r} does not exist.")
        if self.world.component(character_id, "character.appearance") is None:
            return OpeningPhase.APPEARANCE
        if self.world.component(character_id, "character.identity") is None:
            return OpeningPhase.NAME
        return OpeningPhase.COMPLETE

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .actions import (
    ActionEngine,
    ActionExecutionContext,
    ActionRegistry,
)


class DirectorProposalError(ValueError):
    """A Director proposal envelope is malformed or not allowed in the current scope."""


class DirectorActionNotAllowedError(DirectorProposalError):
    """A syntactically valid proposal is outside the engine-supplied Action scope."""


@dataclass(frozen=True, slots=True, order=True)
class ActionRef:
    type_id: str
    schema_version: int


@dataclass(frozen=True, slots=True)
class DirectorActionProposal:
    """Provider-neutral model output for one proposed Action.

    Actor identity is intentionally absent. It comes from trusted engine state.
    """

    action_type: str
    schema_version: int
    arguments: dict[str, Any]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DirectorActionProposal:
        expected = {"action_type", "schema_version", "arguments"}
        actual = set(value)
        missing = expected - actual
        extra = actual - expected
        if missing or extra:
            details: list[str] = []
            if missing:
                details.append(f"missing {sorted(missing)!r}")
            if extra:
                details.append(f"unexpected {sorted(extra)!r}")
            raise DirectorProposalError("Invalid Director Action proposal: " + "; ".join(details) + ".")

        action_type = value["action_type"]
        schema_version = value["schema_version"]
        arguments = value["arguments"]

        if not isinstance(action_type, str) or not action_type.strip():
            raise DirectorProposalError("Director Action proposal action_type must be a non-empty string.")
        if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version < 1:
            raise DirectorProposalError(
                "Director Action proposal schema_version must be a positive integer."
            )
        if not isinstance(arguments, Mapping):
            raise DirectorProposalError("Director Action proposal arguments must be a JSON object.")

        return cls(
            action_type=action_type,
            schema_version=schema_version,
            arguments=deepcopy(dict(arguments)),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "schema_version": self.schema_version,
            "arguments": deepcopy(self.arguments),
        }

    @property
    def action_ref(self) -> ActionRef:
        return ActionRef(self.action_type, self.schema_version)


@dataclass(frozen=True, slots=True)
class DirectorActionOffer:
    """One Action contract that the engine may expose to the Director for this turn."""

    action_type: str
    schema_version: int
    description: str
    arguments_schema: dict[str, Any]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "schema_version": self.schema_version,
            "description": self.description,
            "arguments_schema": deepcopy(self.arguments_schema),
        }


@dataclass(frozen=True, slots=True)
class DirectorActionScope:
    """Trusted per-request actor identity plus the exact Actions currently allowed."""

    actor_entity_id: str
    allowed_actions: frozenset[ActionRef]

    def __post_init__(self) -> None:
        if not self.actor_entity_id.strip():
            raise DirectorProposalError("Director Action scope actor Entity ID must not be empty.")

    def offers(self, registry: ActionRegistry) -> tuple[DirectorActionOffer, ...]:
        offers: list[DirectorActionOffer] = []
        for action_ref in sorted(self.allowed_actions):
            definition = registry.definition(action_ref.type_id, action_ref.schema_version)
            offers.append(
                DirectorActionOffer(
                    action_type=definition.type_id,
                    schema_version=definition.schema_version,
                    description=definition.description,
                    arguments_schema=deepcopy(dict(definition.input_schema)),
                )
            )
        return tuple(offers)


class DirectorActionGateway:
    """Validates one Director proposal and executes only an engine-allowed Action.

    This is the write-side boundary for Director-originated gameplay operations. The
    Director never receives the ActionEngine, registry factories, repository, or world
    transaction directly.
    """

    def __init__(self, registry: ActionRegistry, engine: ActionEngine) -> None:
        self.registry = registry
        self.engine = engine

    def execute(
        self,
        proposal: DirectorActionProposal,
        scope: DirectorActionScope,
    ) -> Any:
        if proposal.action_ref not in scope.allowed_actions:
            raise DirectorActionNotAllowedError(
                f"Action {proposal.action_type!r} v{proposal.schema_version} is not allowed "
                "in the current Director Action scope."
            )

        context = ActionExecutionContext(actor_entity_id=scope.actor_entity_id)
        action = self.registry.build(
            proposal.action_type,
            proposal.schema_version,
            context,
            proposal.arguments,
        )
        return self.engine.execute(action)

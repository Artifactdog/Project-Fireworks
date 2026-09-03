from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from .world.repository import WorldRepository, WorldTransaction

Result = TypeVar("Result", covariant=True)
JsonObject = Mapping[str, Any]

_ACTION_TYPE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$")


class ActionContractError(RuntimeError):
    """An Action violated the engine's atomic-history contract."""


class ActionDefinitionError(ValueError):
    """A project/module Action definition is invalid."""


class ActionNotRegisteredError(ValueError):
    """A requested Action type/version is not registered."""


class ActionPayloadError(ValueError):
    """Director-proposed Action arguments do not match the registered schema."""


class Action(Protocol[Result]):
    """A validated engine action executable inside one world transaction."""

    def execute(self, transaction: WorldTransaction) -> Result: ...


@dataclass(frozen=True, slots=True)
class ActionExecutionContext:
    """Trusted engine-owned context supplied separately from model output."""

    actor_entity_id: str

    def __post_init__(self) -> None:
        if not self.actor_entity_id.strip():
            raise ActionDefinitionError("Action actor Entity ID must not be empty.")


ActionFactory = Callable[[ActionExecutionContext, dict[str, Any]], Action[Any]]


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    """Project/module-owned declaration of one Director-proposable Action version."""

    type_id: str
    schema_version: int
    description: str
    input_schema: JsonObject
    factory: ActionFactory = field(compare=False, repr=False)


class ActionRegistry:
    """Immutable-by-key registry of project/module-owned Action definitions."""

    def __init__(self) -> None:
        self._definitions: dict[tuple[str, int], ActionDefinition] = {}

    def register(self, definition: ActionDefinition) -> None:
        if not _ACTION_TYPE_ID_PATTERN.fullmatch(definition.type_id):
            raise ActionDefinitionError(
                f"Action type ID {definition.type_id!r} must be a lowercase namespaced ID "
                "such as 'core.move'."
            )
        if definition.schema_version < 1:
            raise ActionDefinitionError("Action schema versions are positive integers starting at 1.")
        if not definition.description.strip():
            raise ActionDefinitionError("Action descriptions must not be empty.")
        if not callable(definition.factory):
            raise ActionDefinitionError("Action factory must be callable.")

        try:
            Draft202012Validator.check_schema(dict(definition.input_schema))
        except SchemaError as exc:
            raise ActionDefinitionError(
                f"Invalid JSON Schema for Action {definition.type_id!r}: {exc.message}"
            ) from exc

        key = (definition.type_id, definition.schema_version)
        if key in self._definitions:
            raise ActionDefinitionError(
                f"Action {definition.type_id!r} version {definition.schema_version} is already registered."
            )
        self._definitions[key] = definition

    def definition(self, type_id: str, schema_version: int) -> ActionDefinition:
        try:
            return self._definitions[(type_id, schema_version)]
        except KeyError as exc:
            raise ActionNotRegisteredError(
                f"Action {type_id!r} version {schema_version} is not registered."
            ) from exc

    def validate_arguments(
        self,
        type_id: str,
        schema_version: int,
        arguments: Mapping[str, Any],
    ) -> ActionDefinition:
        definition = self.definition(type_id, schema_version)
        try:
            Draft202012Validator(dict(definition.input_schema)).validate(dict(arguments))
        except ValidationError as exc:
            location = ".".join(str(part) for part in exc.absolute_path)
            suffix = f" at {location}" if location else ""
            raise ActionPayloadError(
                f"Invalid arguments for Action {type_id!r} v{schema_version}{suffix}: {exc.message}"
            ) from exc
        return definition

    def build(
        self,
        type_id: str,
        schema_version: int,
        context: ActionExecutionContext,
        arguments: Mapping[str, Any],
    ) -> Action[Any]:
        definition = self.validate_arguments(type_id, schema_version, arguments)
        action = definition.factory(context, dict(arguments))
        if not callable(getattr(action, "execute", None)):
            raise ActionDefinitionError(
                f"Factory for Action {type_id!r} v{schema_version} did not return an executable Action."
            )
        return action


class ActionEngine:
    """Runs one Action as one atomic canonical-world transaction.

    Gameplay Action schemas and Director-facing proposal semantics are registered
    separately. A state-changing Action must append at least one Event in the same
    transaction.
    """

    def __init__(self, world: WorldRepository) -> None:
        self.world = world

    def execute(self, action: Action[Result]) -> Result:
        with self.world.transaction() as transaction:
            connection = transaction._connection
            changes_before = connection.total_changes
            events_before = connection.execute("SELECT COUNT(*) AS count FROM events").fetchone()[
                "count"
            ]

            result = action.execute(transaction)

            events_after = connection.execute("SELECT COUNT(*) AS count FROM events").fetchone()[
                "count"
            ]
            event_delta = events_after - events_before
            total_delta = connection.total_changes - changes_before
            state_delta = total_delta - event_delta

            if state_delta > 0 and event_delta == 0:
                raise ActionContractError(
                    "State-changing Actions must append at least one Event in the same transaction."
                )
            return result

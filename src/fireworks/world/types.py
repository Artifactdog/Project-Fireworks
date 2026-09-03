from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

JsonObject = Mapping[str, Any]


class WorldReadView(Protocol):
    """Minimal read-only world access available to semantic validators.

    The concrete persistence implementation is deliberately hidden from validators.
    This protocol can grow only when a real validation use-case requires it.
    """

    def entity_exists(self, entity_id: str) -> bool: ...

    def has_component(self, entity_id: str, type_id: str) -> bool: ...


ComponentSemanticValidator = Callable[[WorldReadView, str, JsonObject], None]
RelationSemanticValidator = Callable[[WorldReadView, str, str, JsonObject], None]
EventSemanticValidator = Callable[[WorldReadView, JsonObject], None]
EpistemicClaimSemanticValidator = Callable[[WorldReadView, str, JsonObject], None]


class WorldTypeError(ValueError):
    """Base error for project-owned world type failures."""


class TypeDefinitionError(WorldTypeError):
    """A registered world type definition itself is invalid."""


class TypeNotRegisteredError(WorldTypeError):
    """A requested type/version is not registered in the current project."""


class TypePayloadError(WorldTypeError):
    """A payload does not conform to its registered type definition."""


@dataclass(frozen=True, slots=True)
class ComponentTypeDefinition:
    type_id: str
    schema_version: int
    schema: JsonObject
    semantic_validator: ComponentSemanticValidator | None = field(
        default=None,
        compare=False,
        repr=False,
    )


@dataclass(frozen=True, slots=True)
class RelationTypeDefinition:
    type_id: str
    schema_version: int
    payload_schema: JsonObject
    directional: bool = True
    source_requires: frozenset[str] = frozenset()
    target_requires: frozenset[str] = frozenset()
    max_from_source: int | None = None
    max_to_target: int | None = None
    semantic_validator: RelationSemanticValidator | None = field(
        default=None,
        compare=False,
        repr=False,
    )


@dataclass(frozen=True, slots=True)
class EventTypeDefinition:
    type_id: str
    schema_version: int
    schema: JsonObject
    semantic_validator: EventSemanticValidator | None = field(
        default=None,
        compare=False,
        repr=False,
    )


@dataclass(frozen=True, slots=True)
class EpistemicClaimTypeDefinition:
    """Project/module-owned schema for one kind of character belief or knowledge claim."""

    type_id: str
    schema_version: int
    schema: JsonObject
    semantic_validator: EpistemicClaimSemanticValidator | None = field(
        default=None,
        compare=False,
        repr=False,
    )

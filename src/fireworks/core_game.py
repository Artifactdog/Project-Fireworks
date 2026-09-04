from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .actions import (
    ActionDefinition,
    ActionExecutionContext,
    ActionRegistry,
)
from .world import (
    ComponentTypeDefinition,
    EventTypeDefinition,
    RelationTypeDefinition,
    TypeRegistry,
    WorldInvariantError,
    WorldTransaction,
)

EMPTY_OBJECT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
}

DISPLAY_NAME_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"name": {"type": "string", "minLength": 1}},
    "required": ["name"],
    "additionalProperties": False,
}

APPEARANCE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"description": {"type": "string", "minLength": 1}},
    "required": ["description"],
    "additionalProperties": False,
}

IDENTITY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"name": {"type": "string", "minLength": 1}},
    "required": ["name"],
    "additionalProperties": False,
}

MOVE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "destination_entity_id": {"type": "string", "minLength": 1},
    },
    "required": ["destination_entity_id"],
    "additionalProperties": False,
}

ESTABLISH_APPEARANCE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"description": {"type": "string", "minLength": 1}},
    "required": ["description"],
    "additionalProperties": False,
}

ESTABLISH_NAME_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"name": {"type": "string", "minLength": 1}},
    "required": ["name"],
    "additionalProperties": False,
}

LOCATION_CHANGED_EVENT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "entity": {"type": "string", "minLength": 1},
        "from": {"type": "string", "minLength": 1},
        "to": {"type": "string", "minLength": 1},
    },
    "required": ["entity", "from", "to"],
    "additionalProperties": False,
}

CHARACTER_APPEARANCE_EVENT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "entity": {"type": "string", "minLength": 1},
        "description": {"type": "string", "minLength": 1},
    },
    "required": ["entity", "description"],
    "additionalProperties": False,
}

CHARACTER_NAME_EVENT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "entity": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
    },
    "required": ["entity", "name"],
    "additionalProperties": False,
}


def build_core_type_registry() -> TypeRegistry:
    registry = TypeRegistry()

    registry.register_component(ComponentTypeDefinition("core.physical", 1, EMPTY_OBJECT_SCHEMA))
    registry.register_component(ComponentTypeDefinition("core.location", 1, EMPTY_OBJECT_SCHEMA))
    registry.register_component(ComponentTypeDefinition("core.display_name", 1, DISPLAY_NAME_SCHEMA))
    registry.register_component(ComponentTypeDefinition("character.appearance", 1, APPEARANCE_SCHEMA))
    registry.register_component(ComponentTypeDefinition("character.identity", 1, IDENTITY_SCHEMA))

    registry.register_relation(
        RelationTypeDefinition(
            type_id="core.physical_location",
            schema_version=1,
            payload_schema=EMPTY_OBJECT_SCHEMA,
            source_requires=frozenset({"core.physical"}),
            target_requires=frozenset({"core.location"}),
            max_from_source=1,
        )
    )
    registry.register_relation(
        RelationTypeDefinition(
            type_id="core.contains",
            schema_version=1,
            payload_schema=EMPTY_OBJECT_SCHEMA,
            source_requires=frozenset({"core.location"}),
            target_requires=frozenset({"core.location"}),
        )
    )
    registry.register_relation(
        RelationTypeDefinition(
            type_id="core.directly_reachable",
            schema_version=1,
            payload_schema=EMPTY_OBJECT_SCHEMA,
            directional=False,
            source_requires=frozenset({"core.location"}),
            target_requires=frozenset({"core.location"}),
        )
    )

    registry.register_event(
        EventTypeDefinition("core.location_changed", 1, LOCATION_CHANGED_EVENT_SCHEMA)
    )
    registry.register_event(
        EventTypeDefinition(
            "character.appearance_established",
            1,
            CHARACTER_APPEARANCE_EVENT_SCHEMA,
        )
    )
    registry.register_event(
        EventTypeDefinition("character.name_established", 1, CHARACTER_NAME_EVENT_SCHEMA)
    )

    return registry


def _current_location(transaction: WorldTransaction, actor_entity_id: str) -> str:
    locations = transaction.relations_for(actor_entity_id, "core.physical_location")
    if len(locations) != 1:
        raise WorldInvariantError(
            f"Entity {actor_entity_id!r} must have exactly one physical location to move."
        )
    relation = locations[0]
    if relation.source_entity_id != actor_entity_id:
        raise WorldInvariantError(
            f"Physical-location Relation for {actor_entity_id!r} is malformed."
        )
    return relation.target_entity_id


def _directly_reachable(
    transaction: WorldTransaction,
    source_entity_id: str,
    destination_entity_id: str,
) -> bool:
    for relation in transaction.relations_for(source_entity_id, "core.directly_reachable"):
        endpoints = {relation.source_entity_id, relation.target_entity_id}
        if endpoints == {source_entity_id, destination_entity_id}:
            return True
    return False


@dataclass(frozen=True, slots=True)
class MoveAction:
    actor_entity_id: str
    destination_entity_id: str

    def execute(self, transaction: WorldTransaction) -> str:
        source = _current_location(transaction, self.actor_entity_id)
        destination = self.destination_entity_id
        if source == destination:
            raise WorldInvariantError("The actor is already at that location.")
        if not _directly_reachable(transaction, source, destination):
            raise WorldInvariantError(
                f"Location {destination!r} is not directly reachable from {source!r}."
            )

        current = transaction.relations_for(self.actor_entity_id, "core.physical_location")[0]
        transaction.remove_relation(current.relation_id)
        transaction.add_relation(
            "core.physical_location",
            self.actor_entity_id,
            destination,
        )
        transaction.append_event(
            "core.location_changed",
            {"entity": self.actor_entity_id, "from": source, "to": destination},
        )
        return destination


@dataclass(frozen=True, slots=True)
class EstablishAppearanceAction:
    actor_entity_id: str
    description: str

    def execute(self, transaction: WorldTransaction) -> dict[str, Any]:
        if transaction.component(self.actor_entity_id, "character.appearance") is not None:
            raise WorldInvariantError("Character appearance has already been established.")
        payload = {"description": self.description.strip()}
        transaction.set_component(self.actor_entity_id, "character.appearance", payload)
        transaction.append_event(
            "character.appearance_established",
            {"entity": self.actor_entity_id, **payload},
        )
        return payload


@dataclass(frozen=True, slots=True)
class EstablishNameAction:
    actor_entity_id: str
    name: str

    def execute(self, transaction: WorldTransaction) -> dict[str, Any]:
        if transaction.component(self.actor_entity_id, "character.identity") is not None:
            raise WorldInvariantError("Character name has already been established.")
        payload = {"name": self.name.strip()}
        transaction.set_component(self.actor_entity_id, "character.identity", payload)
        transaction.append_event(
            "character.name_established",
            {"entity": self.actor_entity_id, **payload},
        )
        return payload


def build_core_action_registry() -> ActionRegistry:
    registry = ActionRegistry()

    registry.register(
        ActionDefinition(
            type_id="core.move",
            schema_version=1,
            description="Move the acting character to one directly reachable location.",
            input_schema=MOVE_SCHEMA,
            factory=lambda context, args: MoveAction(
                context.actor_entity_id,
                args["destination_entity_id"],
            ),
        )
    )
    registry.register(
        ActionDefinition(
            type_id="character.establish_appearance",
            schema_version=1,
            description="Establish the acting character's initial freeform physical appearance.",
            input_schema=ESTABLISH_APPEARANCE_SCHEMA,
            factory=lambda context, args: EstablishAppearanceAction(
                context.actor_entity_id,
                args["description"],
            ),
        )
    )
    registry.register(
        ActionDefinition(
            type_id="character.establish_name",
            schema_version=1,
            description="Establish the acting character's initial name.",
            input_schema=ESTABLISH_NAME_SCHEMA,
            factory=lambda context, args: EstablishNameAction(
                context.actor_entity_id,
                args["name"],
            ),
        )
    )

    return registry

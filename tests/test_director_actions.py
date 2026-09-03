from __future__ import annotations

from dataclasses import dataclass

import pytest

from fireworks.actions import (
    ActionDefinition,
    ActionDefinitionError,
    ActionEngine,
    ActionPayloadError,
    ActionRegistry,
)
from fireworks.director import (
    ActionRef,
    DirectorActionGateway,
    DirectorActionNotAllowedError,
    DirectorActionProposal,
    DirectorActionScope,
    DirectorProposalError,
)
from fireworks.storage import SQLiteStore
from fireworks.world import ComponentTypeDefinition, EventTypeDefinition, TypeRegistry, WorldRepository
from fireworks.world.repository import WorldTransaction

MARKER_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"label": {"type": "string", "minLength": 1}},
    "required": ["label"],
    "additionalProperties": False,
}

MARKER_EVENT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "actor": {"type": "string", "minLength": 1},
        "label": {"type": "string", "minLength": 1},
    },
    "required": ["actor", "label"],
    "additionalProperties": False,
}

ACTION_INPUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"label": {"type": "string", "minLength": 1}},
    "required": ["label"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class SetOwnMarkerAction:
    actor_entity_id: str
    label: str

    def execute(self, transaction: WorldTransaction) -> str:
        transaction.set_component(self.actor_entity_id, "test.marker", {"label": self.label})
        transaction.append_event(
            "test.marker_set",
            {"actor": self.actor_entity_id, "label": self.label},
        )
        return self.actor_entity_id


def marker_factory(context, arguments):
    return SetOwnMarkerAction(context.actor_entity_id, arguments["label"])


def make_world(path) -> WorldRepository:
    registry = TypeRegistry()
    registry.register_component(ComponentTypeDefinition("test.marker", 1, MARKER_SCHEMA))
    registry.register_event(EventTypeDefinition("test.marker_set", 1, MARKER_EVENT_SCHEMA))
    world = WorldRepository(SQLiteStore(path), registry)
    world.create_entity("player")
    world.create_entity("nadia")
    return world


def make_action_registry() -> ActionRegistry:
    registry = ActionRegistry()
    registry.register(
        ActionDefinition(
            type_id="test.set_marker",
            schema_version=1,
            description="Set a marker on the acting Entity.",
            input_schema=ACTION_INPUT_SCHEMA,
            factory=marker_factory,
        )
    )
    return registry


def test_action_definition_requires_namespaced_id_and_cannot_be_redefined() -> None:
    registry = ActionRegistry()

    with pytest.raises(ActionDefinitionError):
        registry.register(
            ActionDefinition(
                type_id="set_marker",
                schema_version=1,
                description="Invalid unnamespaced Action.",
                input_schema=ACTION_INPUT_SCHEMA,
                factory=marker_factory,
            )
        )

    definition = ActionDefinition(
        type_id="test.set_marker",
        schema_version=1,
        description="Set a marker.",
        input_schema=ACTION_INPUT_SCHEMA,
        factory=marker_factory,
    )
    registry.register(definition)

    with pytest.raises(ActionDefinitionError):
        registry.register(definition)


def test_director_proposal_envelope_cannot_supply_actor_or_extra_fields() -> None:
    with pytest.raises(DirectorProposalError):
        DirectorActionProposal.from_mapping(
            {
                "action_type": "test.set_marker",
                "schema_version": 1,
                "arguments": {"label": "hello"},
                "actor_entity_id": "nadia",
            }
        )


def test_director_proposal_requires_exact_schema_version() -> None:
    with pytest.raises(DirectorProposalError):
        DirectorActionProposal.from_mapping(
            {
                "action_type": "test.set_marker",
                "arguments": {"label": "hello"},
            }
        )


def test_scope_exposes_only_exact_engine_allowed_action_contracts() -> None:
    registry = make_action_registry()
    scope = DirectorActionScope(
        actor_entity_id="player",
        allowed_actions=frozenset({ActionRef("test.set_marker", 1)}),
    )

    offers = scope.offers(registry)

    assert len(offers) == 1
    assert offers[0].action_type == "test.set_marker"
    assert offers[0].schema_version == 1
    assert offers[0].arguments_schema == ACTION_INPUT_SCHEMA


def test_registered_action_is_still_rejected_when_not_allowed_this_turn(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    action_registry = make_action_registry()
    gateway = DirectorActionGateway(action_registry, ActionEngine(world))
    proposal = DirectorActionProposal.from_mapping(
        {
            "action_type": "test.set_marker",
            "schema_version": 1,
            "arguments": {"label": "hello"},
        }
    )
    scope = DirectorActionScope(actor_entity_id="player", allowed_actions=frozenset())

    with pytest.raises(DirectorActionNotAllowedError):
        gateway.execute(proposal, scope)

    assert world.component("player", "test.marker") is None
    assert world.events_after() == []


def test_invalid_arguments_are_rejected_before_world_mutation(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    action_registry = make_action_registry()
    gateway = DirectorActionGateway(action_registry, ActionEngine(world))
    proposal = DirectorActionProposal.from_mapping(
        {
            "action_type": "test.set_marker",
            "schema_version": 1,
            "arguments": {"label": "hello", "actor": "nadia"},
        }
    )
    scope = DirectorActionScope(
        actor_entity_id="player",
        allowed_actions=frozenset({ActionRef("test.set_marker", 1)}),
    )

    with pytest.raises(ActionPayloadError):
        gateway.execute(proposal, scope)

    assert world.component("player", "test.marker") is None
    assert world.component("nadia", "test.marker") is None
    assert world.events_after() == []


def test_gateway_injects_trusted_actor_and_executes_atomically(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    action_registry = make_action_registry()
    gateway = DirectorActionGateway(action_registry, ActionEngine(world))
    proposal = DirectorActionProposal.from_mapping(
        {
            "action_type": "test.set_marker",
            "schema_version": 1,
            "arguments": {"label": "hello"},
        }
    )
    scope = DirectorActionScope(
        actor_entity_id="player",
        allowed_actions=frozenset({ActionRef("test.set_marker", 1)}),
    )

    result = gateway.execute(proposal, scope)

    assert result == "player"
    assert world.component("player", "test.marker").payload == {"label": "hello"}
    assert world.component("nadia", "test.marker") is None
    events = world.events_after()
    assert len(events) == 1
    assert events[0].payload == {"actor": "player", "label": "hello"}

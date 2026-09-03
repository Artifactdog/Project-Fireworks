from dataclasses import dataclass

import pytest

from fireworks.actions import ActionEngine
from fireworks.storage import SQLiteStore
from fireworks.world import (
    ComponentTypeDefinition,
    EventTypeDefinition,
    RelationTypeDefinition,
    TypePayloadError,
    TypeRegistry,
    WorldRepository,
    WorldTransaction,
)

EMPTY_OBJECT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
}

LOCATION_CHANGED_SCHEMA = {
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


def make_registry() -> TypeRegistry:
    registry = TypeRegistry()
    registry.register_component(ComponentTypeDefinition("core.physical", 1, EMPTY_OBJECT_SCHEMA))
    registry.register_component(ComponentTypeDefinition("core.location", 1, EMPTY_OBJECT_SCHEMA))
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
    registry.register_event(
        EventTypeDefinition(
            type_id="core.location_changed",
            schema_version=1,
            schema=LOCATION_CHANGED_SCHEMA,
        )
    )
    return registry


def make_world(path) -> WorldRepository:
    return WorldRepository(SQLiteStore(path), make_registry())


def seed_locations(world: WorldRepository):
    for entity_id in ("nadia", "bar", "apartment"):
        world.create_entity(entity_id)
    world.set_component("nadia", "core.physical", {})
    world.set_component("bar", "core.location", {})
    world.set_component("apartment", "core.location", {})
    return world.add_relation("core.physical_location", "nadia", "bar")


def test_events_have_monotonic_world_local_sequence(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")

    with world.transaction() as transaction:
        first = transaction.append_event(
            "core.location_changed",
            {"entity": "nadia", "from": "bar", "to": "apartment"},
        )
        second = transaction.append_event(
            "core.location_changed",
            {"entity": "nadia", "from": "apartment", "to": "bar"},
        )

    assert first.sequence == 1
    assert second.sequence == 2
    assert [event.sequence for event in world.events_after()] == [1, 2]


def test_invalid_event_payload_is_rejected_before_persistence(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")

    with pytest.raises(TypePayloadError):
        with world.transaction() as transaction:
            transaction.append_event(
                "core.location_changed",
                {"entity": "nadia", "from": "bar"},
            )

    assert world.events_after() == []


def test_state_and_event_roll_back_together(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    original = seed_locations(world)

    with pytest.raises(RuntimeError):
        with world.transaction() as transaction:
            assert transaction.remove_relation(original.relation_id)
            transaction.add_relation("core.physical_location", "nadia", "apartment")
            transaction.append_event(
                "core.location_changed",
                {"entity": "nadia", "from": "bar", "to": "apartment"},
            )
            raise RuntimeError("simulated failure")

    locations = world.relations_for("nadia", "core.physical_location")
    assert len(locations) == 1
    assert locations[0].target_entity_id == "bar"
    assert world.events_after() == []


@dataclass(frozen=True)
class MoveAction:
    destination: str

    def execute(self, transaction: WorldTransaction) -> str:
        current = transaction.relations_for("nadia", "core.physical_location")
        assert len(current) == 1
        previous = current[0]
        transaction.remove_relation(previous.relation_id)
        transaction.add_relation("core.physical_location", "nadia", self.destination)
        transaction.append_event(
            "core.location_changed",
            {"entity": "nadia", "from": previous.target_entity_id, "to": self.destination},
        )
        return self.destination


def test_action_engine_commits_state_and_event_atomically(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    seed_locations(world)

    result = ActionEngine(world).execute(MoveAction("apartment"))

    assert result == "apartment"
    locations = world.relations_for("nadia", "core.physical_location")
    assert len(locations) == 1
    assert locations[0].target_entity_id == "apartment"
    events = world.events_after()
    assert len(events) == 1
    assert events[0].payload == {
        "entity": "nadia",
        "from": "bar",
        "to": "apartment",
    }


@dataclass(frozen=True)
class BrokenMoveAction:
    destination: str

    def execute(self, transaction: WorldTransaction) -> None:
        current = transaction.relations_for("nadia", "core.physical_location")
        transaction.remove_relation(current[0].relation_id)
        transaction.add_relation("core.physical_location", "nadia", self.destination)
        transaction.append_event(
            "core.location_changed",
            {"entity": "nadia", "from": current[0].target_entity_id, "to": self.destination},
        )
        raise RuntimeError("handler failed")


def test_action_engine_rolls_back_failed_handler(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    seed_locations(world)

    with pytest.raises(RuntimeError):
        ActionEngine(world).execute(BrokenMoveAction("apartment"))

    assert world.relations_for("nadia", "core.physical_location")[0].target_entity_id == "bar"
    assert world.events_after() == []


def test_storage_revision_one_migrates_to_events_without_losing_entities(tmp_path) -> None:
    path = tmp_path / "world.sqlite3"
    store = SQLiteStore(path)
    with store.connect() as connection:
        connection.execute(
            "CREATE TABLE fireworks_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO fireworks_meta(key, value) VALUES ('storage_schema_version', '1')"
        )
        connection.execute(
            "CREATE TABLE entities (id TEXT PRIMARY KEY, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO entities(id, created_at) VALUES ('nadia', '2026-09-03T00:00:00+00:00')"
        )

    world = WorldRepository(store, make_registry())

    assert world.entity("nadia").entity_id == "nadia"
    with store.connect() as connection:
        version = connection.execute(
            "SELECT value FROM fireworks_meta WHERE key = 'storage_schema_version'"
        ).fetchone()["value"]
        events_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'events'"
        ).fetchone()
    assert version == "2"
    assert events_table is not None

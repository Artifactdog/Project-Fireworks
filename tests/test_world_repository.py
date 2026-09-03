from concurrent.futures import ThreadPoolExecutor

import pytest

from fireworks.storage import SQLiteStore
from fireworks.world import ComponentTypeDefinition, RelationTypeDefinition, TypeRegistry
from fireworks.world.repository import (
    EntityNotFoundError,
    StorageSchemaError,
    WorldInvariantError,
    WorldRepository,
)

EMPTY_OBJECT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
}

IDENTITY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"name": {"type": "string", "minLength": 1}},
    "required": ["name"],
    "additionalProperties": False,
}


def make_registry() -> TypeRegistry:
    registry = TypeRegistry()
    registry.register_component(
        ComponentTypeDefinition("person.identity", 1, IDENTITY_SCHEMA)
    )
    registry.register_component(
        ComponentTypeDefinition("core.physical", 1, EMPTY_OBJECT_SCHEMA)
    )
    registry.register_component(
        ComponentTypeDefinition("core.location", 1, EMPTY_OBJECT_SCHEMA)
    )
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
            type_id="core.owns",
            schema_version=1,
            payload_schema=EMPTY_OBJECT_SCHEMA,
            max_to_target=1,
        )
    )
    return registry


def make_world(path) -> WorldRepository:
    return WorldRepository(SQLiteStore(path), make_registry())


def test_entities_and_singleton_components_persist_after_reopen(tmp_path) -> None:
    database_path = tmp_path / "world.sqlite3"
    world = make_world(database_path)
    nadia = world.create_entity("nadia")

    world.set_component(nadia.entity_id, "person.identity", {"name": "Nadia"})
    world.set_component(nadia.entity_id, "person.identity", {"name": "Nadia Keller"})

    reopened = make_world(database_path)

    assert reopened.entity("nadia").entity_id == "nadia"
    component = reopened.component("nadia", "person.identity")
    assert component is not None
    assert component.payload == {"name": "Nadia Keller"}


def test_separate_database_files_are_separate_world_instances(tmp_path) -> None:
    live = make_world(tmp_path / "live.sqlite3")
    staging = make_world(tmp_path / "staging.sqlite3")

    live.create_entity("nadia")

    assert live.entity_exists("nadia")
    assert not staging.entity_exists("nadia")


def test_physical_location_requires_valid_endpoint_components(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    world.create_entity("nadia")
    world.create_entity("bar")

    with pytest.raises(WorldInvariantError):
        world.add_relation("core.physical_location", "nadia", "bar")

    world.set_component("nadia", "core.physical", {})
    world.set_component("bar", "core.location", {})

    relation = world.add_relation("core.physical_location", "nadia", "bar")
    assert relation.source_entity_id == "nadia"
    assert relation.target_entity_id == "bar"


def test_entity_cannot_have_two_exclusive_physical_locations(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    for entity_id in ("nadia", "bar", "apartment"):
        world.create_entity(entity_id)

    world.set_component("nadia", "core.physical", {})
    world.set_component("bar", "core.location", {})
    world.set_component("apartment", "core.location", {})

    first = world.add_relation("core.physical_location", "nadia", "bar")

    with pytest.raises(WorldInvariantError):
        world.add_relation("core.physical_location", "nadia", "apartment")

    assert world.remove_relation(first.relation_id)
    second = world.add_relation("core.physical_location", "nadia", "apartment")
    assert second.target_entity_id == "apartment"


def test_unique_entity_cannot_have_two_exclusive_owners(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    for entity_id in ("nadia", "alex", "gun"):
        world.create_entity(entity_id)

    world.add_relation("core.owns", "nadia", "gun")

    with pytest.raises(WorldInvariantError):
        world.add_relation("core.owns", "alex", "gun")


def test_concurrent_location_writes_cannot_both_pass_exclusivity(tmp_path) -> None:
    database_path = tmp_path / "world.sqlite3"
    world = make_world(database_path)
    for entity_id in ("nadia", "bar", "apartment"):
        world.create_entity(entity_id)

    world.set_component("nadia", "core.physical", {})
    world.set_component("bar", "core.location", {})
    world.set_component("apartment", "core.location", {})

    def attempt(target: str) -> str:
        try:
            world.add_relation("core.physical_location", "nadia", target)
        except WorldInvariantError:
            return "rejected"
        return "accepted"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, ("bar", "apartment")))

    assert sorted(results) == ["accepted", "rejected"]
    assert len(world.relations_for("nadia", "core.physical_location")) == 1


def test_relations_require_existing_entities(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    world.create_entity("nadia")

    with pytest.raises(EntityNotFoundError):
        world.add_relation("core.owns", "nadia", "missing-gun")


def test_unknown_storage_schema_revision_is_rejected(tmp_path) -> None:
    database_path = tmp_path / "world.sqlite3"
    world = make_world(database_path)

    with world.store.connect() as connection:
        connection.execute(
            "UPDATE fireworks_meta SET value = '999' WHERE key = 'storage_schema_version'"
        )

    with pytest.raises(StorageSchemaError):
        make_world(database_path)

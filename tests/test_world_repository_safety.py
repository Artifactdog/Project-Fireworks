import sqlite3

import pytest

from fireworks.storage import SQLiteStore
from fireworks.world import (
    ComponentTypeDefinition,
    RelationTypeDefinition,
    TypePayloadError,
    TypeRegistry,
)
from fireworks.world.repository import StorageSchemaError, WorldRepository, WorldStateError

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
    registry.register_relation(
        RelationTypeDefinition("core.owns", 1, EMPTY_OBJECT_SCHEMA)
    )
    return registry


def test_explicit_empty_record_ids_are_rejected(tmp_path) -> None:
    world = WorldRepository(SQLiteStore(tmp_path / "world.sqlite3"), make_registry())

    with pytest.raises(WorldStateError):
        world.create_entity("")

    world.create_entity("owner")
    world.create_entity("item")

    with pytest.raises(WorldStateError):
        world.add_relation("core.owns", "owner", "item", relation_id="")


def test_corrupt_stored_component_is_rejected_on_read(tmp_path) -> None:
    world = WorldRepository(SQLiteStore(tmp_path / "world.sqlite3"), make_registry())
    world.create_entity("nadia")
    world.set_component("nadia", "person.identity", {"name": "Nadia"})

    with world.store.connect() as connection:
        connection.execute(
            "UPDATE components SET payload_json = ? WHERE entity_id = ? AND type_id = ?",
            ('{"invented_by_corruption":true}', "nadia", "person.identity"),
        )

    with pytest.raises(TypePayloadError):
        world.component("nadia", "person.identity")

    with pytest.raises(TypePayloadError):
        world.has_component("nadia", "person.identity")


def test_future_storage_revision_is_rejected_before_world_tables_are_created(tmp_path) -> None:
    database_path = tmp_path / "future.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE fireworks_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO fireworks_meta(key, value) VALUES ('storage_schema_version', '999')"
        )

    with pytest.raises(StorageSchemaError):
        WorldRepository(SQLiteStore(database_path), make_registry())

    with sqlite3.connect(database_path) as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'entities'"
        ).fetchone()
    assert table is None


def test_unversioned_world_tables_are_not_silently_adopted(tmp_path) -> None:
    database_path = tmp_path / "unversioned.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE entities (id TEXT PRIMARY KEY)")

    with pytest.raises(StorageSchemaError):
        WorldRepository(SQLiteStore(database_path), make_registry())

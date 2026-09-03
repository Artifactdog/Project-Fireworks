from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fireworks.storage import SQLiteStore

from .registry import TypeRegistry
from .types import RelationTypeDefinition, WorldReadView

_STORAGE_SCHEMA_VERSION = 1


class WorldStateError(ValueError):
    """Base error for canonical world-state operations."""


class StorageSchemaError(WorldStateError):
    """The SQLite world store uses an unsupported internal schema revision."""


class EntityNotFoundError(WorldStateError):
    """A requested Entity does not exist in this world instance."""


class EntityAlreadyExistsError(WorldStateError):
    """An Entity ID already exists in this world instance."""


class WorldInvariantError(WorldStateError):
    """A proposed mutation would violate a registered world invariant."""


@dataclass(frozen=True, slots=True)
class EntityRecord:
    entity_id: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ComponentRecord:
    entity_id: str
    type_id: str
    schema_version: int
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RelationRecord:
    relation_id: str
    type_id: str
    schema_version: int
    source_entity_id: str
    target_entity_id: str
    payload: dict[str, Any]
    created_at: str


class _ConnectionReadView(WorldReadView):
    """Read-only validator view bound to the mutation's SQLite transaction."""

    def __init__(self, connection: sqlite3.Connection, registry: TypeRegistry) -> None:
        self._connection = connection
        self._registry = registry

    def entity_exists(self, entity_id: str) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM entities WHERE id = ?",
                (entity_id,),
            ).fetchone()
            is not None
        )

    def has_component(self, entity_id: str, type_id: str) -> bool:
        row = self._connection.execute(
            """
            SELECT schema_version, payload_json
            FROM components
            WHERE entity_id = ? AND type_id = ?
            """,
            (entity_id, type_id),
        ).fetchone()
        if row is None:
            return False
        self._registry.validate_component_payload(
            type_id,
            json.loads(row["payload_json"]),
            row["schema_version"],
        )
        return True


class WorldRepository(WorldReadView):
    """Validated persistent current-state store for one Fireworks world instance.

    This is a low-level engine boundary. Runtime AI and players must not receive this
    repository as a direct arbitrary-write tool.
    """

    def __init__(self, store: SQLiteStore, registry: TypeRegistry) -> None:
        self.store = store
        self.registry = registry
        self._initialize()

    def _initialize(self) -> None:
        with self.store.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS fireworks_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

            row = connection.execute(
                "SELECT value FROM fireworks_meta WHERE key = 'storage_schema_version'"
            ).fetchone()
            if row is None:
                unversioned_world_table = connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table' AND name IN ('entities', 'components', 'relations')
                    LIMIT 1
                    """
                ).fetchone()
                if unversioned_world_table is not None:
                    raise StorageSchemaError(
                        "World database contains unversioned canonical-state tables and cannot be adopted safely."
                    )
                connection.execute(
                    "INSERT INTO fireworks_meta(key, value) VALUES ('storage_schema_version', ?)",
                    (str(_STORAGE_SCHEMA_VERSION),),
                )
            elif row["value"] != str(_STORAGE_SCHEMA_VERSION):
                raise StorageSchemaError(
                    "World database storage schema revision "
                    f"{row['value']} is not supported by this build; expected {_STORAGE_SCHEMA_VERSION}."
                )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS components (
                    entity_id TEXT NOT NULL,
                    type_id TEXT NOT NULL,
                    schema_version INTEGER NOT NULL CHECK (schema_version >= 1),
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (entity_id, type_id),
                    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS relations (
                    id TEXT PRIMARY KEY,
                    type_id TEXT NOT NULL,
                    schema_version INTEGER NOT NULL CHECK (schema_version >= 1),
                    source_entity_id TEXT NOT NULL,
                    target_entity_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (source_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_entity_id) REFERENCES entities(id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_components_type ON components(type_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_relations_type_source ON relations(type_id, source_entity_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_relations_type_target ON relations(type_id, target_entity_id)"
            )

    def entity_exists(self, entity_id: str) -> bool:
        with self.store.connect() as connection:
            return _ConnectionReadView(connection, self.registry).entity_exists(entity_id)

    def has_component(self, entity_id: str, type_id: str) -> bool:
        with self.store.connect() as connection:
            return _ConnectionReadView(connection, self.registry).has_component(entity_id, type_id)

    def create_entity(self, entity_id: str | None = None) -> EntityRecord:
        resolved_id = str(uuid4()) if entity_id is None else entity_id
        if not resolved_id.strip():
            raise WorldStateError("Entity IDs must not be empty.")

        created_at = _utc_now()
        try:
            with self.store.connect() as connection:
                connection.execute(
                    "INSERT INTO entities(id, created_at) VALUES (?, ?)",
                    (resolved_id, created_at),
                )
        except sqlite3.IntegrityError as exc:
            raise EntityAlreadyExistsError(f"Entity {resolved_id!r} already exists.") from exc

        return EntityRecord(entity_id=resolved_id, created_at=created_at)

    def entity(self, entity_id: str) -> EntityRecord:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT id, created_at FROM entities WHERE id = ?",
                (entity_id,),
            ).fetchone()
        if row is None:
            raise EntityNotFoundError(f"Entity {entity_id!r} does not exist.")
        return EntityRecord(entity_id=row["id"], created_at=row["created_at"])

    def set_component(
        self,
        entity_id: str,
        type_id: str,
        payload: Mapping[str, Any],
        *,
        schema_version: int | None = None,
    ) -> ComponentRecord:
        definition = self.registry.validate_component_payload(
            type_id,
            payload,
            schema_version,
        )
        payload_json = _encode_payload(payload)

        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            view = _ConnectionReadView(connection, self.registry)
            self._require_entity(view, entity_id)

            if definition.semantic_validator is not None:
                definition.semantic_validator(view, entity_id, dict(payload))

            connection.execute(
                """
                INSERT INTO components(entity_id, type_id, schema_version, payload_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(entity_id, type_id) DO UPDATE SET
                    schema_version = excluded.schema_version,
                    payload_json = excluded.payload_json
                """,
                (entity_id, type_id, definition.schema_version, payload_json),
            )

        return ComponentRecord(
            entity_id=entity_id,
            type_id=type_id,
            schema_version=definition.schema_version,
            payload=dict(payload),
        )

    def component(self, entity_id: str, type_id: str) -> ComponentRecord | None:
        with self.store.connect() as connection:
            row = connection.execute(
                """
                SELECT entity_id, type_id, schema_version, payload_json
                FROM components
                WHERE entity_id = ? AND type_id = ?
                """,
                (entity_id, type_id),
            ).fetchone()
        if row is None:
            return None
        record = _component_from_row(row)
        self.registry.validate_component_payload(
            record.type_id,
            record.payload,
            record.schema_version,
        )
        return record

    def add_relation(
        self,
        type_id: str,
        source_entity_id: str,
        target_entity_id: str,
        payload: Mapping[str, Any] | None = None,
        *,
        schema_version: int | None = None,
        relation_id: str | None = None,
    ) -> RelationRecord:
        resolved_payload = dict(payload or {})
        definition = self.registry.validate_relation_payload(
            type_id,
            resolved_payload,
            schema_version,
        )
        payload_json = _encode_payload(resolved_payload)
        resolved_relation_id = str(uuid4()) if relation_id is None else relation_id
        if not resolved_relation_id.strip():
            raise WorldStateError("Relation record IDs must not be empty.")
        created_at = _utc_now()

        source = source_entity_id
        target = target_entity_id
        if not definition.directional and target < source:
            source, target = target, source

        try:
            with self.store.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                view = _ConnectionReadView(connection, self.registry)
                self._require_entity(view, source)
                self._require_entity(view, target)
                self._validate_relation_endpoints(view, definition, source, target)
                self._validate_relation_cardinality(connection, definition, source, target)

                if definition.semantic_validator is not None:
                    definition.semantic_validator(view, source, target, resolved_payload)

                connection.execute(
                    """
                    INSERT INTO relations(
                        id,
                        type_id,
                        schema_version,
                        source_entity_id,
                        target_entity_id,
                        payload_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        resolved_relation_id,
                        type_id,
                        definition.schema_version,
                        source,
                        target,
                        payload_json,
                        created_at,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise WorldInvariantError(
                f"Relation ID {resolved_relation_id!r} already exists or violates database integrity."
            ) from exc

        return RelationRecord(
            relation_id=resolved_relation_id,
            type_id=type_id,
            schema_version=definition.schema_version,
            source_entity_id=source,
            target_entity_id=target,
            payload=resolved_payload,
            created_at=created_at,
        )

    def relation(self, relation_id: str) -> RelationRecord | None:
        with self.store.connect() as connection:
            row = connection.execute(
                """
                SELECT id, type_id, schema_version, source_entity_id,
                       target_entity_id, payload_json, created_at
                FROM relations
                WHERE id = ?
                """,
                (relation_id,),
            ).fetchone()
        if row is None:
            return None
        record = _relation_from_row(row)
        self.registry.validate_relation_payload(
            record.type_id,
            record.payload,
            record.schema_version,
        )
        return record

    def relations_for(self, entity_id: str, type_id: str | None = None) -> list[RelationRecord]:
        with self.store.connect() as connection:
            if type_id is None:
                rows = connection.execute(
                    """
                    SELECT id, type_id, schema_version, source_entity_id,
                           target_entity_id, payload_json, created_at
                    FROM relations
                    WHERE source_entity_id = ? OR target_entity_id = ?
                    ORDER BY created_at, id
                    """,
                    (entity_id, entity_id),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id, type_id, schema_version, source_entity_id,
                           target_entity_id, payload_json, created_at
                    FROM relations
                    WHERE type_id = ? AND (source_entity_id = ? OR target_entity_id = ?)
                    ORDER BY created_at, id
                    """,
                    (type_id, entity_id, entity_id),
                ).fetchall()

        records = [_relation_from_row(row) for row in rows]
        for record in records:
            self.registry.validate_relation_payload(
                record.type_id,
                record.payload,
                record.schema_version,
            )
        return records

    def remove_relation(self, relation_id: str) -> bool:
        with self.store.connect() as connection:
            cursor = connection.execute("DELETE FROM relations WHERE id = ?", (relation_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _require_entity(view: WorldReadView, entity_id: str) -> None:
        if not view.entity_exists(entity_id):
            raise EntityNotFoundError(f"Entity {entity_id!r} does not exist.")

    @staticmethod
    def _validate_relation_endpoints(
        view: WorldReadView,
        definition: RelationTypeDefinition,
        source: str,
        target: str,
    ) -> None:
        for required_type in definition.source_requires:
            if not view.has_component(source, required_type):
                raise WorldInvariantError(
                    f"Source Entity {source!r} requires Component {required_type!r} "
                    f"for Relation {definition.type_id!r}."
                )
        for required_type in definition.target_requires:
            if not view.has_component(target, required_type):
                raise WorldInvariantError(
                    f"Target Entity {target!r} requires Component {required_type!r} "
                    f"for Relation {definition.type_id!r}."
                )

    @staticmethod
    def _validate_relation_cardinality(
        connection: sqlite3.Connection,
        definition: RelationTypeDefinition,
        source: str,
        target: str,
    ) -> None:
        if definition.directional:
            if definition.max_from_source is not None:
                count = connection.execute(
                    "SELECT COUNT(*) AS count FROM relations WHERE type_id = ? AND source_entity_id = ?",
                    (definition.type_id, source),
                ).fetchone()["count"]
                if count >= definition.max_from_source:
                    raise WorldInvariantError(
                        f"Relation {definition.type_id!r} allows at most "
                        f"{definition.max_from_source} outgoing relation(s) from {source!r}."
                    )

            if definition.max_to_target is not None:
                count = connection.execute(
                    "SELECT COUNT(*) AS count FROM relations WHERE type_id = ? AND target_entity_id = ?",
                    (definition.type_id, target),
                ).fetchone()["count"]
                if count >= definition.max_to_target:
                    raise WorldInvariantError(
                        f"Relation {definition.type_id!r} allows at most "
                        f"{definition.max_to_target} incoming relation(s) to {target!r}."
                    )
            return

        limit = definition.max_from_source
        if limit is None:
            return

        for endpoint in {source, target}:
            count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM relations
                WHERE type_id = ? AND (source_entity_id = ? OR target_entity_id = ?)
                """,
                (definition.type_id, endpoint, endpoint),
            ).fetchone()["count"]
            if count >= limit:
                raise WorldInvariantError(
                    f"Relation {definition.type_id!r} allows at most {limit} relation(s) "
                    f"for endpoint {endpoint!r}."
                )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _encode_payload(payload: Mapping[str, Any]) -> str:
    try:
        return json.dumps(dict(payload), separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise WorldStateError("World payloads must be JSON-serializable.") from exc


def _component_from_row(row: sqlite3.Row) -> ComponentRecord:
    return ComponentRecord(
        entity_id=row["entity_id"],
        type_id=row["type_id"],
        schema_version=row["schema_version"],
        payload=json.loads(row["payload_json"]),
    )


def _relation_from_row(row: sqlite3.Row) -> RelationRecord:
    return RelationRecord(
        relation_id=row["id"],
        type_id=row["type_id"],
        schema_version=row["schema_version"],
        source_entity_id=row["source_entity_id"],
        target_entity_id=row["target_entity_id"],
        payload=json.loads(row["payload_json"]),
        created_at=row["created_at"],
    )

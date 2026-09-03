from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fireworks.storage import SQLiteStore

from .registry import TypeRegistry
from .types import RelationTypeDefinition, WorldReadView

_STORAGE_SCHEMA_VERSION = 2


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


@dataclass(frozen=True, slots=True)
class EventRecord:
    sequence: int
    event_id: str
    type_id: str
    schema_version: int
    payload: dict[str, Any]
    recorded_at_utc: str


class _ConnectionReadView(WorldReadView):
    """Read-only validator view bound to one SQLite connection."""

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


class WorldTransaction(WorldReadView):
    """One all-or-nothing canonical world mutation transaction."""

    def __init__(self, connection: sqlite3.Connection, registry: TypeRegistry) -> None:
        self._connection = connection
        self.registry = registry
        self._view = _ConnectionReadView(connection, registry)

    def entity_exists(self, entity_id: str) -> bool:
        return self._view.entity_exists(entity_id)

    def has_component(self, entity_id: str, type_id: str) -> bool:
        return self._view.has_component(entity_id, type_id)

    def create_entity(self, entity_id: str | None = None) -> EntityRecord:
        resolved_id = str(uuid4()) if entity_id is None else entity_id
        if not resolved_id.strip():
            raise WorldStateError("Entity IDs must not be empty.")

        created_at = _utc_now()
        try:
            self._connection.execute(
                "INSERT INTO entities(id, created_at) VALUES (?, ?)",
                (resolved_id, created_at),
            )
        except sqlite3.IntegrityError as exc:
            raise EntityAlreadyExistsError(f"Entity {resolved_id!r} already exists.") from exc

        return EntityRecord(entity_id=resolved_id, created_at=created_at)

    def entity(self, entity_id: str) -> EntityRecord:
        row = self._connection.execute(
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
        definition = self.registry.validate_component_payload(type_id, payload, schema_version)
        self._require_entity(entity_id)

        if definition.semantic_validator is not None:
            definition.semantic_validator(self, entity_id, dict(payload))

        self._connection.execute(
            """
            INSERT INTO components(entity_id, type_id, schema_version, payload_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(entity_id, type_id) DO UPDATE SET
                schema_version = excluded.schema_version,
                payload_json = excluded.payload_json
            """,
            (entity_id, type_id, definition.schema_version, _encode_payload(payload)),
        )

        return ComponentRecord(
            entity_id=entity_id,
            type_id=type_id,
            schema_version=definition.schema_version,
            payload=dict(payload),
        )

    def component(self, entity_id: str, type_id: str) -> ComponentRecord | None:
        row = self._connection.execute(
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
        self.registry.validate_component_payload(record.type_id, record.payload, record.schema_version)
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
        definition = self.registry.validate_relation_payload(type_id, resolved_payload, schema_version)
        resolved_relation_id = str(uuid4()) if relation_id is None else relation_id
        if not resolved_relation_id.strip():
            raise WorldStateError("Relation record IDs must not be empty.")

        source = source_entity_id
        target = target_entity_id
        if not definition.directional and target < source:
            source, target = target, source

        self._require_entity(source)
        self._require_entity(target)
        self._validate_relation_endpoints(definition, source, target)
        self._validate_relation_cardinality(definition, source, target)

        if definition.semantic_validator is not None:
            definition.semantic_validator(self, source, target, resolved_payload)

        created_at = _utc_now()
        try:
            self._connection.execute(
                """
                INSERT INTO relations(
                    id, type_id, schema_version, source_entity_id,
                    target_entity_id, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_relation_id,
                    type_id,
                    definition.schema_version,
                    source,
                    target,
                    _encode_payload(resolved_payload),
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
        row = self._connection.execute(
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
        self.registry.validate_relation_payload(record.type_id, record.payload, record.schema_version)
        return record

    def relations_for(self, entity_id: str, type_id: str | None = None) -> list[RelationRecord]:
        if type_id is None:
            rows = self._connection.execute(
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
            rows = self._connection.execute(
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
            self.registry.validate_relation_payload(record.type_id, record.payload, record.schema_version)
        return records

    def remove_relation(self, relation_id: str) -> bool:
        cursor = self._connection.execute("DELETE FROM relations WHERE id = ?", (relation_id,))
        return cursor.rowcount > 0

    def append_event(
        self,
        type_id: str,
        payload: Mapping[str, Any],
        *,
        schema_version: int | None = None,
        event_id: str | None = None,
    ) -> EventRecord:
        definition = self.registry.validate_event_payload(type_id, payload, schema_version)
        resolved_event_id = str(uuid4()) if event_id is None else event_id
        if not resolved_event_id.strip():
            raise WorldStateError("Event IDs must not be empty.")

        if definition.semantic_validator is not None:
            definition.semantic_validator(self, dict(payload))

        recorded_at_utc = _utc_now()
        try:
            cursor = self._connection.execute(
                """
                INSERT INTO events(id, type_id, schema_version, payload_json, recorded_at_utc)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    resolved_event_id,
                    type_id,
                    definition.schema_version,
                    _encode_payload(payload),
                    recorded_at_utc,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise WorldInvariantError(
                f"Event ID {resolved_event_id!r} already exists or violates database integrity."
            ) from exc

        return EventRecord(
            sequence=int(cursor.lastrowid),
            event_id=resolved_event_id,
            type_id=type_id,
            schema_version=definition.schema_version,
            payload=dict(payload),
            recorded_at_utc=recorded_at_utc,
        )

    def _require_entity(self, entity_id: str) -> None:
        if not self.entity_exists(entity_id):
            raise EntityNotFoundError(f"Entity {entity_id!r} does not exist.")

    def _validate_relation_endpoints(
        self,
        definition: RelationTypeDefinition,
        source: str,
        target: str,
    ) -> None:
        for required_type in definition.source_requires:
            if not self.has_component(source, required_type):
                raise WorldInvariantError(
                    f"Source Entity {source!r} requires Component {required_type!r} "
                    f"for Relation {definition.type_id!r}."
                )
        for required_type in definition.target_requires:
            if not self.has_component(target, required_type):
                raise WorldInvariantError(
                    f"Target Entity {target!r} requires Component {required_type!r} "
                    f"for Relation {definition.type_id!r}."
                )

    def _validate_relation_cardinality(
        self,
        definition: RelationTypeDefinition,
        source: str,
        target: str,
    ) -> None:
        if definition.directional:
            if definition.max_from_source is not None:
                count = self._connection.execute(
                    "SELECT COUNT(*) AS count FROM relations WHERE type_id = ? AND source_entity_id = ?",
                    (definition.type_id, source),
                ).fetchone()["count"]
                if count >= definition.max_from_source:
                    raise WorldInvariantError(
                        f"Relation {definition.type_id!r} allows at most "
                        f"{definition.max_from_source} outgoing relation(s) from {source!r}."
                    )

            if definition.max_to_target is not None:
                count = self._connection.execute(
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
            count = self._connection.execute(
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


class WorldRepository(WorldReadView):
    """Validated persistent current-state and Event store for one world instance."""

    def __init__(self, store: SQLiteStore, registry: TypeRegistry) -> None:
        self.store = store
        self.registry = registry
        self._initialize()

    def _initialize(self) -> None:
        with self.store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
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
                        SELECT name FROM sqlite_master
                        WHERE type = 'table'
                          AND name IN ('entities', 'components', 'relations', 'events')
                        LIMIT 1
                        """
                    ).fetchone()
                    if unversioned_world_table is not None:
                        raise StorageSchemaError(
                            "World database contains unversioned canonical tables and cannot be adopted safely."
                        )
                    self._create_schema_v2(connection)
                    connection.execute(
                        "INSERT INTO fireworks_meta(key, value) VALUES ('storage_schema_version', ?)",
                        (str(_STORAGE_SCHEMA_VERSION),),
                    )
                else:
                    current = _parse_storage_version(row["value"])
                    if current > _STORAGE_SCHEMA_VERSION:
                        raise StorageSchemaError(
                            "World database storage schema revision "
                            f"{current} is newer than this build supports ({_STORAGE_SCHEMA_VERSION})."
                        )
                    while current < _STORAGE_SCHEMA_VERSION:
                        current = self._migrate(connection, current)
                    self._ensure_schema_v2(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _create_schema_v2(connection: sqlite3.Connection) -> None:
        WorldRepository._create_schema_v1_tables(connection)
        WorldRepository._create_events_table(connection)

    @staticmethod
    def _ensure_schema_v2(connection: sqlite3.Connection) -> None:
        WorldRepository._create_schema_v1_tables(connection)
        WorldRepository._create_events_table(connection)

    @staticmethod
    def _create_schema_v1_tables(connection: sqlite3.Connection) -> None:
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
        connection.execute("CREATE INDEX IF NOT EXISTS idx_components_type ON components(type_id)")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_relations_type_source ON relations(type_id, source_entity_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_relations_type_target ON relations(type_id, target_entity_id)"
        )

    @staticmethod
    def _create_events_table(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                type_id TEXT NOT NULL,
                schema_version INTEGER NOT NULL CHECK (schema_version >= 1),
                payload_json TEXT NOT NULL,
                recorded_at_utc TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_type_sequence ON events(type_id, sequence)"
        )

    @staticmethod
    def _migrate(connection: sqlite3.Connection, current: int) -> int:
        if current == 1:
            WorldRepository._create_events_table(connection)
            connection.execute(
                "UPDATE fireworks_meta SET value = '2' WHERE key = 'storage_schema_version'"
            )
            return 2
        raise StorageSchemaError(f"No storage migration is defined from revision {current}.")

    @contextmanager
    def transaction(self) -> Iterator[WorldTransaction]:
        connection = self.store.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            transaction = WorldTransaction(connection, self.registry)
            yield transaction
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def entity_exists(self, entity_id: str) -> bool:
        with self.store.connect() as connection:
            return _ConnectionReadView(connection, self.registry).entity_exists(entity_id)

    def has_component(self, entity_id: str, type_id: str) -> bool:
        with self.store.connect() as connection:
            return _ConnectionReadView(connection, self.registry).has_component(entity_id, type_id)

    def create_entity(self, entity_id: str | None = None) -> EntityRecord:
        with self.transaction() as transaction:
            return transaction.create_entity(entity_id)

    def entity(self, entity_id: str) -> EntityRecord:
        with self.store.connect() as connection:
            return WorldTransaction(connection, self.registry).entity(entity_id)

    def set_component(
        self,
        entity_id: str,
        type_id: str,
        payload: Mapping[str, Any],
        *,
        schema_version: int | None = None,
    ) -> ComponentRecord:
        with self.transaction() as transaction:
            return transaction.set_component(entity_id, type_id, payload, schema_version=schema_version)

    def component(self, entity_id: str, type_id: str) -> ComponentRecord | None:
        with self.store.connect() as connection:
            return WorldTransaction(connection, self.registry).component(entity_id, type_id)

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
        with self.transaction() as transaction:
            return transaction.add_relation(
                type_id,
                source_entity_id,
                target_entity_id,
                payload,
                schema_version=schema_version,
                relation_id=relation_id,
            )

    def relation(self, relation_id: str) -> RelationRecord | None:
        with self.store.connect() as connection:
            return WorldTransaction(connection, self.registry).relation(relation_id)

    def relations_for(self, entity_id: str, type_id: str | None = None) -> list[RelationRecord]:
        with self.store.connect() as connection:
            return WorldTransaction(connection, self.registry).relations_for(entity_id, type_id)

    def remove_relation(self, relation_id: str) -> bool:
        with self.transaction() as transaction:
            return transaction.remove_relation(relation_id)

    def event(self, sequence: int) -> EventRecord | None:
        with self.store.connect() as connection:
            row = connection.execute(
                """
                SELECT sequence, id, type_id, schema_version, payload_json, recorded_at_utc
                FROM events WHERE sequence = ?
                """,
                (sequence,),
            ).fetchone()
        if row is None:
            return None
        return self._validated_event_from_row(row)

    def events_after(self, sequence: int = 0, *, limit: int = 100) -> list[EventRecord]:
        if sequence < 0:
            raise WorldStateError("Event sequence must not be negative.")
        if limit < 1:
            raise WorldStateError("Event limit must be positive.")

        with self.store.connect() as connection:
            rows = connection.execute(
                """
                SELECT sequence, id, type_id, schema_version, payload_json, recorded_at_utc
                FROM events
                WHERE sequence > ?
                ORDER BY sequence
                LIMIT ?
                """,
                (sequence, limit),
            ).fetchall()
        return [self._validated_event_from_row(row) for row in rows]

    def _validated_event_from_row(self, row: sqlite3.Row) -> EventRecord:
        record = _event_from_row(row)
        self.registry.validate_event_payload(record.type_id, record.payload, record.schema_version)
        return record


def _parse_storage_version(value: str) -> int:
    try:
        version = int(value)
    except ValueError as exc:
        raise StorageSchemaError(f"Invalid storage schema revision marker {value!r}.") from exc
    if version < 1:
        raise StorageSchemaError(f"Invalid storage schema revision marker {value!r}.")
    return version


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


def _event_from_row(row: sqlite3.Row) -> EventRecord:
    return EventRecord(
        sequence=row["sequence"],
        event_id=row["id"],
        type_id=row["type_id"],
        schema_version=row["schema_version"],
        payload=json.loads(row["payload_json"]),
        recorded_at_utc=row["recorded_at_utc"],
    )

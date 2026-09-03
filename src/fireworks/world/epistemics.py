from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4

from .registry import TypeRegistry
from .repository import (
    StorageSchemaError,
    WorldInvariantError,
    WorldRepository,
    WorldStateError,
    WorldTransaction,
)

_EPISTEMIC_STORAGE_SCHEMA_VERSION = 3


class EpistemicCertainty(StrEnum):
    CERTAIN = "certain"
    BELIEVED = "believed"
    SUSPECTED = "suspected"
    DOUBTED = "doubted"
    REJECTED = "rejected"


class PerspectiveSource(StrEnum):
    MEMORY = "memory"
    PERCEPTION = "perception"
    COMMUNICATION = "communication"
    PUBLIC = "public"


@dataclass(frozen=True, slots=True)
class EpistemicRecord:
    record_id: str
    holder_entity_id: str
    claim_type_id: str
    claim_schema_version: int
    payload: dict[str, Any]
    certainty: EpistemicCertainty
    as_of_event_sequence: int | None
    recorded_at_utc: str


@dataclass(frozen=True, slots=True)
class PerspectiveContribution:
    """Transient information already scoped to a particular recipient."""

    recipient_entity_id: str
    claim_type_id: str
    payload: dict[str, Any]
    source: PerspectiveSource
    certainty: EpistemicCertainty = EpistemicCertainty.CERTAIN
    claim_schema_version: int | None = None
    as_of_event_sequence: int | None = None

    def __post_init__(self) -> None:
        if self.source is PerspectiveSource.MEMORY:
            raise ValueError("Transient PerspectiveContribution cannot use the memory source.")


@dataclass(frozen=True, slots=True)
class PerspectiveClaim:
    claim_type_id: str
    claim_schema_version: int
    payload: dict[str, Any]
    certainty: EpistemicCertainty
    source: PerspectiveSource
    as_of_event_sequence: int | None
    epistemic_record_id: str | None = None


@dataclass(frozen=True, slots=True)
class Perspective:
    """Temporary character-scoped information safe to hand to the runtime Director."""

    holder_entity_id: str
    claims: tuple[PerspectiveClaim, ...]


class EpistemicReadView(Protocol):
    def entity_exists(self, entity_id: str) -> bool: ...

    def epistemic_records_for(
        self, holder_entity_id: str, claim_type_id: str | None = None
    ) -> list[EpistemicRecord]: ...


class PerspectiveBuilder:
    """Builds a safe view without querying omniscient Components or Relations."""

    def __init__(self, reader: EpistemicReadView, registry: TypeRegistry) -> None:
        self._reader = reader
        self._registry = registry

    def build(
        self,
        holder_entity_id: str,
        *,
        contributions: tuple[PerspectiveContribution, ...] = (),
    ) -> Perspective:
        if not self._reader.entity_exists(holder_entity_id):
            raise ValueError(f"Perspective holder {holder_entity_id!r} does not exist.")

        claims: list[PerspectiveClaim] = []
        for record in self._reader.epistemic_records_for(holder_entity_id):
            claims.append(
                PerspectiveClaim(
                    claim_type_id=record.claim_type_id,
                    claim_schema_version=record.claim_schema_version,
                    payload=dict(record.payload),
                    certainty=record.certainty,
                    source=PerspectiveSource.MEMORY,
                    as_of_event_sequence=record.as_of_event_sequence,
                    epistemic_record_id=record.record_id,
                )
            )

        for contribution in contributions:
            if contribution.recipient_entity_id != holder_entity_id:
                continue
            definition = self._registry.validate_epistemic_claim_payload(
                contribution.claim_type_id,
                contribution.payload,
                contribution.claim_schema_version,
            )
            claims.append(
                PerspectiveClaim(
                    claim_type_id=contribution.claim_type_id,
                    claim_schema_version=definition.schema_version,
                    payload=dict(contribution.payload),
                    certainty=contribution.certainty,
                    source=contribution.source,
                    as_of_event_sequence=contribution.as_of_event_sequence,
                )
            )

        return Perspective(holder_entity_id=holder_entity_id, claims=tuple(claims))


class EpistemicWorldTransaction(WorldTransaction):
    """WorldTransaction extended with persistent character belief/knowledge state."""

    def add_epistemic_record(
        self,
        holder_entity_id: str,
        claim_type_id: str,
        payload: Mapping[str, Any],
        *,
        certainty: EpistemicCertainty | str = EpistemicCertainty.BELIEVED,
        claim_schema_version: int | None = None,
        as_of_event_sequence: int | None = None,
        record_id: str | None = None,
    ) -> EpistemicRecord:
        certainty_value = _coerce_certainty(certainty)
        definition = self.registry.validate_epistemic_claim_payload(
            claim_type_id, payload, claim_schema_version
        )
        self._require_entity(holder_entity_id)
        self._require_event_sequence(as_of_event_sequence)

        if definition.semantic_validator is not None:
            definition.semantic_validator(self, holder_entity_id, dict(payload))

        resolved_id = str(uuid4()) if record_id is None else record_id
        if not resolved_id.strip():
            raise WorldStateError("Epistemic record IDs must not be empty.")
        recorded_at_utc = _utc_now()

        try:
            self._connection.execute(
                """
                INSERT INTO epistemic_records(
                    id, holder_entity_id, claim_type_id, claim_schema_version,
                    payload_json, certainty, as_of_event_sequence, recorded_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_id,
                    holder_entity_id,
                    claim_type_id,
                    definition.schema_version,
                    _encode_payload(payload),
                    certainty_value.value,
                    as_of_event_sequence,
                    recorded_at_utc,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise WorldInvariantError(
                f"Epistemic record ID {resolved_id!r} already exists or violates database integrity."
            ) from exc

        return EpistemicRecord(
            record_id=resolved_id,
            holder_entity_id=holder_entity_id,
            claim_type_id=claim_type_id,
            claim_schema_version=definition.schema_version,
            payload=dict(payload),
            certainty=certainty_value,
            as_of_event_sequence=as_of_event_sequence,
            recorded_at_utc=recorded_at_utc,
        )

    def replace_epistemic_record(
        self,
        record_id: str,
        payload: Mapping[str, Any],
        *,
        certainty: EpistemicCertainty | str,
        claim_schema_version: int | None = None,
        as_of_event_sequence: int | None = None,
    ) -> EpistemicRecord:
        existing = self.epistemic_record(record_id)
        if existing is None:
            raise WorldStateError(f"Epistemic record {record_id!r} does not exist.")

        certainty_value = _coerce_certainty(certainty)
        definition = self.registry.validate_epistemic_claim_payload(
            existing.claim_type_id, payload, claim_schema_version
        )
        self._require_event_sequence(as_of_event_sequence)
        if definition.semantic_validator is not None:
            definition.semantic_validator(self, existing.holder_entity_id, dict(payload))

        recorded_at_utc = _utc_now()
        self._connection.execute(
            """
            UPDATE epistemic_records
            SET claim_schema_version = ?, payload_json = ?, certainty = ?,
                as_of_event_sequence = ?, recorded_at_utc = ?
            WHERE id = ?
            """,
            (
                definition.schema_version,
                _encode_payload(payload),
                certainty_value.value,
                as_of_event_sequence,
                recorded_at_utc,
                record_id,
            ),
        )
        return EpistemicRecord(
            record_id=record_id,
            holder_entity_id=existing.holder_entity_id,
            claim_type_id=existing.claim_type_id,
            claim_schema_version=definition.schema_version,
            payload=dict(payload),
            certainty=certainty_value,
            as_of_event_sequence=as_of_event_sequence,
            recorded_at_utc=recorded_at_utc,
        )

    def epistemic_record(self, record_id: str) -> EpistemicRecord | None:
        row = self._connection.execute(
            """
            SELECT id, holder_entity_id, claim_type_id, claim_schema_version,
                   payload_json, certainty, as_of_event_sequence, recorded_at_utc
            FROM epistemic_records WHERE id = ?
            """,
            (record_id,),
        ).fetchone()
        if row is None:
            return None
        return self._validated_epistemic_from_row(row)

    def epistemic_records_for(
        self, holder_entity_id: str, claim_type_id: str | None = None
    ) -> list[EpistemicRecord]:
        self._require_entity(holder_entity_id)
        if claim_type_id is None:
            rows = self._connection.execute(
                """
                SELECT id, holder_entity_id, claim_type_id, claim_schema_version,
                       payload_json, certainty, as_of_event_sequence, recorded_at_utc
                FROM epistemic_records
                WHERE holder_entity_id = ?
                ORDER BY recorded_at_utc, id
                """,
                (holder_entity_id,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT id, holder_entity_id, claim_type_id, claim_schema_version,
                       payload_json, certainty, as_of_event_sequence, recorded_at_utc
                FROM epistemic_records
                WHERE holder_entity_id = ? AND claim_type_id = ?
                ORDER BY recorded_at_utc, id
                """,
                (holder_entity_id, claim_type_id),
            ).fetchall()
        return [self._validated_epistemic_from_row(row) for row in rows]

    def remove_epistemic_record(self, record_id: str) -> bool:
        cursor = self._connection.execute("DELETE FROM epistemic_records WHERE id = ?", (record_id,))
        return cursor.rowcount > 0

    def _validated_epistemic_from_row(self, row: sqlite3.Row) -> EpistemicRecord:
        record = _epistemic_from_row(row)
        self.registry.validate_epistemic_claim_payload(
            record.claim_type_id,
            record.payload,
            record.claim_schema_version,
        )
        return record

    def _require_event_sequence(self, sequence: int | None) -> None:
        if sequence is None:
            return
        if sequence < 1:
            raise WorldStateError("Epistemic as-of Event sequence must be positive when provided.")
        row = self._connection.execute("SELECT 1 FROM events WHERE sequence = ?", (sequence,)).fetchone()
        if row is None:
            raise WorldInvariantError(f"Event sequence {sequence} does not exist in this world.")


class EpistemicWorldRepository(WorldRepository):
    """Revision-3 world repository with persistent epistemic state."""

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
                    unversioned = connection.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type = 'table'
                          AND name IN ('entities', 'components', 'relations', 'events', 'epistemic_records')
                        LIMIT 1
                        """
                    ).fetchone()
                    if unversioned is not None:
                        raise StorageSchemaError(
                            "World database contains unversioned canonical tables and cannot be adopted safely."
                        )
                    WorldRepository._create_schema_v1_tables(connection)
                    WorldRepository._create_events_table(connection)
                    self._create_epistemic_table(connection)
                    connection.execute(
                        "INSERT INTO fireworks_meta(key, value) VALUES ('storage_schema_version', '3')"
                    )
                else:
                    current = _parse_storage_version(row["value"])
                    if current > _EPISTEMIC_STORAGE_SCHEMA_VERSION:
                        raise StorageSchemaError(
                            "World database storage schema revision "
                            f"{current} is newer than this build supports ({_EPISTEMIC_STORAGE_SCHEMA_VERSION})."
                        )
                    while current < _EPISTEMIC_STORAGE_SCHEMA_VERSION:
                        if current < 2:
                            current = WorldRepository._migrate(connection, current)
                        elif current == 2:
                            self._create_epistemic_table(connection)
                            connection.execute(
                                "UPDATE fireworks_meta SET value = '3' WHERE key = 'storage_schema_version'"
                            )
                            current = 3
                        else:
                            raise StorageSchemaError(
                                f"No epistemic storage migration is defined from revision {current}."
                            )

                    WorldRepository._create_schema_v1_tables(connection)
                    WorldRepository._create_events_table(connection)
                    self._create_epistemic_table(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _create_epistemic_table(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS epistemic_records (
                id TEXT PRIMARY KEY,
                holder_entity_id TEXT NOT NULL,
                claim_type_id TEXT NOT NULL,
                claim_schema_version INTEGER NOT NULL CHECK (claim_schema_version >= 1),
                payload_json TEXT NOT NULL,
                certainty TEXT NOT NULL CHECK (
                    certainty IN ('certain', 'believed', 'suspected', 'doubted', 'rejected')
                ),
                as_of_event_sequence INTEGER,
                recorded_at_utc TEXT NOT NULL,
                FOREIGN KEY (holder_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
                FOREIGN KEY (as_of_event_sequence) REFERENCES events(sequence) ON DELETE RESTRICT
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_epistemic_holder_type "
            "ON epistemic_records(holder_entity_id, claim_type_id)"
        )

    @contextmanager
    def transaction(self) -> Iterator[EpistemicWorldTransaction]:
        connection = self.store.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            transaction = EpistemicWorldTransaction(connection, self.registry)
            yield transaction
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def add_epistemic_record(
        self,
        holder_entity_id: str,
        claim_type_id: str,
        payload: Mapping[str, Any],
        *,
        certainty: EpistemicCertainty | str = EpistemicCertainty.BELIEVED,
        claim_schema_version: int | None = None,
        as_of_event_sequence: int | None = None,
        record_id: str | None = None,
    ) -> EpistemicRecord:
        with self.transaction() as transaction:
            return transaction.add_epistemic_record(
                holder_entity_id,
                claim_type_id,
                payload,
                certainty=certainty,
                claim_schema_version=claim_schema_version,
                as_of_event_sequence=as_of_event_sequence,
                record_id=record_id,
            )

    def replace_epistemic_record(
        self,
        record_id: str,
        payload: Mapping[str, Any],
        *,
        certainty: EpistemicCertainty | str,
        claim_schema_version: int | None = None,
        as_of_event_sequence: int | None = None,
    ) -> EpistemicRecord:
        with self.transaction() as transaction:
            return transaction.replace_epistemic_record(
                record_id,
                payload,
                certainty=certainty,
                claim_schema_version=claim_schema_version,
                as_of_event_sequence=as_of_event_sequence,
            )

    def epistemic_record(self, record_id: str) -> EpistemicRecord | None:
        with self.store.connect() as connection:
            return EpistemicWorldTransaction(connection, self.registry).epistemic_record(record_id)

    def epistemic_records_for(
        self, holder_entity_id: str, claim_type_id: str | None = None
    ) -> list[EpistemicRecord]:
        with self.store.connect() as connection:
            return EpistemicWorldTransaction(connection, self.registry).epistemic_records_for(
                holder_entity_id, claim_type_id
            )

    def remove_epistemic_record(self, record_id: str) -> bool:
        with self.transaction() as transaction:
            return transaction.remove_epistemic_record(record_id)


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


def _coerce_certainty(value: EpistemicCertainty | str) -> EpistemicCertainty:
    try:
        return value if isinstance(value, EpistemicCertainty) else EpistemicCertainty(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in EpistemicCertainty)
        raise WorldStateError(f"Unknown epistemic certainty {value!r}; expected one of: {allowed}.") from exc


def _epistemic_from_row(row: sqlite3.Row) -> EpistemicRecord:
    return EpistemicRecord(
        record_id=row["id"],
        holder_entity_id=row["holder_entity_id"],
        claim_type_id=row["claim_type_id"],
        claim_schema_version=row["claim_schema_version"],
        payload=json.loads(row["payload_json"]),
        certainty=_coerce_certainty(row["certainty"]),
        as_of_event_sequence=row["as_of_event_sequence"],
        recorded_at_utc=row["recorded_at_utc"],
    )

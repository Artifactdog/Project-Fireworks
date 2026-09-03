from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from .registry import TypeRegistry


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
    """Perspective-safe transient information produced by a perception/comms/public subsystem."""

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
    """Builds a character-scoped view without querying omniscient Components/Relations."""

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

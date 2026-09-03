from dataclasses import dataclass

import pytest

from fireworks.actions import ActionContractError, ActionEngine
from fireworks.storage import SQLiteStore
from fireworks.world import (
    EpistemicCertainty,
    EpistemicClaimTypeDefinition,
    EpistemicWorldRepository,
    EpistemicWorldTransaction,
    EventTypeDefinition,
    PerspectiveBuilder,
    PerspectiveContribution,
    PerspectiveSource,
    StorageSchemaError,
    TypePayloadError,
    TypeRegistry,
    WorldInvariantError,
    WorldRepository,
)

EMPTY_OBJECT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
}

LOCATION_CLAIM_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "entity": {"type": "string", "minLength": 1},
        "location": {"type": "string", "minLength": 1},
    },
    "required": ["entity", "location"],
    "additionalProperties": False,
}

OBSERVED_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "observer": {"type": "string", "minLength": 1},
        "entity": {"type": "string", "minLength": 1},
        "location": {"type": "string", "minLength": 1},
    },
    "required": ["observer", "entity", "location"],
    "additionalProperties": False,
}


def make_registry() -> TypeRegistry:
    registry = TypeRegistry()
    registry.register_epistemic_claim(
        EpistemicClaimTypeDefinition(
            type_id="core.entity_location",
            schema_version=1,
            schema=LOCATION_CLAIM_SCHEMA,
        )
    )
    registry.register_event(
        EventTypeDefinition(
            type_id="core.observed_location",
            schema_version=1,
            schema=OBSERVED_SCHEMA,
        )
    )
    registry.register_event(
        EventTypeDefinition(
            type_id="core.note",
            schema_version=1,
            schema=EMPTY_OBJECT_SCHEMA,
        )
    )
    return registry


def make_world(path) -> EpistemicWorldRepository:
    return EpistemicWorldRepository(SQLiteStore(path), make_registry())


def test_epistemic_claim_payloads_are_typed_and_validated(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    world.create_entity("player-a")

    with pytest.raises(TypePayloadError):
        world.add_epistemic_record(
            "player-a",
            "core.entity_location",
            {"entity": "nadia", "invented": "field"},
        )

    assert world.epistemic_records_for("player-a") == []


def test_contradictory_beliefs_can_coexist_without_core_resolution(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    world.create_entity("player-a")

    first = world.add_epistemic_record(
        "player-a",
        "core.entity_location",
        {"entity": "nadia", "location": "bar"},
        certainty=EpistemicCertainty.BELIEVED,
    )
    second = world.add_epistemic_record(
        "player-a",
        "core.entity_location",
        {"entity": "nadia", "location": "apartment"},
        certainty=EpistemicCertainty.SUSPECTED,
    )

    records = world.epistemic_records_for("player-a", "core.entity_location")
    assert {record.record_id for record in records} == {first.record_id, second.record_id}
    assert {record.payload["location"] for record in records} == {"bar", "apartment"}


def test_epistemic_as_of_sequence_must_reference_real_event(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    world.create_entity("player-a")

    with pytest.raises(WorldInvariantError):
        world.add_epistemic_record(
            "player-a",
            "core.entity_location",
            {"entity": "nadia", "location": "bar"},
            as_of_event_sequence=999,
        )

    with world.transaction() as transaction:
        event = transaction.append_event(
            "core.observed_location",
            {"observer": "player-a", "entity": "nadia", "location": "bar"},
        )
        record = transaction.add_epistemic_record(
            "player-a",
            "core.entity_location",
            {"entity": "nadia", "location": "bar"},
            certainty=EpistemicCertainty.CERTAIN,
            as_of_event_sequence=event.sequence,
        )

    assert world.epistemic_record(record.record_id).as_of_event_sequence == event.sequence


def test_stored_knowledge_does_not_magically_advance_with_later_events(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    world.create_entity("player-a")

    with world.transaction() as transaction:
        observed = transaction.append_event(
            "core.observed_location",
            {"observer": "player-a", "entity": "nadia", "location": "bar"},
        )
        record = transaction.add_epistemic_record(
            "player-a",
            "core.entity_location",
            {"entity": "nadia", "location": "bar"},
            certainty=EpistemicCertainty.CERTAIN,
            as_of_event_sequence=observed.sequence,
        )
        later = transaction.append_event("core.note", {})

    stored = world.epistemic_record(record.record_id)
    assert stored.payload["location"] == "bar"
    assert stored.as_of_event_sequence == observed.sequence
    assert later.sequence > stored.as_of_event_sequence


def test_perspective_contains_only_holder_memory_and_addressed_contributions(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    world.create_entity("player-a")
    world.create_entity("player-b")

    world.add_epistemic_record(
        "player-a",
        "core.entity_location",
        {"entity": "nadia", "location": "old-bar"},
        certainty=EpistemicCertainty.BELIEVED,
    )
    world.add_epistemic_record(
        "player-b",
        "core.entity_location",
        {"entity": "nadia", "location": "secret-place"},
        certainty=EpistemicCertainty.CERTAIN,
    )

    perspective = PerspectiveBuilder(world, world.registry).build(
        "player-a",
        contributions=(
            PerspectiveContribution(
                recipient_entity_id="player-a",
                claim_type_id="core.entity_location",
                payload={"entity": "alex", "location": "hallway"},
                source=PerspectiveSource.PERCEPTION,
            ),
            PerspectiveContribution(
                recipient_entity_id="player-b",
                claim_type_id="core.entity_location",
                payload={"entity": "nadia", "location": "velvet-bar"},
                source=PerspectiveSource.PERCEPTION,
            ),
        ),
    )

    locations = {(claim.payload["entity"], claim.payload["location"]) for claim in perspective.claims}
    assert locations == {("nadia", "old-bar"), ("alex", "hallway")}
    assert {claim.source for claim in perspective.claims} == {
        PerspectiveSource.MEMORY,
        PerspectiveSource.PERCEPTION,
    }


def test_perspective_rejects_malformed_transient_claims(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    world.create_entity("player-a")

    with pytest.raises(TypePayloadError):
        PerspectiveBuilder(world, world.registry).build(
            "player-a",
            contributions=(
                PerspectiveContribution(
                    recipient_entity_id="player-a",
                    claim_type_id="core.entity_location",
                    payload={"entity": "nadia"},
                    source=PerspectiveSource.COMMUNICATION,
                ),
            ),
        )


@dataclass(frozen=True)
class LearnLocationAction:
    fail: bool = False

    def execute(self, transaction: EpistemicWorldTransaction) -> str:
        event = transaction.append_event(
            "core.observed_location",
            {"observer": "player-a", "entity": "nadia", "location": "bar"},
        )
        transaction.add_epistemic_record(
            "player-a",
            "core.entity_location",
            {"entity": "nadia", "location": "bar"},
            certainty=EpistemicCertainty.CERTAIN,
            as_of_event_sequence=event.sequence,
        )
        if self.fail:
            raise RuntimeError("simulated failure")
        return "learned"


def test_epistemic_change_and_source_event_commit_atomically(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    world.create_entity("player-a")

    assert ActionEngine(world).execute(LearnLocationAction()) == "learned"
    assert len(world.events_after()) == 1
    assert len(world.epistemic_records_for("player-a")) == 1


def test_epistemic_change_and_event_roll_back_together(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    world.create_entity("player-a")

    with pytest.raises(RuntimeError):
        ActionEngine(world).execute(LearnLocationAction(fail=True))

    assert world.events_after() == []
    assert world.epistemic_records_for("player-a") == []


@dataclass(frozen=True)
class HistorylessBeliefAction:
    def execute(self, transaction: EpistemicWorldTransaction) -> None:
        transaction.add_epistemic_record(
            "player-a",
            "core.entity_location",
            {"entity": "nadia", "location": "bar"},
        )


def test_epistemic_mutation_without_event_is_rejected_by_action_engine(tmp_path) -> None:
    world = make_world(tmp_path / "world.sqlite3")
    world.create_entity("player-a")

    with pytest.raises(ActionContractError):
        ActionEngine(world).execute(HistorylessBeliefAction())

    assert world.epistemic_records_for("player-a") == []


def test_revision_two_migrates_to_epistemic_storage_and_old_repository_refuses_it(tmp_path) -> None:
    path = tmp_path / "world.sqlite3"
    store = SQLiteStore(path)
    base_registry = make_registry()
    old_world = WorldRepository(store, base_registry)
    old_world.create_entity("player-a")
    with old_world.transaction() as transaction:
        transaction.append_event("core.note", {})

    world = EpistemicWorldRepository(store, base_registry)
    assert world.entity("player-a").entity_id == "player-a"
    assert len(world.events_after()) == 1

    with store.connect() as connection:
        version = connection.execute(
            "SELECT value FROM fireworks_meta WHERE key = 'storage_schema_version'"
        ).fetchone()["value"]
        epistemic_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'epistemic_records'"
        ).fetchone()

    assert version == "3"
    assert epistemic_table is not None

    with pytest.raises(StorageSchemaError):
        WorldRepository(store, base_registry)

from fastapi.testclient import TestClient

from fireworks.app import create_app
from fireworks.content.green_star import GREEN_STAR_RESTROOM_ID
from fireworks.core_game import build_core_type_registry
from fireworks.storage import SQLiteStore
from fireworks.world import EpistemicWorldRepository


def test_green_star_opening_creates_character_and_moves_to_restroom(tmp_path) -> None:
    database_path = tmp_path / "fireworks.sqlite3"
    client = TestClient(create_app(database_path))

    response = client.post("/play/start")

    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == "appearance"
    assert body["prompt"] == "What do you look like? Describe the person taking shape in the mirror."
    assert "Green Star" in body["text"]

    world = EpistemicWorldRepository(SQLiteStore(database_path), build_core_type_registry())
    locations = world.relations_for(body["character_id"], "core.physical_location")
    assert len(locations) == 1
    assert locations[0].target_entity_id == GREEN_STAR_RESTROOM_ID

    events = world.events_after()
    assert [event.type_id for event in events] == ["core.location_changed"]


def test_freeform_appearance_is_preserved_and_name_is_established_separately(tmp_path) -> None:
    database_path = tmp_path / "fireworks.sqlite3"
    client = TestClient(create_app(database_path))
    character_id = client.post("/play/start").json()["character_id"]
    appearance = (
        "A tired-looking woman somewhere around thirty, with short black hair, dark circles "
        "under her eyes, and a wrinkled white shirt that still looks like work clothes."
    )

    appearance_response = client.post(
        "/play/input",
        json={"character_id": character_id, "text": appearance},
    )

    assert appearance_response.status_code == 200
    appearance_body = appearance_response.json()
    assert appearance_body["phase"] == "name"
    assert appearance_body["text"] == appearance
    assert "name" in appearance_body["prompt"].lower()

    name_response = client.post(
        "/play/input",
        json={"character_id": character_id, "text": "Mara"},
    )

    assert name_response.status_code == 200
    name_body = name_response.json()
    assert name_body["phase"] == "complete"
    assert name_body["prompt"] is None
    assert '"Mara."' in name_body["text"]

    world = EpistemicWorldRepository(SQLiteStore(database_path), build_core_type_registry())
    assert world.component(character_id, "character.appearance").payload == {
        "description": appearance
    }
    assert world.component(character_id, "character.identity").payload == {"name": "Mara"}
    assert [event.type_id for event in world.events_after()] == [
        "core.location_changed",
        "character.appearance_established",
        "character.name_established",
    ]


def test_completed_character_resumes_after_new_app_instance(tmp_path) -> None:
    database_path = tmp_path / "fireworks.sqlite3"
    first_client = TestClient(create_app(database_path))
    character_id = first_client.post("/play/start").json()["character_id"]
    first_client.post(
        "/play/input",
        json={"character_id": character_id, "text": "Tall, pale, and visibly exhausted."},
    )
    first_client.post(
        "/play/input",
        json={"character_id": character_id, "text": "Iris"},
    )

    second_client = TestClient(create_app(database_path))
    response = second_client.get(f"/play/{character_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == "complete"
    assert '"Iris."' in body["text"]


def test_empty_character_creation_input_is_rejected_without_mutation(tmp_path) -> None:
    database_path = tmp_path / "fireworks.sqlite3"
    client = TestClient(create_app(database_path))
    character_id = client.post("/play/start").json()["character_id"]

    response = client.post(
        "/play/input",
        json={"character_id": character_id, "text": "   "},
    )

    assert response.status_code == 400
    world = EpistemicWorldRepository(SQLiteStore(database_path), build_core_type_registry())
    assert world.component(character_id, "character.appearance") is None
    assert [event.type_id for event in world.events_after()] == ["core.location_changed"]

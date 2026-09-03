from fastapi.testclient import TestClient

from fireworks.app import create_app


def test_health_checks_sqlite(tmp_path) -> None:
    database_path = tmp_path / "fireworks.sqlite3"
    client = TestClient(create_app(database_path))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert database_path.exists()

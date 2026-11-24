"""End-to-end tests for REST API endpoints and WebSocket stream."""

import json
import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "chance-to-alert"


def test_get_config_presets(client):
    response = client.get("/api/v1/config/presets")
    assert response.status_code == 200
    presets = response.json()
    assert "odesa_district" in presets
    assert "odesa_oblast" in presets


def test_get_preset_detail(client):
    response = client.get("/api/v1/config/presets/odesa_district")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] in ("Odesa District", "odesa_district")
    assert "centroid" in data


def test_get_preset_detail_not_found(client):
    response = client.get("/api/v1/config/presets/non_existent_preset")
    assert response.status_code == 404


def test_get_channels(client):
    response = client.get("/api/v1/config/channels")
    assert response.status_code == 200
    channels = response.json()
    assert isinstance(channels, list)
    assert len(channels) > 0


def test_get_probability_default(client):
    response = client.get("/api/v1/probability")
    assert response.status_code == 200
    data = response.json()
    assert "probability_percent" in data
    assert 0 <= data["probability_percent"] <= 100
    assert "alert_level" in data
    assert "target_district" in data


def test_simulate_threat_pipeline(client):
    payload = {
        "text": "3 БПЛА Shahed з моря курсом на Одесу!",
        "channel": "vanek_nikolaev",
        "quantity": 3,
    }
    response = client.post("/api/v1/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ingested"
    assert data["signals_count"] >= 1
    assert data["probability"]["probability_percent"] > 0

    # Verify reflected in current threats
    curr_resp = client.get("/api/v1/threats/current")
    assert curr_resp.status_code == 200
    assert len(curr_resp.json()) >= 1

    # Verify reflected in history
    hist_resp = client.get("/api/v1/threats/history?limit=10&offset=0")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["total"] >= 1
    assert len(hist_data["items"]) >= 1


def test_websocket_stream(client):
    with client.websocket_connect("/api/v1/ws") as websocket:
        init_data = websocket.receive_text()
        parsed = json.loads(init_data)
        assert parsed["type"] == "connected"
        assert parsed["status"] == "ready"

        websocket.send_text("ping")
        pong = websocket.receive_text()
        assert pong == "pong"

        websocket.send_text("close")

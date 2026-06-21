"""Agent management API tests."""
from tests.test_api_auth import client


def _get_token():
    client.post("/api/v1/auth/register", json={"email": "agent@test.com", "password": "secret"})
    r = client.post("/api/v1/auth/login", data={"username": "agent@test.com", "password": "secret"})
    return r.json()["access_token"]


def test_register_agent():
    token = _get_token()
    res = client.post(
        "/api/v1/agents/",
        json={"name": "test-agent-1", "capabilities": '["dockerfile", "k8s"]'},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "test-agent-1"
    assert data["status"] == "idle"


def test_list_agents():
    token = _get_token()
    client.post(
        "/api/v1/agents/",
        json={"name": "agent-list-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post(
        "/api/v1/agents/",
        json={"name": "agent-list-2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    res = client.get(
        "/api/v1/agents/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert len(res.json()) >= 2


def test_agent_heartbeat():
    token = _get_token()
    create_res = client.post(
        "/api/v1/agents/",
        json={"name": "heartbeat-agent"},
        headers={"Authorization": f"Bearer {token}"},
    )
    agent_id = create_res.json()["id"]
    res = client.post(
        f"/api/v1/agents/{agent_id}/heartbeat",
        json={"status": "busy"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "busy"


def test_get_agent():
    token = _get_token()
    create_res = client.post(
        "/api/v1/agents/",
        json={"name": "get-test-agent"},
        headers={"Authorization": f"Bearer {token}"},
    )
    agent_id = create_res.json()["id"]
    res = client.get(
        f"/api/v1/agents/{agent_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "get-test-agent"


def test_get_agent_not_found():
    token = _get_token()
    res = client.get(
        "/api/v1/agents/99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
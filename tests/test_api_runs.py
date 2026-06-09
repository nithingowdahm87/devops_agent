"""Run API tests."""
from fastapi.testclient import TestClient
from tests.test_api_auth import client, _setup_db


def _get_token():
    client.post("/api/v1/auth/register", json={"email": "run@test.com", "password": "secret"})
    r = client.post("/api/v1/auth/login", data={"username": "run@test.com", "password": "secret"})
    return r.json()["access_token"]


def test_start_run():
    token = _get_token()
    p = client.post("/api/v1/projects/", json={"name": "RunTest"}, headers={"Authorization": f"Bearer {token}"})
    pid = p.json()["id"]

    # Note: project.repo_url is empty, so pipeline will fail, but we test the API endpoint
    res = client.post(
        "/api/v1/runs/",
        json={"project_id": pid, "config": {}, "no_heal": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 202
    assert "run_id" in res.json()


def test_get_run():
    token = _get_token()
    p = client.post("/api/v1/projects/", json={"name": "RunTest2"}, headers={"Authorization": f"Bearer {token}"})
    pid = p.json()["id"]

    r = client.post(
        "/api/v1/runs/",
        json={"project_id": pid, "config": {}, "no_heal": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    rid = r.json()["run_id"]

    res = client.get(f"/api/v1/runs/{rid}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["status"] in ("pending", "running", "completed", "failed")


def test_admin_health():
    res = client.get("/api/v1/admin/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
"""Project API tests."""
from tests.test_api_auth import client


def _get_token():
    client.post("/api/v1/auth/register", json={"email": "proj@test.com", "password": "secret"})
    r = client.post("/api/v1/auth/login", data={"username": "proj@test.com", "password": "secret"})
    return r.json()["access_token"]


def test_create_project():
    token = _get_token()
    res = client.post(
        "/api/v1/projects/",
        json={"name": "My App", "repo_url": "https://github.com/user/repo"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    assert res.json()["name"] == "My App"


def test_list_projects():
    token = _get_token()
    client.post("/api/v1/projects/", json={"name": "App1"}, headers={"Authorization": f"Bearer {token}"})
    res = client.get("/api/v1/projects/", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert len(res.json()) >= 1


def test_unauthorized():
    res = client.get("/api/v1/projects/")
    assert res.status_code == 401

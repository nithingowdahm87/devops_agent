"""Video API tests."""
from tests.test_api_auth import client


def _get_token():
    client.post("/api/v1/auth/register", json={"email": "video@test.com", "password": "secret"})
    r = client.post("/api/v1/auth/login", data={"username": "video@test.com", "password": "secret"})
    return r.json()["access_token"]


def _get_project_id(token: str) -> int:
    r = client.post(
        "/api/v1/projects/",
        json={"name": "Video Test Project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return r.json()["id"]


def test_create_video_task():
    token = _get_token()
    project_id = _get_project_id(token)
    res = client.post(
        "/api/v1/video/jobs",
        json={"prompt": "Generate a demo video", "project_id": project_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["prompt"] == "Generate a demo video"
    assert data["status"] == "pending"


def test_list_video_tasks():
    token = _get_token()
    project_id = _get_project_id(token)
    client.post(
        "/api/v1/video/jobs",
        json={"prompt": "Task 1", "project_id": project_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post(
        "/api/v1/video/jobs",
        json={"prompt": "Task 2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    res = client.get(
        "/api/v1/video/jobs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert len(res.json()) >= 2


def test_get_video_task():
    token = _get_token()
    project_id = _get_project_id(token)
    create_res = client.post(
        "/api/v1/video/jobs",
        json={"prompt": "Get me", "project_id": project_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    task_id = create_res.json()["id"]
    res = client.get(
        f"/api/v1/video/jobs/{task_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["prompt"] == "Get me"


def test_get_video_task_not_found():
    token = _get_token()
    res = client.get(
        "/api/v1/video/jobs/99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
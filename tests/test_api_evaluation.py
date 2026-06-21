"""Evaluation API tests."""
from tests.test_api_auth import client


def _get_token():
    client.post("/api/v1/auth/register", json={"email": "eval@test.com", "password": "secret"})
    r = client.post("/api/v1/auth/login", data={"username": "eval@test.com", "password": "secret"})
    return r.json()["access_token"]


def _get_project_id(token: str) -> int:
    r = client.post(
        "/api/v1/projects/",
        json={"name": "Eval Test Project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return r.json()["id"]


def test_create_evaluation():
    token = _get_token()
    project_id = _get_project_id(token)
    res = client.post(
        "/api/v1/evaluation/",
        json={
            "predictions": [1, 0, 1, 1, 0],
            "ground_truth": [1, 0, 1, 0, 0],
            "project_id": project_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["metric"] == "cohens_kappa"
    assert isinstance(data["score"], float)
    assert 0.0 <= data["score"] <= 1.0


def test_list_evaluations():
    token = _get_token()
    project_id = _get_project_id(token)
    client.post(
        "/api/v1/evaluation/",
        json={
            "predictions": [1, 0],
            "ground_truth": [1, 0],
            "project_id": project_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    res = client.get(
        "/api/v1/evaluation/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert len(res.json()) >= 1


def test_get_evaluation():
    token = _get_token()
    project_id = _get_project_id(token)
    create_res = client.post(
        "/api/v1/evaluation/",
        json={
            "predictions": [1, 1, 0],
            "ground_truth": [1, 0, 0],
            "project_id": project_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    eval_id = create_res.json()["id"]
    res = client.get(
        f"/api/v1/evaluation/{eval_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["metric"] == "cohens_kappa"
    assert isinstance(res.json()["score"], float)


def test_get_evaluation_not_found():
    token = _get_token()
    res = client.get(
        "/api/v1/evaluation/99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
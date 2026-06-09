"""API auth integration tests."""
import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_register():
    res = client.post("/api/v1/auth/register", json={"email": "test@example.com", "password": "secret"})
    assert res.status_code == 201
    assert "access_token" in res.json()


def test_login():
    client.post("/api/v1/auth/register", json={"email": "test@example.com", "password": "secret"})
    res = client.post("/api/v1/auth/login", data={"username": "test@example.com", "password": "secret"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password():
    client.post("/api/v1/auth/register", json={"email": "test@example.com", "password": "secret"})
    res = client.post("/api/v1/auth/login", data={"username": "test@example.com", "password": "wrong"})
    assert res.status_code == 401

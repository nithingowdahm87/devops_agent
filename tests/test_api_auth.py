"""API auth integration tests."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.main import app
from src.db.database import Base, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
_engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
_TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


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
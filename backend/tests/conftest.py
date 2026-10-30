"""
tests/conftest.py

Shared pytest fixtures used across all test modules.

Why use mongomock instead of a real MongoDB?
  Tests must be isolated and repeatable.  Using a real MongoDB would require
  a running server and would leave test data behind.  mongomock provides an
  in-memory MongoDB-compatible layer, so no real DB is needed.

  Install: pip install mongomock
  The fixture patches 'app.database.mongodb.database' so every call to
  get_database() inside the routes returns the mock DB.

TestClient:
  FastAPI's TestClient (from Starlette, backed by httpx) lets us call
  routes as if they were real HTTP requests, but entirely in-process.
"""

import pytest
from fastapi.testclient import TestClient

import app.api.documents as documents_api
from app.main import app


@pytest.fixture(scope="function")
def client(monkeypatch, test_database, tmp_path):
    """Provide an API client isolated from production MongoDB and uploads."""
    monkeypatch.setattr(documents_api, "UPLOAD_DIR", tmp_path)

    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def registered_user(client):
    """Register a standard user and return the payload used."""
    payload = {
        "name": "Test User",
        "email": "testuser@example.com",
        "password": "SecurePass123",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201, response.json()
    return payload


@pytest.fixture(scope="function")
def auth_token(client, registered_user):
    """Return a valid Bearer token for the registered test user."""
    response = client.post(
        "/api/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert response.status_code == 200, response.json()
    return response.json()["access_token"]


@pytest.fixture(scope="function")
def auth_headers(auth_token):
    """Return HTTP headers dict with Authorization Bearer token."""
    return {"Authorization": f"Bearer {auth_token}"}

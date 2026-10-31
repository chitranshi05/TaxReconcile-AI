from unittest.mock import patch

import mongomock
import pytest

# Construct the application's default client with mongomock too. This prevents
# a missing fixture from ever falling through to the configured MongoDB URL.
with patch("pymongo.MongoClient", mongomock.MongoClient):
    import app.main as main_module
    from app.database import mongodb
    from app.main import app


@pytest.fixture(scope="function", autouse=True)
def test_database(monkeypatch):
    """Provide an isolated in-memory database to every backend test."""
    mock_client = mongomock.MongoClient()
    mock_db = mock_client["test_tax_reconcile"]
    monkeypatch.setattr(mongodb, "database", mock_db)
    monkeypatch.setattr(mongodb, "client", mock_client)
    monkeypatch.setattr(main_module, "client", mock_client)
    yield mock_db
    mock_client.close()

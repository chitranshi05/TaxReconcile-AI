
from unittest.mock import MagicMock

from app.services import audit_service


def test_log_audit_event_returns_id_on_success(monkeypatch):
    fake_db = MagicMock()
    fake_db.__getitem__.return_value.insert_one.return_value.inserted_id = "audit123"

    monkeypatch.setattr(
        audit_service, "get_database", lambda: fake_db
    )

    result = audit_service.log_audit_event(
        action="DOCUMENT_UPLOADED",
        user_id="user123",
        resource_type="document",
        resource_id="doc123",
    )

    assert result == "audit123"


def test_log_audit_event_returns_none_when_database_fails(monkeypatch):
    fake_db = MagicMock()
    fake_db.__getitem__.return_value.insert_one.side_effect = RuntimeError(
        "Database unavailable"
    )

    monkeypatch.setattr(
        audit_service, "get_database", lambda: fake_db
    )

    result = audit_service.log_audit_event(
        action="DOCUMENT_UPLOADED",
        user_id="user123",
        resource_type="document",
        resource_id="doc123",
    )

    assert result is None

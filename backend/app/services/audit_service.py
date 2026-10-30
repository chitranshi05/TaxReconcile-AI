
import logging
from datetime import datetime, timezone
from typing import Any

from app.database.mongodb import get_database

logger = logging.getLogger(__name__)


def log_audit_event(
    action: str,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> str | None:
    """Store an audit event; log failures without raising an exception."""
    event = {
        "action": action,
        "user_id": user_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details or {},
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = get_database()["audit_logs"].insert_one(event)
        return str(result.inserted_id)
    except Exception:
        logger.exception(
            "Failed to write audit event: action=%s, resource_type=%s, resource_id=%s",
            action,
            resource_type,
            resource_id,
        )
        return None

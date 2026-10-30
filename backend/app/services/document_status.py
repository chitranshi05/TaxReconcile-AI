
from datetime import datetime, timezone

from bson import ObjectId

from app.database.mongodb import get_database
from app.services.audit_service import log_audit_event


ALLOWED_STATUSES = {"UPLOADED", "PENDING", "PROCESSED", "FAILED"}

ALLOWED_TRANSITIONS = {
    "UPLOADED": {"PENDING", "FAILED"},
    "PENDING": {"PROCESSED", "FAILED"},
    "FAILED": {"PENDING"},
    "PROCESSED": set(),
}


def update_document_status(document_id: str, status: str) -> bool:
    """Update a document's processing status if the transition is valid.

    Returns True if the document exists and was updated, otherwise False.
    Raises ValueError for an unsupported status, invalid ID, or invalid transition.
    """
    normalized_status = status.strip().upper()

    if normalized_status not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported document status: {status}")

    if not ObjectId.is_valid(document_id):
        raise ValueError("Invalid document ID")

    db = get_database()
    object_id = ObjectId(document_id)
    document = db.documents.find_one({"_id": object_id})

    if document is None:
        return False

    current_status = document.get("status", "UPLOADED").strip().upper()

    if normalized_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
        raise ValueError(
            f"Invalid document status transition: "
            f"{current_status} -> {normalized_status}"
        )

    result = db.documents.update_one(
        {"_id": object_id, "status": document.get("status", "UPLOADED")},
        {
            "$set": {
                "status": normalized_status,
                "status_updated_at": datetime.now(timezone.utc),
            }
        },
    )

    if result.matched_count == 0:
        return False

    log_audit_event(
        action="DOCUMENT_STATUS_UPDATED",
        resource_type="document",
        resource_id=document_id,
        details={
            "previous_status": current_status,
            "status": normalized_status,
        },
    )

    return True

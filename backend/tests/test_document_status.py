
import pytest
from bson import ObjectId

from app.database.mongodb import get_database
from app.services.document_status import update_document_status


def test_update_document_status_success(client):
    db = get_database()
    document_id = db.documents.insert_one({
        "filename": "test.csv",
        "status": "UPLOADED",
    }).inserted_id

    result = update_document_status(str(document_id), "PENDING")

    assert result is True
    document = db.documents.find_one({"_id": document_id})
    assert document["status"] == "PENDING"
    assert "status_updated_at" in document



def test_update_document_status_normalizes_case(client):
    db = get_database()
    document_id = db.documents.insert_one({
        "filename": "test.csv",
        "status": "UPLOADED",
    }).inserted_id

    assert update_document_status(str(document_id), "pending") is True
    assert update_document_status(str(document_id), "processed") is True
    assert db.documents.find_one({"_id": document_id})["status"] == "PROCESSED"



def test_update_document_status_rejects_unknown_status():
    with pytest.raises(ValueError, match="Unsupported document status"):
        update_document_status(str(ObjectId()), "IN_PROGRESS")


def test_update_document_status_rejects_invalid_id():
    with pytest.raises(ValueError, match="Invalid document ID"):
        update_document_status("not-an-object-id", "PENDING")


def test_update_document_status_returns_false_when_missing(client):
    assert update_document_status(str(ObjectId()), "FAILED") is False


def test_update_document_status_rejects_invalid_transition(client):
    db = get_database()
    document_id = db.documents.insert_one({
        "filename": "test.csv",
        "status": "UPLOADED",
    }).inserted_id

    with pytest.raises(ValueError, match="Invalid document status transition"):
        update_document_status(str(document_id), "PROCESSED")


def test_update_document_status_rejects_transition_from_processed(client):
    db = get_database()
    document_id = db.documents.insert_one({
        "filename": "test.csv",
        "status": "PROCESSED",
    }).inserted_id

    with pytest.raises(ValueError, match="Invalid document status transition"):
        update_document_status(str(document_id), "PENDING")

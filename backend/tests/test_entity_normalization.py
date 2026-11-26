"""
tests/test_entity_normalization.py

Integration tests for description normalization and entity extraction endpoints.
Uses shared fixtures from tests/conftest.py (client, auth_headers, registered_user).
"""

from bson import ObjectId
from fastapi.testclient import TestClient

from app.database.mongodb import get_database


def test_normalize_description_endpoint_success(client: TestClient, auth_headers: dict):
    """POST /api/documents/normalize-description parses raw Indian banking narration."""
    payload = {
        "description": "UPI/512391203912/Swiggy Bangalore/swiggy@icici/Food order"
    }
    response = client.post(
        "/api/documents/normalize-description",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["channel"] == "UPI"
    assert data["reference_id"] == "512391203912"
    assert data["vpa"] == "swiggy@icici"
    assert data["normalized_entity"] == "Swiggy"
    assert data["counterparty_type"] == "MERCHANT"
    assert "512391203912" not in data["clean_description"]


def test_normalize_description_requires_auth(client: TestClient):
    """Endpoint rejects unauthenticated requests with 401."""
    response = client.post(
        "/api/documents/normalize-description",
        json={"description": "ATM CASH WITHDRAWAL"},
    )
    assert response.status_code == 401


def test_get_document_entities_success(client: TestClient, auth_headers: dict, registered_user: dict):
    """GET /api/documents/{id}/entities returns extracted entities for all document transactions."""
    db = get_database()
    user_record = db.users.find_one({"email": registered_user["email"]})
    owner_id = str(user_record["_id"])

    # Insert test document
    doc_res = db.documents.insert_one({
        "filename": "statement.csv",
        "owner_id": owner_id,
        "status": "PROCESSED",
    })
    doc_id = str(doc_res.inserted_id)

    # Insert test transactions
    db.transactions.insert_many([
        {
            "document_id": doc_id,
            "owner_id": owner_id,
            "description": "UPI/111122223333/Zomato/zomato@hdfc/Food",
        },
        {
            "document_id": doc_id,
            "owner_id": owner_id,
            "description": "NEFT-N998877665544-INFOSYS TECHNOLOGIES-SALARY",
        },
    ])

    response = client.get(f"/api/documents/{doc_id}/entities", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == doc_id
    assert data["transaction_count"] == 2
    entities = data["entities"]
    assert entities[0]["normalized_entity"] == "Zomato"
    assert entities[1]["normalized_entity"] == "Infosys"


def test_get_document_entities_invalid_id(client: TestClient, auth_headers: dict):
    """Invalid ObjectId returns 400."""
    response = client.get("/api/documents/invalid-id/entities", headers=auth_headers)
    assert response.status_code == 400


def test_get_document_entities_not_found(client: TestClient, auth_headers: dict):
    """Non-existent document returns 404."""
    missing_id = str(ObjectId())
    response = client.get(f"/api/documents/{missing_id}/entities", headers=auth_headers)
    assert response.status_code == 404

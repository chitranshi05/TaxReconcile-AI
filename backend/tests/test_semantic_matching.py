"""
tests/test_semantic_matching.py

Integration tests for semantic matching and reconciliation semantic matching passes.
Uses shared fixtures from tests/conftest.py.
"""

from bson import ObjectId
from fastapi.testclient import TestClient

from app.database.mongodb import get_database


def test_semantic_similarity_endpoint_success(client: TestClient, auth_headers: dict):
    """POST /api/documents/semantic-similarity calculates domain-aware semantic similarity."""
    payload = {
        "text1": "Office premises lease rental",
        "text2": "Rent payment property",
        "semantic_threshold": 70.0,
    }
    response = client.post(
        "/api/documents/semantic-similarity",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_match"] is True
    assert data["similarity_score"] >= 70.0
    assert "Rent" in data["matched_concepts"]


def test_semantic_similarity_requires_auth(client: TestClient):
    """POST /api/documents/semantic-similarity requires authentication."""
    response = client.post(
        "/api/documents/semantic-similarity",
        json={"text1": "Lease", "text2": "Rent"},
    )
    assert response.status_code == 401


def test_semantic_compare_batch_success(client: TestClient, auth_headers: dict):
    """POST /api/documents/semantic-compare ranks candidate descriptions."""
    payload = {
        "reference_text": "Employee salary disbursement May",
        "candidates": [
            "Monthly grocery expense",
            "Staff payroll wages credit",
            "Electricity utility bill",
        ],
        "semantic_threshold": 70.0,
    }
    response = client.post(
        "/api/documents/semantic-compare",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["candidates_count"] == 3
    assert data["matches_count"] == 1
    top = data["results"][0]
    assert top["candidate"] == "Staff payroll wages credit"
    assert top["is_match"] is True
    assert "Salary" in top["matched_concepts"]


def test_reconciliation_semantic_matching_end_to_end(
    client: TestClient,
    auth_headers: dict,
    registered_user: dict,
):
    """POST /api/reconciliation matches transactions via SEMANTIC_MATCH."""
    db = get_database()
    user = db.users.find_one({"email": registered_user["email"]})
    owner_id = str(user["_id"])

    # Insert Bank Document
    bank_doc_id = db.documents.insert_one({
        "owner_id": owner_id,
        "filename": "bank_statement.csv",
        "status": "PROCESSED",
    }).inserted_id

    # Insert Ledger Document
    ledger_doc_id = db.documents.insert_one({
        "owner_id": owner_id,
        "filename": "company_ledger.csv",
        "status": "PROCESSED",
    }).inserted_id

    # Bank transaction: "Office premises lease rental"
    db.transactions.insert_one({
        "document_id": str(bank_doc_id),
        "owner_id": owner_id,
        "transaction_date": "2026-05-15",
        "description": "Office premises lease rental",
        "amount": 45000.0,
    })

    # Ledger transaction: "Rent payment property"
    db.transactions.insert_one({
        "document_id": str(ledger_doc_id),
        "owner_id": owner_id,
        "transaction_date": "2026-05-15",
        "description": "Rent payment property",
        "amount": 45000.0,
    })

    # Call reconciliation API
    req = {
        "bank_document_id": str(bank_doc_id),
        "ledger_document_id": str(ledger_doc_id),
        "date_tolerance_days": 1,
        "amount_tolerance": 0.0,
        "fuzzy_threshold": 75.0,
        "semantic_threshold": 70.0,
    }
    response = client.post("/api/reconciliation", json=req, headers=auth_headers)
    assert response.status_code == 200
    res_data = response.json()

    assert res_data["summary"]["potential_match_count"] == 1
    assert len(res_data["matches"]) == 1

    match = res_data["matches"][0]
    assert match["status"] == "POTENTIAL_MATCH"
    assert match["match_type"] == "SEMANTIC_MATCH"
    assert match["confidence_score"] >= 0.70
    assert "Rent" in match.get("matched_concepts", [])

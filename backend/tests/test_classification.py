"""
tests/test_classification.py

Integration tests for transaction classification endpoints.
Uses shared fixtures from tests/conftest.py.
"""

from bson import ObjectId
from fastapi.testclient import TestClient

from app.database.mongodb import get_database


def test_classify_transaction_endpoint_success(client: TestClient, auth_headers: dict):
    """POST /api/documents/classify-transaction returns classification and tax head."""
    payload = {
        "description": "UPI/512391203912/Swiggy Bangalore/swiggy@icici/Food",
        "debit": 520.0,
    }
    response = client.post(
        "/api/documents/classify-transaction",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "FOOD_AND_DINING"
    assert data["tax_head"] == "PERSONAL_NON_DEDUCTIBLE"
    assert data["is_tax_deductible"] is False
    assert data["confidence_score"] >= 0.90


def test_classify_batch_endpoint_success(client: TestClient, auth_headers: dict):
    """POST /api/documents/classify-batch classifies multiple transactions with summary."""
    payload = {
        "transactions": [
            {"description": "Infosys Technologies Salary April", "credit": 95000.0},
            {"description": "WeWork monthly office rent", "debit": 35000.0},
            {"description": "Uber rides Mumbai", "debit": 1200.0},
        ]
    }
    response = client.post(
        "/api/documents/classify-batch",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    summary = data["summary"]
    assert summary["total_transactions"] == 3
    assert summary["total_income"] == 95000.0
    assert summary["total_deductible_expense"] == 36200.0  # Rent (35000) + Uber (1200)


def test_classify_transaction_requires_auth(client: TestClient):
    """Classification endpoints reject unauthenticated calls with 401."""
    response = client.post(
        "/api/documents/classify-transaction",
        json={"description": "Salary"},
    )
    assert response.status_code == 401


def test_get_document_classification_success(client: TestClient, auth_headers: dict, registered_user: dict):
    """GET /api/documents/{id}/classification returns full document analysis."""
    db = get_database()
    user_record = db.users.find_one({"email": registered_user["email"]})
    owner_id = str(user_record["_id"])

    # Insert test document
    doc_res = db.documents.insert_one({
        "filename": "bank_statement.csv",
        "owner_id": owner_id,
        "status": "PROCESSED",
    })
    doc_id = str(doc_res.inserted_id)

    # Insert test transactions
    db.transactions.insert_many([
        {
            "document_id": doc_id,
            "owner_id": owner_id,
            "description": "NEFT-N987654321012-INFOSYS-SALARY",
            "credit": 100000.0,
        },
        {
            "document_id": doc_id,
            "owner_id": owner_id,
            "description": "BHARTI AIRTEL BROADBAND BILL",
            "debit": 2000.0,
        },
    ])

    response = client.get(f"/api/documents/{doc_id}/classification", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == doc_id
    assert data["summary"]["total_transactions"] == 2
    assert data["summary"]["total_income"] == 100000.0
    assert data["summary"]["total_deductible_expense"] == 2000.0


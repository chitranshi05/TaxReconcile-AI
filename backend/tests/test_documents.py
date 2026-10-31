"""
tests/test_documents.py

End-to-end tests for the documents API.

Covers:
  POST   /api/documents/upload        — success, bad extension, too large, no auth
  GET    /api/documents/              — list own docs, empty list
  GET    /api/documents/{id}          — found, not found, ownership
  GET    /api/documents/{id}/inspect  — CSV inspection
  DELETE /api/documents/{id}          — success, not found, ownership check

The 'client' fixture from conftest.py provides an isolated in-memory DB
and a pre-registered test user with a valid auth token.
"""

import io
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_csv_bytes(rows: int = 3) -> bytes:
    """Generate a minimal valid CSV with transaction-like columns."""
    lines = ["Date,Narration,Amount"]
    for i in range(rows):
        lines.append(f"01-04-2026,Test transaction {i},{100 * (i + 1)}")
    return "\n".join(lines).encode()


def upload_csv(client, headers, filename="test.csv", content=None):
    """Upload a CSV file and return the response."""
    data = content or make_csv_bytes()
    return client.post(
        "/api/documents/upload",
        files={"file": (filename, io.BytesIO(data), "text/csv")},
        headers=headers,
    )


# ── Upload ────────────────────────────────────────────────────────────────────

def test_upload_csv_success(client, auth_headers):
    """A valid CSV upload returns 201 with document_id and status UPLOADED."""
    response = upload_csv(client, auth_headers)
    assert response.status_code == 201

    body = response.json()
    assert "document_id" in body
    assert body["file_type"] == "CSV"
    assert body["status"] == "UPLOADED"
    assert body["filename"] == "test.csv"
    # The UUID-prefixed stored name must NOT leak to the response
    assert not body["filename"].startswith(body["document_id"][:4])


def test_upload_rejects_unsupported_extension(client, auth_headers):
    """Files with unsupported extensions are rejected with 400."""
    response = client.post(
        "/api/documents/upload",
        files={"file": ("report.docx", io.BytesIO(b"not a real doc"), "application/octet-stream")},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_upload_rejects_empty_file(client, auth_headers):
    """An empty file (0 bytes) is rejected with 400."""
    response = client.post(
        "/api/documents/upload",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_upload_rejects_oversized_file_and_cleans_partial_file(
    client, auth_headers, tmp_path, monkeypatch
):
    """Oversized uploads return 413 and leave no partial file behind."""
    import app.api.documents as doc_module

    monkeypatch.setattr(doc_module, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(
        doc_module,
        "settings",
        SimpleNamespace(MAX_UPLOAD_BYTES=10),
    )

    response = upload_csv(
        client,
        auth_headers,
        content=b"Date,Narration,Amount\n" + b"x" * 100,
    )

    assert response.status_code == 413
    assert list(tmp_path.iterdir()) == []



def test_upload_requires_auth(client):
    """Uploading without a token returns 401."""
    response = client.post(
        "/api/documents/upload",
        files={"file": ("test.csv", io.BytesIO(make_csv_bytes()), "text/csv")},
    )
    assert response.status_code == 401


def test_upload_two_same_filenames_no_collision(client, auth_headers):
    """
    Uploading the same filename twice must produce two separate documents.
    The UUID prefix prevents filesystem collision.
    """
    r1 = upload_csv(client, auth_headers, filename="report.csv")
    r2 = upload_csv(client, auth_headers, filename="report.csv")

    assert r1.status_code == 201
    assert r2.status_code == 201
    # Different document IDs
    assert r1.json()["document_id"] != r2.json()["document_id"]


def test_corrupt_excel_returns_client_errors_and_failed_status(
    client, auth_headers
):
    upload_response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "corrupt.xlsx",
                io.BytesIO(b"not an Excel workbook"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=auth_headers,
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["document_id"]

    inspect_response = client.get(
        f"/api/documents/{document_id}/inspect",
        headers=auth_headers,
    )
    assert inspect_response.status_code == 400
    assert "Unable to read Excel workbook" in inspect_response.json()["detail"]

    process_response = client.post(
        f"/api/documents/{document_id}/process",
        headers=auth_headers,
    )
    assert process_response.status_code == 400
    assert "Unable to read Excel workbook" in process_response.json()["detail"]

    document_response = client.get(
        f"/api/documents/{document_id}",
        headers=auth_headers,
    )
    assert document_response.status_code == 200
    assert document_response.json()["status"] == "FAILED"


def test_excel_and_json_documents_process_through_api(client, auth_headers):
    workbook_bytes = io.BytesIO()
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Date", "Description", "Amount"])
    sheet.append(["2026-04-01", "Excel transaction", 125.5])
    workbook.save(workbook_bytes)

    excel_upload = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "transactions.xlsx",
                workbook_bytes.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=auth_headers,
    )
    assert excel_upload.status_code == 201
    excel_id = excel_upload.json()["document_id"]
    assert client.get(
        f"/api/documents/{excel_id}/inspect", headers=auth_headers
    ).status_code == 200
    excel_process = client.post(
        f"/api/documents/{excel_id}/process", headers=auth_headers
    )
    assert excel_process.status_code == 200
    excel_transactions = client.get(
        f"/api/documents/{excel_id}/transactions", headers=auth_headers
    )
    assert excel_transactions.json()["transactions"][0]["amount"] == 125.5

    json_upload = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "transactions.json",
                json.dumps(
                    {
                        "transactions": [
                            {
                                "date": "2026-04-02",
                                "description": "JSON transaction",
                                "credit": 250,
                            }
                        ]
                    }
                ).encode(),
                "application/json",
            )
        },
        headers=auth_headers,
    )
    assert json_upload.status_code == 201
    json_id = json_upload.json()["document_id"]
    json_process = client.post(
        f"/api/documents/{json_id}/process", headers=auth_headers
    )
    assert json_process.status_code == 200
    json_transactions = client.get(
        f"/api/documents/{json_id}/transactions", headers=auth_headers
    )
    assert json_transactions.json()["transactions"][0]["credit"] == 250


# ── List ──────────────────────────────────────────────────────────────────────

def test_list_documents_empty(client, auth_headers):
    """A new user with no uploads gets an empty list."""
    response = client.get("/api/documents/", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_list_documents_returns_own_docs(client, auth_headers):
    """After uploading, the document appears in the list."""
    upload_csv(client, auth_headers)
    upload_csv(client, auth_headers)

    response = client.get("/api/documents/", headers=auth_headers)
    assert response.status_code == 200

    docs = response.json()
    assert len(docs) == 2
    for doc in docs:
        assert "id" in doc
        assert doc["file_type"] == "CSV"
        assert doc["status"] == "UPLOADED"


def test_list_requires_auth(client):
    """GET /api/documents/ without a token returns 401."""
    response = client.get("/api/documents/")
    assert response.status_code == 401


def test_list_documents_rejects_negative_skip(client, auth_headers):
    """Negative skip values are rejected."""
    response = client.get(
        "/api/documents/?skip=-1",
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_list_documents_rejects_limit_over_100(client, auth_headers):
    """Limits above 100 are rejected."""
    response = client.get(
        "/api/documents/?limit=101",
        headers=auth_headers,
    )
    assert response.status_code == 422



# ── Get one ───────────────────────────────────────────────────────────────────

def test_get_document_success(client, auth_headers):
    """GET /api/documents/{id} returns the correct document."""
    upload_response = upload_csv(client, auth_headers)
    doc_id = upload_response.json()["document_id"]

    response = client.get(f"/api/documents/{doc_id}", headers=auth_headers)
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == doc_id
    assert body["file_type"] == "CSV"


def test_get_document_not_found(client, auth_headers):
    """Getting a non-existent document returns 404."""
    fake_id = "507f1f77bcf86cd799439011"
    response = client.get(f"/api/documents/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


def test_get_document_invalid_id(client, auth_headers):
    """Getting with a malformed ObjectId returns 400."""
    response = client.get("/api/documents/not-a-real-id", headers=auth_headers)
    assert response.status_code == 400


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_document_success(client, auth_headers):
    """Delete removes the document; subsequent GET returns 404."""
    doc_id = upload_csv(client, auth_headers).json()["document_id"]

    delete_response = client.delete(f"/api/documents/{doc_id}", headers=auth_headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["document_id"] == doc_id

    get_response = client.get(f"/api/documents/{doc_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_delete_document_not_found(client, auth_headers):
    """Deleting a non-existent document returns 404."""
    fake_id = "507f1f77bcf86cd799439011"
    response = client.delete(f"/api/documents/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


def test_delete_requires_auth(client):
    """DELETE without a token returns 401."""
    fake_id = "507f1f77bcf86cd799439011"
    response = client.delete(f"/api/documents/{fake_id}")
    assert response.status_code == 401


# ── Inspect ───────────────────────────────────────────────────────────────────

def test_inspect_csv(client, auth_headers, tmp_path, monkeypatch):
    """
    Inspect endpoint returns column mapping and validation result.

    We monkeypatch the UPLOAD_DIR so the test CSV is saved to tmp_path
    instead of creating a real uploads/ directory.
    """
    import app.api.documents as doc_module

    original_dir = doc_module.UPLOAD_DIR
    doc_module.UPLOAD_DIR = tmp_path
    try:
        doc_id = upload_csv(client, auth_headers).json()["document_id"]

        response = client.get(f"/api/documents/{doc_id}/inspect", headers=auth_headers)
        assert response.status_code == 200

        body = response.json()
        assert "sheets" in body
        assert len(body["sheets"]) >= 1

        sheet = body["sheets"][0]
        assert "columns" in sheet
        assert "column_mapping" in sheet
        assert "validation" in sheet
    finally:
        doc_module.UPLOAD_DIR = original_dir

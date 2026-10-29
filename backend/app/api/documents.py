"""
app/api/documents.py

Document management endpoints:

  POST   /api/documents/upload          — upload a file, persist metadata
  GET    /api/documents/                — list caller's documents
  GET    /api/documents/{id}            — get one document's metadata
  GET    /api/documents/{id}/inspect    — preview columns + validate sample rows
  DELETE /api/documents/{id}            — delete metadata and the stored file

Security notes
--------------
- Every route requires a valid JWT (get_current_user dependency).
- Ownership is checked on every per-document operation: a USER can only
  touch their own documents; an ADMIN can touch any document.
- Files are stored with a UUID prefix so two uploads of "report.csv" from
  different users (or the same user at different times) never collide.
- File size is rejected before the file is written to disk.
- Path traversal is prevented by using Path(file.filename).name (basename only).
"""

import uuid
from pathlib import Path

import pandas as pd
from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from app.services.audit_service import log_audit_event

from app.config import settings
from app.database.mongodb import get_database
from app.models.document import create_document
from app.schemas.document import DocumentMetadataResponse
from app.services.auth_dependencies import get_current_user
from app.services.ingestion.column_mapper import detect_columns
from app.services.ingestion.data_validator import validate_transactions
from app.services.ingestion.inspector import inspect_file

router = APIRouter(prefix="/api/documents", tags=["Documents"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_FILE_TYPES = {
    "csv": "CSV",
    "xlsx": "XLSX",
    "xls": "XLS",
    "pdf": "PDF",
    "json": "JSON",
}


def _get_owned_document(document_id: str, current_user: dict) -> dict:
    """
    Fetch a document by ID, enforcing ownership.

    - ADMIN users can access any document.
    - Regular users can only access their own documents.

    Raises 400 if the ID is not a valid ObjectId.
    Raises 404 if the document does not exist or does not belong to this user.
    """
    if not ObjectId.is_valid(document_id):
        raise HTTPException(status_code=400, detail="Invalid document ID.")

    db = get_database()
    query: dict = {"_id": ObjectId(document_id)}

    if current_user.get("role") != "ADMIN":
        query["owner_id"] = str(current_user["_id"])

    document = db.documents.find_one(query)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    return document


# ── Upload ────────────────────────────────────────────────────────────────────


@router.post("/upload", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload a financial document and persist its metadata."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    safe_name = Path(file.filename).name
    extension = Path(safe_name).suffix.lower().lstrip(".")

    if extension not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{extension}. "
            f"Allowed: {', '.join(ALLOWED_FILE_TYPES)}",
        )

    file_type = ALLOWED_FILE_TYPES[extension]
    stored_filename = f"{uuid.uuid4().hex}_{safe_name}"
    file_path = UPLOAD_DIR / stored_filename
    total_size = 0
    chunk_size = 1024 * 1024  # 1 MB per read

    try:
        # Stream the file to disk and enforce the size limit while reading.
        with file_path.open("wb") as destination:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break

                total_size += len(chunk)
                if total_size > settings.MAX_UPLOAD_BYTES:
                    max_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the {max_mb} MB size limit.",
                    )

                destination.write(chunk)

        if total_size == 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty.",
            )

        document = create_document(
            filename=stored_filename,
            original_filename=safe_name,
            file_type=file_type,
            document_type="OTHER",
            source="USER",
            owner_id=str(current_user["_id"]),
        )

        result = get_database().documents.insert_one(document)
        log_audit_event(
            action="DOCUMENT_UPLOADED",
            user_id=str(current_user["_id"]),
            resource_type="document",
            resource_id=str(result.inserted_id),
            details={
                "filename": safe_name,
                "file_type": file_type,
            },
        )

    except HTTPException:
        file_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to save the uploaded document. Please try again.",
        ) from exc
    finally:
        await file.close()

    return {
        "message": "Document uploaded successfully.",
        "document_id": str(result.inserted_id),
        "filename": safe_name,
        "file_type": file_type,
        "status": document["status"],
    }



# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[DocumentMetadataResponse])
def list_documents(
    current_user: dict = Depends(get_current_user),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """
    Return the calling user's documents, newest first.

    ADMIN users see all documents across all users.
    Supports basic pagination via skip / limit query parameters.
    """
    db = get_database()

    query: dict = {}
    if current_user.get("role") != "ADMIN":
        query["owner_id"] = str(current_user["_id"])

    cursor = (
        db.documents.find(query)
        .sort("uploaded_at", -1)
        .skip(skip)
        .limit(limit)
    )

    return [_serialize_document(doc) for doc in cursor]


# ── Get one ───────────────────────────────────────────────────────────────────

@router.get("/{document_id}", response_model=DocumentMetadataResponse)
def get_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return metadata for a single document (ownership enforced)."""
    document = _get_owned_document(document_id, current_user)
    return _serialize_document(document)


# ── Inspect ───────────────────────────────────────────────────────────────────

@router.get("/{document_id}/inspect")
def inspect_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Preview the column structure and validate sample rows of a document.

    Returns sheet names, column list, detected column mapping (e.g. which
    column is the "date", "amount", etc.), and validation results for the
    first 5 rows.

    Only CSV and Excel files are supported here. PDF and JSON inspection
    will be added when those parsers are integrated.
    """
    document = _get_owned_document(document_id, current_user)

    file_path = UPLOAD_DIR / document["filename"]

    try:
        sheets = inspect_file(str(file_path))

        for sheet in sheets:
            sheet["column_mapping"] = detect_columns(sheet["columns"])
            dataframe = pd.DataFrame(sheet["sample"])

            sheet["validation_note"] = (
                "Validation uses the sample rows only. "
                "Full-file validation runs during extraction."
            )

            if not dataframe.empty:
                sheet["validation"] = validate_transactions(
                    dataframe, sheet["column_mapping"]
                )
            else:
                sheet["validation"] = {
                    "valid": False,
                    "total_rows": 0,
                    "valid_rows": 0,
                    "invalid_rows": 0,
                    "errors": [
                        {"row": None, "field": None, "message": "No sample rows available."}
                    ],
                    "warnings": [],
                }
        log_audit_event(
            action="DOCUMENT_INSPECTED",
            user_id=str(current_user["_id"]),
            resource_type="document",
            resource_id=document_id,
            details={
                "filename": document["original_filename"],
                "file_type": document["file_type"],
            },
        )

        return {
            "document_id": document_id,
            "filename": document["original_filename"],
            "file_type": document["file_type"],
            "sheets": sheets,
        }


    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Document file not found on server. It may have been deleted.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to inspect document: {exc}",
        )


# ── Delete ────────────────────────────────────────────────────────────────────


@router.delete("/{document_id}", status_code=200)
def delete_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a document and record the action in the audit log."""
    document = _get_owned_document(document_id, current_user)

    file_path = UPLOAD_DIR / document["filename"]
    if file_path.exists():
        file_path.unlink()

    db = get_database()
    db.documents.delete_one({"_id": ObjectId(document_id)})

    log_audit_event(
        action="DOCUMENT_DELETED",
        user_id=str(current_user["_id"]),
        resource_type="document",
        resource_id=document_id,
        details={
            "filename": document.get("original_filename", document["filename"]),
        },
    )

    return {
        "message": "Document deleted successfully.",
        "document_id": document_id,
    }




# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize_document(doc: dict) -> dict:
    """
    Convert a raw MongoDB document dict into the shape expected by
    DocumentMetadataResponse (string IDs, ISO datetime strings).
    """
    return {
        "id": str(doc["_id"]),
        "filename": doc.get("original_filename", doc["filename"]),
        "file_type": doc["file_type"],
        "document_type": doc.get("document_type", "OTHER"),
        "status": doc.get("status", "UPLOADED"),
        "owner_id": doc.get("owner_id", ""),
        "uploaded_at": doc.get("uploaded_at", "").isoformat()
        if doc.get("uploaded_at")
        else None,
    }
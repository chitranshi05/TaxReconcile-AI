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
from app.services.ingestion.csv_processor import process_csv_file
from app.services.ingestion.transaction_saver import save_valid_transactions
from app.services.ingestion.duplicate_detector import detect_duplicates
from app.services.ingestion.anomaly_detector import detect_anomalies


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


@router.post("/{document_id}/process")
def process_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    database = get_database()

    if not ObjectId.is_valid(document_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid document ID.",
        )

    query = {"_id": ObjectId(document_id)}

    if current_user.get("role") != "ADMIN":
        query["owner_id"] = str(current_user["_id"])

    document = database.documents.find_one(query)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    if document.get("file_type") != "CSV":
        raise HTTPException(
            status_code=400,
            detail="Processing currently supports CSV files only.",
        )

    file_path = UPLOAD_DIR / document["filename"]

    try:
        result = process_csv_file(str(file_path))
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    owner_id = document.get("owner_id")

    if not owner_id:
        raise HTTPException(
            status_code=500,
            detail="Document has no owner_id.",
        )

    # Prevent accidental duplicate processing of the same document.
    if database.transactions.find_one({"document_id": document_id}):
        raise HTTPException(
            status_code=409,
            detail="Transactions have already been saved for this document.",
        )

    try:
        saved_count = save_valid_transactions(
            document_id=document_id,
            owner_id=owner_id,
            transactions=result["transactions"],
        )

        database.documents.update_one(
            {"_id": ObjectId(document_id)},
            {
                "$set": {
                    "status": "PROCESSED",
                    "transaction_count": saved_count,
                    "invalid_row_count": result["invalid_rows"],
                    "processing_errors": result["errors"],
                    "processed_at": __import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc
                    ),
                }
            },
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save processed transactions: {error}",
        )

    return {
        "message": "CSV processing completed.",
        "document_id": document_id,
        "total_rows": result["total_rows"],
        "valid_rows": result["valid_rows"],
        "invalid_rows": result["invalid_rows"],
        "saved_transactions": saved_count,
        "column_mapping": result["column_mapping"],
        "errors": result["errors"],
    }


@router.get("/{document_id}/transactions")
def get_document_transactions(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    database = get_database()

    if not ObjectId.is_valid(document_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid document ID.",
        )

    query = {"_id": ObjectId(document_id)}

    # Users can only access their own documents.
    # Admins can access documents across users.
    if current_user.get("role") != "ADMIN":
        query["owner_id"] = str(current_user["_id"])

    document = database.documents.find_one(query)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    transactions = list(
        database.transactions.find(
            {
                "document_id": document_id,
                "owner_id": document.get("owner_id"),
            },
            {"_id": 0},
        ).sort("transaction_date", 1)
    )

    # Convert MongoDB datetimes to JSON-friendly strings.
    for transaction in transactions:
        transaction_date = transaction.get("transaction_date")
        if transaction_date is not None:
            transaction["transaction_date"] = (
                transaction_date.isoformat()
            )

        created_at = transaction.get("created_at")
        if created_at is not None:
            transaction["created_at"] = created_at.isoformat()

    return {
        "document_id": document_id,
        "filename": document["filename"],
        "transaction_count": len(transactions),
        "transactions": transactions,
        "invalid_row_count": document.get("invalid_row_count", 0),
        "processing_errors": document.get("processing_errors", []),
    }


@router.get("/{document_id}/duplicates")
def get_document_duplicates(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve stored transactions for a document and identify duplicate candidates.
    Flags matching date, normalized description, and amount/debit/credit for review.
    """
    database = get_database()

    if not ObjectId.is_valid(document_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid document ID.",
        )

    query = {"_id": ObjectId(document_id)}

    if current_user.get("role") != "ADMIN":
        query["owner_id"] = str(current_user["_id"])

    document = database.documents.find_one(query)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    transactions = list(
        database.transactions.find(
            {
                "document_id": document_id,
                "owner_id": document.get("owner_id"),
            },
            {"_id": 0},
        ).sort("transaction_date", 1)
    )

    duplicate_result = detect_duplicates(transactions)

    # Convert datetimes to ISO strings for JSON response
    for transaction in duplicate_result["flagged_transactions"]:
        transaction_date = transaction.get("transaction_date")
        if transaction_date is not None and hasattr(transaction_date, "isoformat"):
            transaction["transaction_date"] = transaction_date.isoformat()

        created_at = transaction.get("created_at")
        if created_at is not None and hasattr(created_at, "isoformat"):
            transaction["created_at"] = created_at.isoformat()

    return {
        "document_id": document_id,
        "filename": document["filename"],
        "total_transactions": duplicate_result["total_transactions"],
        "unique_count": duplicate_result["unique_count"],
        "original_count": duplicate_result["original_count"],
        "duplicate_count": duplicate_result["duplicate_count"],
        "duplicate_groups_count": duplicate_result["duplicate_groups_count"],
        "duplicates": duplicate_result["duplicates"],
        "duplicate_groups": duplicate_result["duplicate_groups"],
        "flagged_transactions": duplicate_result["flagged_transactions"],
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
@router.get("/{document_id}/anomalies")
def get_document_anomalies(
    document_id: str,
    iqr_multiplier: float = 1.5,
    min_samples_for_iqr: int = 4,
    frequency_threshold: int = 10,
    round_amount_min: float = 5000.0,
    round_amount_min_occurrences: int = 2,
    separate_debit_credit: bool = True,
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve stored transactions for a document and run anomaly detection.
    Identifies statistical outliers (IQR), unusual debits/credits, repeated
    round sums, and high-frequency transaction bursts for tax review.
    """
    database = get_database()

    if not ObjectId.is_valid(document_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid document ID.",
        )

    query = {"_id": ObjectId(document_id)}

    if current_user.get("role") != "ADMIN":
        query["owner_id"] = str(current_user["_id"])

    document = database.documents.find_one(query)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    transactions = list(
        database.transactions.find(
            {
                "document_id": document_id,
                "owner_id": document.get("owner_id"),
            },
            {"_id": 0},
        ).sort("transaction_date", 1)
    )

    result = detect_anomalies(
        transactions=transactions,
        iqr_multiplier=iqr_multiplier,
        min_samples_for_iqr=min_samples_for_iqr,
        frequency_threshold=frequency_threshold,
        round_amount_min=round_amount_min,
        round_amount_min_occurrences=round_amount_min_occurrences,
        separate_debit_credit=separate_debit_credit,
    )

    # Convert datetimes to ISO strings for JSON output
    for tx in result["flagged_transactions"]:
        tx_date = tx.get("transaction_date")
        if tx_date is not None and hasattr(tx_date, "isoformat"):
            tx["transaction_date"] = tx_date.isoformat()

        created_at = tx.get("created_at")
        if created_at is not None and hasattr(created_at, "isoformat"):
            tx["created_at"] = created_at.isoformat()

    return {
        "document_id": document_id,
        "filename": document["filename"],
        "total_transactions": result["total_transactions"],
        "anomalous_transactions_count": result["anomalous_transactions_count"],
        "normal_transactions_count": result["normal_transactions_count"],
        "anomaly_rate": result["anomaly_rate"],
        "flag_counts": result["flag_counts"],
        "statistics": result["statistics"],
        "anomalies": result["anomalies"],
        "flagged_transactions": result["flagged_transactions"],
        "notes": result["notes"],
        "disclaimer": result["disclaimer"],
    }

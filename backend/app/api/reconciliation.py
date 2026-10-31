from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Response

from app.database.mongodb import get_database
from app.services.auth_dependencies import get_current_user
from app.schemas.reconciliation import ReconciliationRequest
from app.services.reconciliation.reconciliation_engine import reconcile_transactions
from app.services.reconciliation.report_generator import (
    generate_reconciliation_pdf,
    generate_reconciliation_xlsx,
)

router = APIRouter(
    prefix="/api/reconciliation",
    tags=["Reconciliation"],
)


def _serialize_dates(items: list[dict]) -> None:
    """Helper to convert date and datetime fields to ISO strings for JSON output."""
    for item in items:
        if "bank_transaction" in item and isinstance(item["bank_transaction"], dict):
            _serialize_single_tx(item["bank_transaction"])
        if "ledger_transaction" in item and isinstance(item["ledger_transaction"], dict):
            _serialize_single_tx(item["ledger_transaction"])

        _serialize_single_tx(item)


def _serialize_single_tx(tx: dict) -> None:
    for key in ("transaction_date", "created_at"):
        val = tx.get(key)
        if val is not None and hasattr(val, "isoformat"):
            tx[key] = val.isoformat()
    if "_id" in tx and isinstance(tx["_id"], ObjectId):
        tx["_id"] = str(tx["_id"])


@router.post("", status_code=200)
def run_reconciliation(
    request: ReconciliationRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Run bank vs ledger reconciliation between two processed financial statement documents.
    Validates ownership of both documents, matches transactions, and stores review results.
    """
    database = get_database()

    # Validate ObjectId formats
    if not ObjectId.is_valid(request.bank_document_id):
        raise HTTPException(status_code=400, detail="Invalid bank_document_id.")
    if not ObjectId.is_valid(request.ledger_document_id):
        raise HTTPException(status_code=400, detail="Invalid ledger_document_id.")

    if request.bank_document_id == request.ledger_document_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot reconcile a document with itself. Provide distinct bank and ledger documents.",
        )

    user_id = str(current_user["_id"])
    is_admin = current_user.get("role") == "ADMIN"

    # Validate document access and ownership
    bank_query = {"_id": ObjectId(request.bank_document_id)}
    if not is_admin:
        bank_query["owner_id"] = user_id
    bank_doc = database.documents.find_one(bank_query)

    if not bank_doc:
        raise HTTPException(
            status_code=404,
            detail="Bank document not found or you are not authorized to access it.",
        )

    ledger_query = {"_id": ObjectId(request.ledger_document_id)}
    if not is_admin:
        ledger_query["owner_id"] = user_id
    ledger_doc = database.documents.find_one(ledger_query)

    if not ledger_doc:
        raise HTTPException(
            status_code=404,
            detail="Ledger document not found or you are not authorized to access it.",
        )

    if bank_doc.get("owner_id") != ledger_doc.get("owner_id"):
        raise HTTPException(
            status_code=400,
            detail="Both documents must belong to the same owner.",
        )

    # Fetch transactions from MongoDB
    bank_transactions = list(
        database.transactions.find(
            {
                "document_id": request.bank_document_id,
                "owner_id": bank_doc.get("owner_id"),
            },
            {"_id": 0},
        ).sort("transaction_date", 1)
    )

    if not bank_transactions:
        raise HTTPException(
            status_code=400,
            detail="The bank document has no stored transactions. Process the document before reconciling.",
        )

    ledger_transactions = list(
        database.transactions.find(
            {
                "document_id": request.ledger_document_id,
                "owner_id": ledger_doc.get("owner_id"),
            },
            {"_id": 0},
        ).sort("transaction_date", 1)
    )

    if not ledger_transactions:
        raise HTTPException(
            status_code=400,
            detail="The ledger document has no stored transactions. Process the document before reconciling.",
        )

    # Run deterministic reconciliation engine
    result = reconcile_transactions(
        bank_transactions=bank_transactions,
        ledger_transactions=ledger_transactions,
        date_tolerance_days=request.date_tolerance_days,
        amount_tolerance=request.amount_tolerance,
    )

    # Serialize datetimes for JSON & storage
    _serialize_dates(result["matches"])
    _serialize_dates(result["bank_only"])
    _serialize_dates(result["ledger_only"])

    # Persist reconciliation outcome for review
    reconciliation_record = {
        "owner_id": bank_doc.get("owner_id"),
        "bank_document_id": request.bank_document_id,
        "ledger_document_id": request.ledger_document_id,
        "bank_filename": bank_doc.get("filename"),
        "ledger_filename": ledger_doc.get("filename"),
        "date_tolerance_days": request.date_tolerance_days,
        "amount_tolerance": request.amount_tolerance,
        "summary": result["summary"],
        "matches": result["matches"],
        "bank_only": result["bank_only"],
        "ledger_only": result["ledger_only"],
        "created_at": datetime.now(timezone.utc),
    }

    insert_result = database.reconciliations.insert_one(reconciliation_record)
    reconciliation_id = str(insert_result.inserted_id)

    return {
        "reconciliation_id": reconciliation_id,
        "bank_document_id": request.bank_document_id,
        "ledger_document_id": request.ledger_document_id,
        "bank_filename": bank_doc.get("filename"),
        "ledger_filename": ledger_doc.get("filename"),
        "summary": result["summary"],
        "matches": result["matches"],
        "bank_only": result["bank_only"],
        "ledger_only": result["ledger_only"],
    }


@router.get("", status_code=200)
def list_reconciliations(current_user: dict = Depends(get_current_user)):
    """List prior reconciliation runs for the current user."""
    database = get_database()
    query = {}
    if current_user.get("role") != "ADMIN":
        query["owner_id"] = str(current_user["_id"])

    records = list(
        database.reconciliations.find(query)
        .sort("created_at", -1)
    )

    for record in records:
        record["reconciliation_id"] = str(record["_id"])
        del record["_id"]
        created_at = record.get("created_at")
        if created_at is not None and hasattr(created_at, "isoformat"):
            record["created_at"] = created_at.isoformat()

    return {
        "count": len(records),
        "reconciliations": records,
    }


@router.get("/{reconciliation_id}", status_code=200)
def get_reconciliation(
    reconciliation_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Retrieve details of a saved reconciliation by ID."""
    database = get_database()

    if not ObjectId.is_valid(reconciliation_id):
        raise HTTPException(status_code=400, detail="Invalid reconciliation_id.")

    query = {"_id": ObjectId(reconciliation_id)}
    if current_user.get("role") != "ADMIN":
        query["owner_id"] = str(current_user["_id"])

    record = database.reconciliations.find_one(query)
    if not record:
        raise HTTPException(status_code=404, detail="Reconciliation record not found.")

    record["reconciliation_id"] = str(record["_id"])
    del record["_id"]
    created_at = record.get("created_at")
    if created_at is not None and hasattr(created_at, "isoformat"):
        record["created_at"] = created_at.isoformat()

    return record


@router.get("/{reconciliation_id}/report", status_code=200)
def download_reconciliation_report(
    reconciliation_id: str,
    format: str = "xlsx",
    current_user: dict = Depends(get_current_user),
):
    """Download a saved reconciliation as an Excel or PDF report."""
    if not ObjectId.is_valid(reconciliation_id):
        raise HTTPException(status_code=400, detail="Invalid reconciliation_id.")

    if format not in {"xlsx", "pdf"}:
        raise HTTPException(
            status_code=400,
            detail="Unsupported report format. Choose 'xlsx' or 'pdf'.",
        )

    query = {"_id": ObjectId(reconciliation_id)}
    if current_user.get("role") != "ADMIN":
        query["owner_id"] = str(current_user["_id"])

    record = get_database().reconciliations.find_one(query)
    if not record:
        raise HTTPException(status_code=404, detail="Reconciliation record not found.")

    if format == "pdf":
        content = generate_reconciliation_pdf(record)
        media_type = "application/pdf"
    else:
        content = generate_reconciliation_xlsx(record)
        media_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="reconciliation-{reconciliation_id}.{format}"'
            )
        },
    )

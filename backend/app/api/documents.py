from pathlib import Path

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.services.auth_dependencies import get_current_user
import pandas as pd
from app.database.mongodb import get_database
from app.models.document import create_document
from app.services.ingestion.inspector import inspect_file
from app.services.ingestion.data_validator import validate_transactions
from app.services.ingestion.column_mapper import detect_columns
from app.services.ingestion.csv_processor import process_csv_file
from app.services.ingestion.transaction_saver import save_valid_transactions


router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"]
)


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


ALLOWED_FILE_TYPES = {
    "csv": "CSV",
    "xlsx": "XLSX",
    "xls": "XLS",
    "pdf": "PDF",
    "json": "JSON",
}


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file selected."
        )

    extension = Path(file.filename).suffix.lower().replace(".", "")

    if extension not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{extension}"
        )

    file_type = ALLOWED_FILE_TYPES[extension]

    file_path = UPLOAD_DIR / file.filename

    contents = await file.read()

    with open(file_path, "wb") as buffer:
        buffer.write(contents)

    database = get_database()

    document = create_document(
        filename=file.filename,
        document_type="OTHER",
        source="USER",
        file_type=file_type,
        owner_id=str(current_user["_id"]),
)

    result = database.documents.insert_one(document)

    return {
        "message": "Document uploaded successfully",
        "document_id": str(result.inserted_id),
        "filename": file.filename,
        "file_type": file_type,
        "status": document["status"]
    }

@router.get("/{document_id}/inspect")
def inspect_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    database = get_database()

    if not ObjectId.is_valid(document_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid document ID."
        )

    query = {"_id": ObjectId(document_id)}

    if current_user.get("role") != "ADMIN":
        query["owner_id"] = str(current_user["_id"])

    document = database.documents.find_one(query)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    file_path = UPLOAD_DIR / document["filename"]

    try:
        result = inspect_file(str(file_path))
        for sheet in result:
            sheet["column_mapping"] = detect_columns(
                sheet["columns"]
            )
            dataframe = pd.DataFrame(sheet["sample"])
            sheet["validation_note"] = (
        "Validation uses the sample rows only. "
        "Full-file validation will be added in the processing pipeline."
            )
            if not dataframe.empty:
                sheet["validation"] = validate_transactions(
                    dataframe,
                    sheet["column_mapping"]
                )
            else:
                sheet["validation"] = {
                    "valid": False,
                    "total_rows": 0,
                    "valid_rows": 0,
                    "invalid_rows": 0,
                    "errors": [
                        {
                            "row": None,
                            "field": None,
                            "message": "No sample rows available."
                }
            ],
            "warnings": []
        }

        return {
            "document_id": document_id,
            "filename": document["filename"],
            "file_type": document["file_type"],
            "sheets": result
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to inspect document: {str(error)}"
        )


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

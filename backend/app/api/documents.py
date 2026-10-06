from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.database.mongodb import get_database
from app.models.document import create_document


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
    file: UploadFile = File(...)
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
        file_type=file_type
    )

    result = database.documents.insert_one(document)

    return {
        "message": "Document uploaded successfully",
        "document_id": str(result.inserted_id),
        "filename": file.filename,
        "file_type": file_type,
        "status": document["status"]
    }
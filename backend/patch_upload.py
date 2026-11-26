"""Patch documents.py to add BackgroundTasks and pipeline integration."""

with open("app/api/documents.py", "r", newline="", encoding="utf-8") as f:
    content = f.read()

# 1. Fix signature
old_sig = (
    "async def upload_document(\r\n"
    "    file: UploadFile = File(...),\r\n"
    "    current_user: dict = Depends(get_current_user),\r\n"
    "):\r\n"
    '    """Upload a financial document and persist its metadata."""'
)
new_sig = (
    "async def upload_document(\r\n"
    "    background_tasks: BackgroundTasks,\r\n"
    "    file: UploadFile = File(...),\r\n"
    "    current_user: dict = Depends(get_current_user),\r\n"
    "):\r\n"
    '    """Upload a financial document and queue it for automated pipeline processing."""'
)
if old_sig in content:
    content = content.replace(old_sig, new_sig, 1)
    print("OK: Replaced upload_document signature")
else:
    print("MISS: Signature not found")

# 2. Fix return block
old_ret = (
    '    return {\r\n'
    '        "message": "Document uploaded successfully.",\r\n'
    '        "document_id": str(result.inserted_id),\r\n'
    '        "filename": safe_name,\r\n'
    '        "file_type": file_type,\r\n'
    '        "status": document["status"],\r\n'
    '    }'
)
new_ret = (
    '    document_id = str(result.inserted_id)\r\n'
    '    owner_id = str(current_user["_id"])\r\n'
    '\r\n'
    '    # Mark pipeline QUEUED and start background processing\r\n'
    '    if file_type in {"CSV", "XLSX", "JSON"}:\r\n'
    '        get_database().documents.update_one(\r\n'
    '            {"_id": result.inserted_id},\r\n'
    '            {"$set": {"pipeline_status": "QUEUED",\r\n'
    '                      "pipeline_status_updated_at": datetime.now(timezone.utc)}},\r\n'
    '        )\r\n'
    '        background_tasks.add_task(run_document_pipeline, document_id, owner_id)\r\n'
    '\r\n'
    '    return {\r\n'
    '        "message": "Document uploaded. Processing started in the background.",\r\n'
    '        "document_id": document_id,\r\n'
    '        "filename": safe_name,\r\n'
    '        "file_type": file_type,\r\n'
    '        "status": document["status"],\r\n'
    '        "pipeline_status": "QUEUED" if file_type in {"CSV", "XLSX", "JSON"} else "N/A",\r\n'
    '    }'
)
if old_ret in content:
    content = content.replace(old_ret, new_ret, 1)
    print("OK: Replaced return block")
else:
    print("MISS: Return block not found")
    idx = content.find('"Document uploaded successfully."')
    print("Return phrase at index:", idx)
    print("Context:", repr(content[max(0, idx-100):idx+100]))

with open("app/api/documents.py", "w", newline="", encoding="utf-8") as f:
    f.write(content)
print("Done writing file")

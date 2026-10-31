# Tax Reconcile-AI backend

## Local setup

Use Python 3.13, then run these commands from this `backend` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `JWT_SECRET_KEY` in `.env` to a unique random value of at least 32
characters. Generate one with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Configure `MONGODB_URL` and `DATABASE_NAME` for the MongoDB instance that
should hold application data. The server creates the required indexes during
startup and will not be ready until MongoDB is reachable. Configure
`CORS_ORIGINS` for the frontend origins and `MAX_UPLOAD_BYTES` for the upload
limit. Never commit `.env` or use the sample JWT key.

Start the API from this directory so runtime paths and settings are consistent:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Uploads are stored under `backend/uploads`. Ensure that directory is writable
and persisted by the deployment. CSV, XLSX, and JSON files can be processed;
PDF and legacy XLS files can be uploaded but are not transaction-processing
formats. Reconciliation reports are available as XLSX and PDF.

## Tests

Install test dependencies and run the complete backend suite from this
directory:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests replace the MongoDB client with `mongomock` and use a fresh in-memory
database per test. They do not connect to the configured MongoDB server.

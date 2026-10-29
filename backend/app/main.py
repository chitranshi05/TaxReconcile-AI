"""
app/main.py

FastAPI application entry point.

Startup tasks (run once when the server starts):
  - Create MongoDB indexes so email uniqueness is enforced at the database
    level, not just the application level.

CORS:
  - Configured via CORS_ORIGINS in backend/.env so the React dev server
    (localhost:5173) can reach the API.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import ASCENDING

from app.api.auth import router as auth_router

from app.api.documents import router as documents_router
from app.config import settings
from app.database.mongodb import client, get_database
from app.api.reconciliation import router as reconciliation_router
from app.api.anomalies import router as anomalies_router
from app.api.tax_validation import router as tax_validation_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    """
    Code inside the 'with' block runs once at startup before the server
    begins accepting requests. Yield hands control back to FastAPI.
    Code after yield would run at shutdown.
    """
    _create_indexes()
    yield


def _create_indexes() -> None:
    """Create indexes required for users, documents, and audit logs."""
    db = get_database()

    db["users"].create_index(
        [("email", ASCENDING)],
        unique=True,
        name="users_email_unique",
    )

    db["documents"].create_index(
        [("owner_id", ASCENDING)],
        name="documents_owner_id",
    )

    db["documents"].create_index(
        [("status", ASCENDING)],
        name="documents_status",
    )

    db["audit_logs"].create_index(
        [("user_id", ASCENDING), ("created_at", ASCENDING)],
        name="audit_logs_user_created",
    )


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered tax reconciliation and anomaly detection platform for India",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# â”€â”€ CORS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Allows the React frontend dev server to make cross-origin requests.
# In production, replace CORS_ORIGINS with the deployed frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# â”€â”€ Routers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(reconciliation_router)
app.include_router(anomalies_router)
app.include_router(tax_validation_router)



# â”€â”€ Root endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.get("/", tags=["System"])
def root():
    return {
        "message": "Tax Reconcile-AI API is running",
        "status": "success",
    }


@app.get("/health", tags=["System"])
def health_check():
    """
    Returns DB connectivity status.  The frontend uses this to show a
    'server unavailable' banner when the backend is unreachable.
    """
    try:
        client.admin.command("ping")
        return {"status": "healthy", "database": "connected"}
    except Exception:

        return {"status": "unhealthy", "database": "disconnected"}

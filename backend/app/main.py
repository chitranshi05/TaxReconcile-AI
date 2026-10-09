from fastapi import FastAPI

from app.api.documents import router as documents_router
from app.database.mongodb import client
from app.api.auth import router as auth_router

app = FastAPI(
    title="Tax Reconcile-AI",
    description="AI-powered tax reconciliation and anomaly detection platform",
    version="1.0.0"
)


app.include_router(documents_router)
app.include_router(auth_router)

@app.get("/")
def root():
    return {
        "message": "Tax Reconcile-AI API is running",
        "status": "success"
    }


@app.get("/health")
def health_check():
    try:
        client.admin.command("ping")

        return {
            "status": "healthy",
            "database": "connected"
        }

    except Exception:
        return {
            "status": "unhealthy",
            "database": "disconnected"
        }
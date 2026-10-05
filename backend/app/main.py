from fastapi import FastAPI

from app.database.mongodb import client


app = FastAPI(
    title="Tax Reconcile-AI",
    description="AI-powered tax reconciliation and anomaly detection platform",
    version="1.0.0"
)


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
from fastapi import FastAPI

app = FastAPI(
    title="Tax Reconcile-AI",
    description="AI-powered tax reconciliation platform",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "message": "Tax Reconcile-AI API is running"
    }
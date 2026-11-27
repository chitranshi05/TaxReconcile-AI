"""
app/config.py

Central settings object.  All values are read from environment variables
(loaded from backend/.env by python-dotenv at import time).

Adding a new setting:
  1. Add a class attribute with os.getenv() and a sensible default.
  2. Document its purpose with a comment.
  3. Add the variable to backend/.env.example.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_FILE)


class Settings:
    # ── Application metadata ──────────────────────────────────────────────
    APP_NAME: str = os.getenv("APP_NAME", "Tax Reconcile-AI")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")

    # ── MongoDB ───────────────────────────────────────────────────────────
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "tax_reconcile_ai")

    # ── File uploads ──────────────────────────────────────────────────────
    # Maximum allowed upload size in bytes.  Default: 20 MB.
    MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))

    # ── CORS ──────────────────────────────────────────────────────────────
    # Comma-separated list of origins the browser frontend is served from.
    # Example: "http://localhost:5173,https://app.example.com"
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]


settings = Settings()
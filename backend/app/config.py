import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = os.getenv(
        "APP_NAME",
        "Tax Reconcile-AI"
    )

    APP_VERSION: str = os.getenv(
        "APP_VERSION",
        "1.0.0"
    )

    MONGODB_URL: str = os.getenv(
        "MONGODB_URL",
        "mongodb://localhost:27017"
    )

    DATABASE_NAME: str = os.getenv(
        "DATABASE_NAME",
        "tax_reconcile_ai"
    )


settings = Settings()
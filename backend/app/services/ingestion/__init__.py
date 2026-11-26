"""Ingestion service package."""
from app.services.ingestion.anomaly_detector import (
    AnomalyDetector,
    detect_anomalies,
)
from app.services.ingestion.duplicate_detector import (
    detect_duplicates,
)
from app.services.ingestion.entity_normalizer import (
    EntityNormalizer,
    normalize_transaction_entity,
    extract_clean_entity,
)
from app.services.ingestion.transaction_classifier import (
    TransactionClassifier,
    TransactionCategory,
    TaxHead,
    classify_transaction,
    classify_transactions,
    summarize_classification,
)

__all__ = [
    "AnomalyDetector",
    "detect_anomalies",
    "detect_duplicates",
    "EntityNormalizer",
    "normalize_transaction_entity",
    "extract_clean_entity",
    "TransactionClassifier",
    "TransactionCategory",
    "TaxHead",
    "classify_transaction",
    "classify_transactions",
    "summarize_classification",
]

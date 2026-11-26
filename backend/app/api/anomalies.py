from fastapi import APIRouter, Depends
from app.services.auth_dependencies import get_current_user
from app.schemas.anomaly import AnomalyDetectionRequest
from app.schemas.isolation_forest import IsolationForestRequest, IsolationForestResponse
from app.services.ingestion.anomaly_detector import detect_anomalies
from app.services.ingestion.isolation_forest_detector import run_isolation_forest

router = APIRouter(
    prefix="/api/anomalies",
    tags=["Anomalies"],
)


@router.post("/detect", status_code=200)
def analyze_transaction_anomalies(
    request: AnomalyDetectionRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Direct anomaly detection on arbitrary transaction data.
    Analyzes:
    - Statistical IQR outliers (unusually large amounts)
    - Unusual debits or credits
    - Repeated round figures (e.g. ₹50,000, ₹1,00,000)
    - High-frequency transaction bursts
    """
    result = detect_anomalies(
        transactions=request.transactions,
        iqr_multiplier=request.iqr_multiplier,
        min_samples_for_iqr=request.min_samples_for_iqr,
        frequency_threshold=request.frequency_threshold,
        round_amount_min=request.round_amount_min,
        round_amount_min_occurrences=request.round_amount_min_occurrences,
        separate_debit_credit=request.separate_debit_credit,
    )

    # Format datetimes
    for tx in result["flagged_transactions"]:
        tx_date = tx.get("transaction_date")
        if tx_date is not None and hasattr(tx_date, "isoformat"):
            tx["transaction_date"] = tx_date.isoformat()
        created_at = tx.get("created_at")
        if created_at is not None and hasattr(created_at, "isoformat"):
            tx["created_at"] = created_at.isoformat()

    return result


@router.post("/ml-detect", status_code=200, response_model=IsolationForestResponse)
def analyze_isolation_forest(
    request: IsolationForestRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Unsupervised ML anomaly detection using Isolation Forest.

    Detects multivariate outliers across the following feature dimensions:
    - Absolute transaction amount (log-scaled)
    - Day of month and day of week
    - Round-number amount indicator
    - Daily transaction frequency
    - Debit vs. credit direction
    - Z-score of amount within the dataset

    **contamination** controls what fraction of transactions are expected to
    be anomalous. Start at 0.05 (5 %) and adjust based on your dataset.

    Returns each transaction enriched with:
    - `is_ml_anomaly` – boolean flag
    - `ml_anomaly_score` – normalized [0, 1] score (higher = more unusual)
    - `ml_severity` – HIGH / MEDIUM / LOW / NORMAL
    - `ml_reason` – human-readable explanation

    Requires at least `min_samples` transactions to train the model.
    """
    return run_isolation_forest(
        transactions=request.transactions,
        contamination=request.contamination,
        n_estimators=request.n_estimators,
        random_state=request.random_state,
        min_samples=request.min_samples,
    )

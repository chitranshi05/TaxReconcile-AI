from fastapi import APIRouter, Depends
from app.services.auth_dependencies import get_current_user
from app.schemas.anomaly import AnomalyDetectionRequest
from app.services.ingestion.anomaly_detector import detect_anomalies

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

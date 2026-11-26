"""
backend/app/api/explainability.py

API router providing explainability for transaction classification,
reconciliation matches, anomalies, and financial risk assessments.
"""

from fastapi import APIRouter, Depends

from app.services.auth_dependencies import get_current_user
from app.schemas.explainability import (
    BatchExplainRequest,
    BatchExplainResponse,
    MatchExplainRequest,
    MatchExplanationResponse,
    TransactionExplainRequest,
    TransactionExplanationResponse,
)
from app.services.analysis.explainability_service import (
    ExplainabilityService,
    explain_reconciliation_match,
    explain_single_transaction,
)

router = APIRouter(
    prefix="/api/explainability",
    tags=["Explainability"],
)


@router.post("/transaction", status_code=200, response_model=TransactionExplanationResponse)
def explain_transaction(
    request: TransactionExplainRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate a 360-degree, human-friendly explanation for an individual transaction.
    Explains:
    - Why it was matched, marked as a potential match, or left unmatched
    - Why it was flagged by statistical IQR rules or ML Isolation Forest
    - Why it was assigned a financial category and tax head
    - What statutory tax risks apply (Section 269ST, Section 40A(3), Section 68, etc.)
    - Step-by-step audit trail through the evaluation pipeline
    """
    return explain_single_transaction(
        transaction=request.transaction,
        match_info=request.match_info,
        context=request.context,
    )


@router.post("/match", status_code=200, response_model=MatchExplanationResponse)
def explain_match(
    request: MatchExplainRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate an in-depth audit explanation for a specific bank-to-ledger reconciliation match.
    Provides key matching factors, amount comparison, date gap analysis, and recommendations.
    """
    return explain_reconciliation_match(request.match)


@router.post("/batch", status_code=200, response_model=BatchExplainResponse)
def explain_batch(
    request: BatchExplainRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Batch-explain a list of transactions with distribution summary by status and risk level.
    """
    explanations = [
        ExplainabilityService.explain_transaction(tx)
        for tx in request.transactions
    ]

    status_counts: dict[str, int] = {}
    risk_counts: dict[str, int] = {}

    for exp in explanations:
        status = exp.get("primary_status", "UNKNOWN")
        risk = exp.get("risk_assessment", {}).get("risk_level", "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1
        risk_counts[risk] = risk_counts.get(risk, 0) + 1

    return {
        "total_explained": len(explanations),
        "summary_by_status": status_counts,
        "summary_by_risk": risk_counts,
        "explanations": explanations,
    }


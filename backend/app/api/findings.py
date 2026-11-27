"""
backend/app/api/findings.py

API router for Unified Finding Generation and Financial/Tax Risk Scoring.
"""

from fastapi import APIRouter, Depends

from app.services.auth_dependencies import get_current_user
from app.schemas.findings import (
    GenerateFindingsRequest,
    GenerateFindingsResponse,
    ReconciliationRiskScoreRequest,
    ReconciliationRiskScoreResponse,
    TransactionRiskScoreRequest,
    TransactionRiskScoreResponse,
)
from app.services.analysis.finding_generator import FindingGenerator
from app.services.analysis.risk_scorer import RiskScorer

router = APIRouter(
    prefix="/api/findings",
    tags=["Findings & Risk Scoring"],
)


@router.post("/generate", status_code=200, response_model=GenerateFindingsResponse)
def generate_unified_findings(
    request: GenerateFindingsRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Compile discrepancies, anomaly flags, and statutory tax non-compliance
    into a structured, prioritized portfolio of findings with risk scores.
    """
    return FindingGenerator.generate_unified_portfolio(
        reconciliation_result=request.reconciliation_result,
        anomaly_result=request.anomaly_result,
        tax_validation_findings=request.tax_validation_findings,
    )


@router.post("/score-transaction", status_code=200, response_model=TransactionRiskScoreResponse)
def calculate_transaction_risk(
    request: TransactionRiskScoreRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Calculate an explainable financial and statutory tax risk score (0-100)
    for a single transaction across statutory triggers, reconciliation status,
    and anomaly detection signals.
    """
    return RiskScorer.score_transaction(request.transaction)


@router.post("/score-reconciliation", status_code=200, response_model=ReconciliationRiskScoreResponse)
def calculate_reconciliation_run_risk(
    request: ReconciliationRiskScoreRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Calculate an aggregate financial risk score (0-100) and audit health grade (A-F)
    for an entire reconciliation run.
    """
    return RiskScorer.score_reconciliation_run(
        summary=request.summary,
        matches=request.matches,
        bank_only=request.bank_only,
        ledger_only=request.ledger_only,
    )


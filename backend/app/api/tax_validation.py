from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.database.mongodb import get_database
from app.services.auth_dependencies import get_current_user
from app.schemas.tax_validation import (
    DocumentTaxValidationRequest,
    TaxValidationRequest,
)
from app.schemas.tds_discrepancy import AdvancedTDSAnalysisRequest, AdvancedTDSAnalysisResponse
from app.services.tax_validation.tax_rule_engine import (
    DEFAULT_FY_CONFIGS,
    TaxRuleEngine,
    validate_tax_records,
)
from app.services.tax_validation.tds_discrepancy_detector import run_advanced_tds_analysis

router = APIRouter(
    prefix="/api/tax-validation",
    tags=["Tax Validation"],
)


@router.get("/rules", status_code=200)
def list_tax_rules():
    """
    List all supported Indian Financial Years and their statutory tax limits.
    Covers Chapter VI-A deductions, Section 269ST cash limits, and tolerances.
    """
    return {
        "supported_financial_years": list(DEFAULT_FY_CONFIGS.keys()),
        "rules_by_fy": DEFAULT_FY_CONFIGS,
    }


@router.get("/rules/{financial_year}", status_code=200)
def get_tax_rules_for_fy(financial_year: str):
    """
    Retrieve configured tax provisions and limits for a specific Financial Year.
    """
    if financial_year not in DEFAULT_FY_CONFIGS:
        raise HTTPException(
            status_code=404,
            detail=f"Financial Year '{financial_year}' is not configured. Supported: {list(DEFAULT_FY_CONFIGS.keys())}",
        )
    return {
        "financial_year": financial_year,
        "rules": DEFAULT_FY_CONFIGS[financial_year],
    }


@router.post("/validate", status_code=200)
def run_direct_tax_validation(
    request: TaxValidationRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Direct Tax Rule Validation API.
    Audits provided transactions, TDS records, declared income, and deductions
    against Indian Income Tax statutory rules for the selected Financial Year.
    """
    engine = TaxRuleEngine(
        financial_year=request.financial_year,
        custom_rules=request.custom_rules,
    )
    result = engine.validate_all(
        transactions=request.transactions,
        tds_entries=request.tds_entries,
        declared_income=request.declared_income,
        claimed_deductions=request.claimed_deductions,
        is_senior_citizen=request.is_senior_citizen,
    )
    return result


@router.post("/tds-discrepancy", status_code=200, response_model=AdvancedTDSAnalysisResponse)
def run_advanced_tds_discrepancy_analysis(
    request: AdvancedTDSAnalysisRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Advanced TDS Discrepancy Detection (6-pass analysis).

    **Pass 1 — Rate Validation**: Computes expected TDS from gross amount using
    section-specific statutory rates (194A, 194C, 194H, 194I, 194J, etc.) and
    flags deviations beyond tolerance.

    **Pass 2 — Quarter-wise Reconciliation**: Compares 26AS TDS quarter-by-quarter
    against book entries (Q1: Apr-Jun, Q2: Jul-Sep, Q3: Oct-Dec, Q4: Jan-Mar).
    Requires `tds_entries_books`.

    **Pass 3 — Late Deduction / Late Deposit**: Detects TDS deducted in a later
    quarter than the payment date, or deposited after the statutory due date
    (Section 201(1A) interest implications).

    **Pass 4 — Lower Deduction Certificate Conflict**: Flags when TDS is deducted
    at standard rates despite a valid Form 15G/15H or Section 197 certificate.
    Requires `exemption_certificates`.

    **Pass 5 — Multi-Deductor PAN Aggregation**: Aggregates TDS credits per PAN
    and identifies excess credit over tax liability or unusual multi-deductor patterns.

    **Pass 6 — Unclaimed TDS Credit**: Cross-checks 26AS TDS with the ITR TDS
    schedule and flags credits not yet claimed. Requires `itr_tds_schedule`.

    All passes are independent; only passes with sufficient input data are executed.
    """
    return run_advanced_tds_analysis(
        tds_entries_26as=request.tds_entries_26as,
        tds_entries_books=request.tds_entries_books,
        exemption_certificates=request.exemption_certificates,
        itr_tds_schedule=request.itr_tds_schedule,
        declared_income=request.declared_income,
        tax_liability=request.tax_liability,
        financial_year=request.financial_year,
        tolerance=request.tolerance,
    )


@router.post("/documents/{document_id}/validate", status_code=200)
def validate_document_tax_compliance(
    document_id: str,
    request: DocumentTaxValidationRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Run tax compliance and discrepancy audit on a stored financial statement document.
    Cross-verifies stored transactions against declared income, deduction claims,
    and 26AS/AIS TDS records before filing ITR.
    """
    database = get_database()

    if not ObjectId.is_valid(document_id):
        raise HTTPException(status_code=400, detail="Invalid document ID.")

    query = {"_id": ObjectId(document_id)}
    if current_user.get("role") != "ADMIN":
        query["owner_id"] = str(current_user["_id"])

    document = database.documents.find_one(query)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found or unauthorized.")

    transactions = list(
        database.transactions.find(
            {
                "document_id": document_id,
                "owner_id": document.get("owner_id"),
            },
            {"_id": 0},
        ).sort("transaction_date", 1)
    )

    result = validate_tax_records(
        transactions=transactions,
        tds_entries=request.tds_entries,
        declared_income=request.declared_income,
        claimed_deductions=request.claimed_deductions,
        financial_year=request.financial_year,
        custom_rules=request.custom_rules,
        is_senior_citizen=request.is_senior_citizen,
    )

    return {
        "document_id": document_id,
        "filename": document.get("filename"),
        "transaction_count": len(transactions),
        "summary": result["summary"],
        "findings": result["findings"],
        "findings_by_category": result["findings_by_category"],
        "disclaimer": result["disclaimer"],
    }

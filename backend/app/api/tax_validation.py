from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.database.mongodb import get_database
from app.services.auth_dependencies import get_current_user
from app.schemas.tax_validation import (
    DocumentTaxValidationRequest,
    TaxValidationRequest,
)
from app.services.tax_validation.tax_rule_engine import (
    DEFAULT_FY_CONFIGS,
    TaxRuleEngine,
    validate_tax_records,
)

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

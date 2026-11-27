"""
app/services/ingestion/transaction_classifier.py

Intelligent Financial Transaction Classification Engine.

Categorizes bank and ledger transactions into standard financial categories,
sub-categories, and Indian tax heads (P&L and ITR schedules) with explainable
confidence scores using multi-signal heuristics:
1. Canonical Entity resolution (via EntityNormalizer)
2. Keyword & regex rule patterns
3. Transaction direction (Debit vs Credit)
4. Banking channel & metadata signals
"""

from __future__ import annotations

import re
from typing import Any, NamedTuple
from enum import Enum

from app.services.ingestion.entity_normalizer import EntityNormalizer, NormalizedEntityResult


class TaxHead(str, Enum):
    INCOME_FROM_SALARY = "INCOME_FROM_SALARY"
    PROFITS_AND_GAINS_OF_BUSINESS_OR_PROFESSION = "PROFITS_AND_GAINS_OF_BUSINESS_OR_PROFESSION"
    INCOME_FROM_HOUSE_PROPERTY = "INCOME_FROM_HOUSE_PROPERTY"
    CAPITAL_GAINS = "CAPITAL_GAINS"
    INCOME_FROM_OTHER_SOURCES = "INCOME_FROM_OTHER_SOURCES"
    BUSINESS_EXPENSE_DEDUCTIBLE = "BUSINESS_EXPENSE_DEDUCTIBLE"
    PERSONAL_NON_DEDUCTIBLE = "PERSONAL_NON_DEDUCTIBLE"
    STATUTORY_TAX_PAYMENT = "STATUTORY_TAX_PAYMENT"
    TRANSFERS_AND_CONTRA = "TRANSFERS_AND_CONTRA"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class TransactionCategory(str, Enum):
    # Income Categories
    SALARY = "SALARY"
    BUSINESS_INCOME = "BUSINESS_INCOME"
    INTEREST_INCOME = "INTEREST_INCOME"
    DIVIDEND_INCOME = "DIVIDEND_INCOME"
    RENTAL_INCOME = "RENTAL_INCOME"
    CAPITAL_GAINS = "CAPITAL_GAINS"

    # Business Operating Expenses
    PROFESSIONAL_FEES = "PROFESSIONAL_FEES"
    RENT_EXPENSE = "RENT_EXPENSE"
    UTILITIES = "UTILITIES"
    OFFICE_SUPPLIES = "OFFICE_SUPPLIES"
    TRAVEL_AND_CONVEYANCE = "TRAVEL_AND_CONVEYANCE"
    ADVERTISING_AND_MARKETING = "ADVERTISING_AND_MARKETING"
    CONTRACTOR_PAYMENTS = "CONTRACTOR_PAYMENTS"

    # Personal / Discretionary Expenses
    FOOD_AND_DINING = "FOOD_AND_DINING"
    ENTERTAINMENT = "ENTERTAINMENT"
    SHOPPING_AND_RETAIL = "SHOPPING_AND_RETAIL"
    HEALTH_AND_MEDICAL = "HEALTH_AND_MEDICAL"

    # Banking, Statutory & Transfers
    BANK_CHARGES = "BANK_CHARGES"
    TAX_PAYMENT = "TAX_PAYMENT"
    LOAN_AND_EMI = "LOAN_AND_EMI"
    INVESTMENT = "INVESTMENT"
    TRANSFERS_AND_CONTRA = "TRANSFERS_AND_CONTRA"

    UNCATEGORIZED = "UNCATEGORIZED"


class ClassificationResult(NamedTuple):
    category: str
    sub_category: str
    tax_head: str
    confidence_score: float
    is_tax_deductible: bool | None
    classification_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "sub_category": self.sub_category,
            "tax_head": self.tax_head,
            "confidence_score": self.confidence_score,
            "is_tax_deductible": self.is_tax_deductible,
            "classification_reason": self.classification_reason,
        }


# Known Entity -> Category mapping
ENTITY_CATEGORY_MAP: dict[str, tuple[TransactionCategory, str, TaxHead, bool | None]] = {
    # Food & Dining
    "Swiggy": (TransactionCategory.FOOD_AND_DINING, "Food Delivery", TaxHead.PERSONAL_NON_DEDUCTIBLE, False),
    "Zomato": (TransactionCategory.FOOD_AND_DINING, "Food Delivery", TaxHead.PERSONAL_NON_DEDUCTIBLE, False),
    "Starbucks": (TransactionCategory.FOOD_AND_DINING, "Cafe & Beverage", TaxHead.PERSONAL_NON_DEDUCTIBLE, False),
    "McDonald's": (TransactionCategory.FOOD_AND_DINING, "Fast Food", TaxHead.PERSONAL_NON_DEDUCTIBLE, False),

    # Travel & Conveyance
    "Uber": (TransactionCategory.TRAVEL_AND_CONVEYANCE, "Cab & Rideshare", TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE, True),
    "Ola": (TransactionCategory.TRAVEL_AND_CONVEYANCE, "Cab & Rideshare", TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE, True),

    # Shopping & Retail
    "Amazon": (TransactionCategory.SHOPPING_AND_RETAIL, "E-Commerce", TaxHead.PERSONAL_NON_DEDUCTIBLE, False),
    "Flipkart": (TransactionCategory.SHOPPING_AND_RETAIL, "E-Commerce", TaxHead.PERSONAL_NON_DEDUCTIBLE, False),
    "Myntra": (TransactionCategory.SHOPPING_AND_RETAIL, "Apparel", TaxHead.PERSONAL_NON_DEDUCTIBLE, False),

    # Entertainment & Digital
    "Netflix": (TransactionCategory.ENTERTAINMENT, "Streaming Video", TaxHead.PERSONAL_NON_DEDUCTIBLE, False),
    "Spotify": (TransactionCategory.ENTERTAINMENT, "Streaming Music", TaxHead.PERSONAL_NON_DEDUCTIBLE, False),

    # Tech & Cloud Infrastructure (Business Office Supplies / Tech)
    "Google": (TransactionCategory.OFFICE_SUPPLIES, "Cloud & Software", TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE, True),
    "Microsoft": (TransactionCategory.OFFICE_SUPPLIES, "Cloud & Software", TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE, True),
    "Apple": (TransactionCategory.OFFICE_SUPPLIES, "Hardware & Software", TaxHead.PERSONAL_NON_DEDUCTIBLE, False),

    # Utilities & Telecom
    "Bharti Airtel": (TransactionCategory.UTILITIES, "Telecom & Internet", TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE, True),
    "Reliance Jio": (TransactionCategory.UTILITIES, "Telecom & Internet", TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE, True),

    # Statutory & Tax
    "Income Tax Department": (TransactionCategory.TAX_PAYMENT, "Direct Tax", TaxHead.STATUTORY_TAX_PAYMENT, False),
    "GST Department": (TransactionCategory.TAX_PAYMENT, "Indirect Tax", TaxHead.STATUTORY_TAX_PAYMENT, False),
    "EPFO": (TransactionCategory.TAX_PAYMENT, "Provident Fund", TaxHead.STATUTORY_TAX_PAYMENT, False),
}

# Rule Patterns for Keyword matching: (regex, category, sub_category, tax_head, is_deductible, confidence)
KEYWORD_RULES = [
    # Salary / Payroll
    (
        r"\b(?:salary|payroll|wages|remuneration|stipend)\b",
        TransactionCategory.SALARY,
        "Employment Income",
        TaxHead.INCOME_FROM_SALARY,
        None,
        0.90,
    ),
    # Interest
    (
        r"\b(?:interest|int\.pd|int\.cr|fd interest|sb int)\b",
        TransactionCategory.INTEREST_INCOME,
        "Bank Interest",
        TaxHead.INCOME_FROM_OTHER_SOURCES,
        None,
        0.92,
    ),
    # Dividend
    (
        r"\b(?:dividend|div\.cr|div payout)\b",
        TransactionCategory.DIVIDEND_INCOME,
        "Corporate Dividend",
        TaxHead.INCOME_FROM_OTHER_SOURCES,
        None,
        0.90,
    ),
    # Professional Fees / Legal / Consulting
    (
        r"\b(?:consulting|consultant|legal fee|retainer|professional fee|audit fee|retainer fee)\b",
        TransactionCategory.PROFESSIONAL_FEES,
        "Consultancy & Legal",
        TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE,
        True,
        0.88,
    ),
    # Rent Expense / Co-working
    (
        r"\b(?:office rent|house rent|we work|wework|coworking|rent payment|monthly rent)\b",
        TransactionCategory.RENT_EXPENSE,
        "Office Rent",
        TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE,
        True,
        0.88,
    ),
    # Advertising & Marketing
    (
        r"\b(?:google ads|facebook ads|meta ads|advertising|marketing agency|promotions)\b",
        TransactionCategory.ADVERTISING_AND_MARKETING,
        "Digital Advertising",
        TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE,
        True,
        0.88,
    ),
    # Travel / Airlines / Hotels
    (
        r"\b(?:indigo|air india|vistara|flight|hotel|booking\.com|makemytrip|cleartrip|irctc|railway)\b",
        TransactionCategory.TRAVEL_AND_CONVEYANCE,
        "Air & Rail Travel",
        TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE,
        True,
        0.85,
    ),
    # Health & Medical
    (
        r"\b(?:apollo|pharmeasy|1mg|hospital|pharmacy|clinic|medical|health insurance)\b",
        TransactionCategory.HEALTH_AND_MEDICAL,
        "Healthcare & Pharmacy",
        TaxHead.PERSONAL_NON_DEDUCTIBLE,
        False,
        0.85,
    ),
    # Bank Charges
    (
        r"\b(?:sms alert|annual fee|debit card fee|maintenance charge|folio charges|service fee)\b",
        TransactionCategory.BANK_CHARGES,
        "Bank Service Charges",
        TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE,
        True,
        0.88,
    ),
    # Loan & EMI
    (
        r"\b(?:emi|loan repayment|home loan|auto loan|personal loan|hdfc loan)\b",
        TransactionCategory.LOAN_AND_EMI,
        "Loan Installment",
        TaxHead.NOT_APPLICABLE,
        False,
        0.85,
    ),
    # Investment
    (
        r"\b(?:mutual fund|zerodha|groww|upstox|sip|ppf|nps|fixed deposit|fd booking)\b",
        TransactionCategory.INVESTMENT,
        "Securities & Deposits",
        TaxHead.NOT_APPLICABLE,
        False,
        0.88,
    ),
    # Transfers / Cash / Contra
    (
        r"\b(?:atm wdl|cash wdl|self transfer|funds transfer to self|credit card bill|cc payment)\b",
        TransactionCategory.TRANSFERS_AND_CONTRA,
        "Internal Transfer",
        TaxHead.TRANSFERS_AND_CONTRA,
        None,
        0.90,
    ),
]


class TransactionClassifier:
    """
    Classifies transactions into financial categories and statutory tax heads.
    """

    def __init__(self, normalizer: EntityNormalizer | None = None):
        self.normalizer = normalizer or EntityNormalizer()

    def classify(self, transaction: dict[str, Any]) -> ClassificationResult:
        """
        Classify a single transaction dict.

        Inspects:
        - description / narration
        - amount / debit / credit / direction
        - channel signals
        """
        raw_desc = str(transaction.get("description") or "").strip()
        is_credit = self._is_credit_transaction(transaction)

        # 1. Normalize entity and extract clean tokens
        entity_res = self.normalizer.normalize(raw_desc)
        norm_entity = entity_res.normalized_entity
        clean_desc = entity_res.clean_description.lower()
        raw_lower = raw_desc.lower()

        # 2. Channel-based direct mapping
        if entity_res.channel == "INTEREST":
            return ClassificationResult(
                category=TransactionCategory.INTEREST_INCOME.value,
                sub_category="Bank Interest",
                tax_head=TaxHead.INCOME_FROM_OTHER_SOURCES.value,
                confidence_score=0.95,
                is_tax_deductible=None,
                classification_reason="Identified bank interest credit via INTEREST channel signal.",
            )

        if entity_res.channel == "CHARGES":
            return ClassificationResult(
                category=TransactionCategory.BANK_CHARGES.value,
                sub_category="Bank Service Charge",
                tax_head=TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE.value,
                confidence_score=0.92,
                is_tax_deductible=True,
                classification_reason="Identified bank fee via CHARGES channel signal.",
            )

        if entity_res.channel == "ATM":
            return ClassificationResult(
                category=TransactionCategory.TRANSFERS_AND_CONTRA.value,
                sub_category="Cash Withdrawal",
                tax_head=TaxHead.TRANSFERS_AND_CONTRA.value,
                confidence_score=0.95,
                is_tax_deductible=None,
                classification_reason="Identified cash withdrawal via ATM channel.",
            )

        # 3. Known Entity Direct Mapping
        if norm_entity in ENTITY_CATEGORY_MAP:
            cat, sub_cat, tax_hd, deductible = ENTITY_CATEGORY_MAP[norm_entity]

            # Special case: If credit from a corporate entity, it might be business income or salary
            if is_credit and entity_res.counterparty_type == "CORPORATE":
                if any(w in raw_lower for w in ["salary", "payroll", "wages"]):
                    return ClassificationResult(
                        category=TransactionCategory.SALARY.value,
                        sub_category="Employment Salary",
                        tax_head=TaxHead.INCOME_FROM_SALARY.value,
                        confidence_score=0.96,
                        is_tax_deductible=None,
                        classification_reason=f"Credit from employer {norm_entity} with salary narration.",
                    )
                else:
                    return ClassificationResult(
                        category=TransactionCategory.BUSINESS_INCOME.value,
                        sub_category="Client Receipt",
                        tax_head=TaxHead.PROFITS_AND_GAINS_OF_BUSINESS_OR_PROFESSION.value,
                        confidence_score=0.88,
                        is_tax_deductible=None,
                        classification_reason=f"Corporate credit from {norm_entity} treated as business revenue.",
                    )

            return ClassificationResult(
                category=cat.value,
                sub_category=sub_cat,
                tax_head=tax_hd.value,
                confidence_score=0.92,
                is_tax_deductible=deductible,
                classification_reason=f"Matched canonical entity '{norm_entity}' in merchant registry.",
            )

        # 4. Keyword & Regex Rule Matching
        for pattern, cat, sub_cat, tax_hd, deductible, conf in KEYWORD_RULES:
            if re.search(pattern, raw_lower) or re.search(pattern, clean_desc):
                # Adjust confidence if direction matches semantic expectation
                if cat == TransactionCategory.SALARY and not is_credit:
                    # Salary paid out to staff -> Business Expense
                    return ClassificationResult(
                        category=TransactionCategory.SALARY.value,
                        sub_category="Payroll Expense",
                        tax_head=TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE.value,
                        confidence_score=conf,
                        is_tax_deductible=True,
                        classification_reason="Debit transaction matching payroll keyword treated as staff salary expense.",
                    )

                if cat in (
                    TransactionCategory.SALARY,
                    TransactionCategory.INTEREST_INCOME,
                    TransactionCategory.DIVIDEND_INCOME,
                ) and is_credit:
                    conf = min(1.0, conf + 0.05)

                return ClassificationResult(
                    category=cat.value,
                    sub_category=sub_cat,
                    tax_head=tax_hd.value,
                    confidence_score=conf,
                    is_tax_deductible=deductible,
                    classification_reason=f"Matched financial keyword rule for {cat.value}.",
                )

        # 5. Direction-based Inferred Fallbacks
        if is_credit:
            if entity_res.counterparty_type == "CORPORATE":
                return ClassificationResult(
                    category=TransactionCategory.BUSINESS_INCOME.value,
                    sub_category="Corporate Inward Remittance",
                    tax_head=TaxHead.PROFITS_AND_GAINS_OF_BUSINESS_OR_PROFESSION.value,
                    confidence_score=0.75,
                    is_tax_deductible=None,
                    classification_reason=f"Inward remittance from corporate entity '{norm_entity}'.",
                )
            return ClassificationResult(
                category=TransactionCategory.BUSINESS_INCOME.value,
                sub_category="Other Inward Receipt",
                tax_head=TaxHead.INCOME_FROM_OTHER_SOURCES.value,
                confidence_score=0.60,
                is_tax_deductible=None,
                classification_reason="Unspecified credit transaction categorized as general inward receipt.",
            )

        # Debit fallbacks
        if entity_res.counterparty_type == "CORPORATE":
            return ClassificationResult(
                category=TransactionCategory.CONTRACTOR_PAYMENTS.value,
                sub_category="Vendor Payment",
                tax_head=TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE.value,
                confidence_score=0.65,
                is_tax_deductible=True,
                classification_reason=f"Outward payment to corporate counterparty '{norm_entity}'.",
            )

        if entity_res.channel == "POS":
            return ClassificationResult(
                category=TransactionCategory.SHOPPING_AND_RETAIL.value,
                sub_category="POS Merchant Swipe",
                tax_head=TaxHead.PERSONAL_NON_DEDUCTIBLE.value,
                confidence_score=0.65,
                is_tax_deductible=False,
                classification_reason="Card swipe at point-of-sale terminal categorized as retail purchase.",
            )

        return ClassificationResult(
            category=TransactionCategory.UNCATEGORIZED.value,
            sub_category="General Transaction",
            tax_head=TaxHead.NOT_APPLICABLE.value,
            confidence_score=0.30,
            is_tax_deductible=None,
            classification_reason="Insufficient merchant or keyword signals to determine financial category.",
        )

    def classify_all(self, transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Classify a list of transactions, returning enriched dictionaries.
        """
        results = []
        for tx in transactions:
            tx_copy = dict(tx)
            classification = self.classify(tx)
            tx_copy.update(classification.to_dict())
            results.append(tx_copy)
        return results

    def summarize(self, classified_transactions: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Generate aggregate category and tax breakdown metrics across classified transactions.
        """
        total_tx = len(classified_transactions)
        category_breakdown: dict[str, dict[str, Any]] = {}
        tax_head_breakdown: dict[str, dict[str, Any]] = {}
        total_deductible_expense = 0.0
        total_non_deductible_expense = 0.0
        total_income = 0.0

        for tx in classified_transactions:
            cat = tx.get("category", TransactionCategory.UNCATEGORIZED.value)
            tax_head = tx.get("tax_head", TaxHead.NOT_APPLICABLE.value)
            amt = abs(float(tx.get("amount") or tx.get("debit") or tx.get("credit") or 0.0))
            is_credit = self._is_credit_transaction(tx)

            # Category metrics
            if cat not in category_breakdown:
                category_breakdown[cat] = {"count": 0, "total_amount": 0.0}
            category_breakdown[cat]["count"] += 1
            category_breakdown[cat]["total_amount"] = round(category_breakdown[cat]["total_amount"] + amt, 2)

            # Tax head metrics
            if tax_head not in tax_head_breakdown:
                tax_head_breakdown[tax_head] = {"count": 0, "total_amount": 0.0}
            tax_head_breakdown[tax_head]["count"] += 1
            tax_head_breakdown[tax_head]["total_amount"] = round(tax_head_breakdown[tax_head]["total_amount"] + amt, 2)

            # Totals
            if is_credit:
                total_income = round(total_income + amt, 2)
            else:
                if tx.get("is_tax_deductible") is True:
                    total_deductible_expense = round(total_deductible_expense + amt, 2)
                elif tx.get("is_tax_deductible") is False:
                    total_non_deductible_expense = round(total_non_deductible_expense + amt, 2)

        categorized_count = sum(1 for tx in classified_transactions if tx.get("category") != TransactionCategory.UNCATEGORIZED.value)
        coverage_rate = round((categorized_count / max(total_tx, 1)) * 100, 2)

        return {
            "total_transactions": total_tx,
            "categorized_count": categorized_count,
            "uncategorized_count": total_tx - categorized_count,
            "category_coverage_rate": coverage_rate,
            "total_income": total_income,
            "total_deductible_expense": total_deductible_expense,
            "total_non_deductible_expense": total_non_deductible_expense,
            "category_breakdown": category_breakdown,
            "tax_head_breakdown": tax_head_breakdown,
        }

    @staticmethod
    def _is_credit_transaction(tx: dict[str, Any]) -> bool:
        """Determine if transaction represents an inflow/credit."""
        credit = tx.get("credit")
        if credit is not None and float(credit or 0) > 0:
            return True
        debit = tx.get("debit")
        if debit is not None and float(debit or 0) > 0:
            return False
        amount = tx.get("amount")
        if amount is not None:
            # Positive amounts conventionally credit, or signed
            return float(amount) > 0
        return False


_default_classifier = TransactionClassifier()


def classify_transaction(transaction: dict[str, Any]) -> dict[str, Any]:
    """Convenience helper to classify a single transaction."""
    return _default_classifier.classify(transaction).to_dict()


def classify_transactions(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convenience helper to classify multiple transactions."""
    return _default_classifier.classify_all(transactions)


def summarize_classification(classified_transactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Convenience helper to generate classification summary metrics."""
    return _default_classifier.summarize(classified_transactions)

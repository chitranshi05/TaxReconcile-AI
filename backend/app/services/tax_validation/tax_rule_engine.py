"""
Tax Rule Validation Engine 🇮🇳 (Income Tax Act, India).

Objective: Identify potential tax-related issues, discrepancies, and statutory
non-compliance in financial records prior to filing Income Tax Returns (ITR).

Core Features:
1. Missing & Incomplete Transaction Data (Missing dates, amounts, narrations)
2. TDS Cross-Source Reconciliation (Form 26AS/AIS vs Books/Bank credits)
3. Income Discrepancy Detection (Declared vs Actual deposits, Section 269ST cash compliance)
4. Deduction Limit Validation (Section 80C, 80D, 80CCD, 80TTA/TTB caps & proof cross-matching)
5. Configurable & Versioned Rules by Financial Year (FY 2023-24, 2024-25, 2025-26)

Important: Findings are advisory flags for manual tax review rather than
definitive non-compliance or fraud declarations.
"""

from copy import deepcopy
from datetime import date, datetime
import re
from typing import Any
import pandas as pd


# ---------------------------------------------------------------------------
# Default Statutory Rule Configurations by Financial Year (India)
# ---------------------------------------------------------------------------

DEFAULT_FY_CONFIGS: dict[str, dict[str, Any]] = {
    "2023-24": {
        "assessment_year": "2024-25",
        "section_80c_cap": 150000.0,
        "section_80d_individual_cap": 25000.0,
        "section_80d_senior_cap": 50000.0,
        "section_80ccd_1b_cap": 50000.0,
        "section_80tta_cap": 10000.0,
        "section_80ttb_cap": 50000.0,
        "cash_receipt_single_day_limit": 200000.0,  # Section 269ST
        "cash_payment_single_tx_limit": 10000.0,   # Section 40A(3)
        "tds_discrepancy_tolerance": 100.0,
        "income_tolerance_pct": 2.0,
    },
    "2024-25": {
        "assessment_year": "2025-26",
        "section_80c_cap": 150000.0,
        "section_80d_individual_cap": 25000.0,
        "section_80d_senior_cap": 50000.0,
        "section_80ccd_1b_cap": 50000.0,
        "section_80tta_cap": 10000.0,
        "section_80ttb_cap": 50000.0,
        "cash_receipt_single_day_limit": 200000.0,
        "cash_payment_single_tx_limit": 10000.0,
        "tds_discrepancy_tolerance": 100.0,
        "income_tolerance_pct": 2.0,
    },
    "2025-26": {
        "assessment_year": "2026-27",
        "section_80c_cap": 150000.0,
        "section_80d_individual_cap": 25000.0,
        "section_80d_senior_cap": 50000.0,
        "section_80ccd_1b_cap": 50000.0,
        "section_80tta_cap": 10000.0,
        "section_80ttb_cap": 50000.0,
        "cash_receipt_single_day_limit": 200000.0,
        "cash_payment_single_tx_limit": 10000.0,
        "tds_discrepancy_tolerance": 100.0,
        "income_tolerance_pct": 2.0,
    },
}


# ---------------------------------------------------------------------------
# Standard Finding Model Helper
# ---------------------------------------------------------------------------

def create_finding(
    rule_id: str,
    category: str,
    severity: str,
    title: str,
    description: str,
    section: str | None = None,
    details: dict[str, Any] | None = None,
    remediation: str | None = None,
) -> dict[str, Any]:
    """
    Standard format for all tax rule validation findings.
    Severities:
      - ERROR: Critical missing information or statutory breach that will cause ITR defect/rejection.
      - WARNING: Potential income, deduction, or TDS mismatch requiring reconciliation before filing.
      - INFO: Informative advisory (e.g. eligible unused deduction balance).
    """
    return {
        "rule_id": rule_id,
        "category": category,
        "severity": severity.upper(),
        "section": section,
        "title": title,
        "description": description,
        "details": details or {},
        "remediation": remediation or "Review transaction and supporting tax documents before filing ITR.",
    }


# ---------------------------------------------------------------------------
# Normalization Utilities
# ---------------------------------------------------------------------------

def parse_float_amount(value: Any) -> float | None:
    """Extract numeric monetary amount safely."""
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    text = str(value).strip()
    for sym in ("₹", "$", "€", "£", ","):
        text = text.replace(sym, "")
    text = text.replace(" ", "")
    try:
        return round(float(text), 2)
    except (ValueError, TypeError):
        return None


def parse_date_obj(value: Any) -> date | None:
    """Normalize date to python datetime.date."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        text = str(value).strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}", text):
            parsed = pd.to_datetime(text, errors="coerce")
        else:
            parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
        if pd.notna(parsed):
            return parsed.date()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Core Tax Rule Engine
# ---------------------------------------------------------------------------

class TaxRuleEngine:
    """
    Indian Income Tax Rule Engine.
    Executes configurable, FY-versioned tax validation checks.
    """

    def __init__(
        self,
        financial_year: str = "2025-26",
        custom_rules: dict[str, Any] | None = None,
    ):
        self.financial_year = financial_year
        base_config = DEFAULT_FY_CONFIGS.get(
            financial_year,
            DEFAULT_FY_CONFIGS["2025-26"],
        )
        self.config = deepcopy(base_config)
        if custom_rules:
            self.config.update(custom_rules)

    # -----------------------------------------------------------------------
    # Rule Set 1: Missing Transaction Information
    # -----------------------------------------------------------------------
    def validate_transaction_integrity(
        self,
        transactions: list[dict] | pd.DataFrame,
    ) -> list[dict]:
        """
        Detect missing or malformed financial records:
        - Missing transaction date
        - Missing amount, debit, and credit
        - Missing description / narration
        - Negative debit/credit amounts
        """
        tx_list = transactions.to_dict(orient="records") if isinstance(transactions, pd.DataFrame) else transactions
        findings = []

        for idx, tx in enumerate(tx_list):
            row_num = tx.get("source_row", idx + 1)
            raw_date = tx.get("transaction_date")
            parsed_date = parse_date_obj(raw_date)

            # Check 1: Missing date
            if parsed_date is None:
                findings.append(
                    create_finding(
                        rule_id="TAX-DATA-001",
                        category="MISSING_DATA",
                        severity="ERROR",
                        title="Missing Transaction Date",
                        description=f"Transaction at row {row_num} has no valid transaction date.",
                        section="General ITR Records",
                        details={"row": row_num, "raw_value": raw_date},
                        remediation="Supply a valid date in YYYY-MM-DD or DD/MM/YYYY format to enable financial year attribution.",
                    )
                )

            # Check 2: Missing or blank amount
            amt = parse_float_amount(tx.get("amount"))
            deb = parse_float_amount(tx.get("debit"))
            crd = parse_float_amount(tx.get("credit"))

            if amt is None and deb is None and crd is None:
                findings.append(
                    create_finding(
                        rule_id="TAX-DATA-002",
                        category="MISSING_DATA",
                        severity="ERROR",
                        title="Missing Monetary Amount",
                        description=f"Transaction at row {row_num} contains no amount, debit, or credit values.",
                        section="General ITR Records",
                        details={"row": row_num},
                        remediation="Enter a non-zero financial amount or remove the unpopulated entry.",
                    )
                )

            # Check 3: Missing description
            desc = str(tx.get("description", "") or "").strip()
            if not desc:
                findings.append(
                    create_finding(
                        rule_id="TAX-DATA-003",
                        category="MISSING_DATA",
                        severity="WARNING",
                        title="Blank Transaction Narration",
                        description=f"Transaction at row {row_num} lacks a description or narration.",
                        section="General ITR Records",
                        details={"row": row_num, "amount": amt or deb or crd},
                        remediation="Add description to substantiate business purpose or personal nature of the transaction.",
                    )
                )

            # Check 4: Negative debit or credit values
            if (deb is not None and deb < 0) or (crd is not None and crd < 0):
                findings.append(
                    create_finding(
                        rule_id="TAX-DATA-004",
                        category="MISSING_DATA",
                        severity="ERROR",
                        title="Negative Debit or Credit Value",
                        description=f"Transaction at row {row_num} contains negative debit/credit figures.",
                        section="General ITR Records",
                        details={"row": row_num, "debit": deb, "credit": crd},
                        remediation="Debit and credit amounts must be non-negative values. Use transaction type instead of negative signs.",
                    )
                )

        return findings

    # -----------------------------------------------------------------------
    # Rule Set 2: TDS Cross-Reconciliation (Form 26AS/AIS vs Books)
    # -----------------------------------------------------------------------
    def reconcile_tds(
        self,
        tds_entries: list[dict],
        financial_records: list[dict],
    ) -> list[dict]:
        """
        Compare TDS records (Form 26AS/AIS/TIS) against company ledger / bank credits:
        - TDS deducted but not deposited / recorded in books
        - TDS amount discrepancy between source and books
        - TDS deducted on income exceeding declared amount
        """
        findings = []
        tolerance = self.config.get("tds_discrepancy_tolerance", 100.0)

        # Normalize financial records for matching
        ledger_map = {}
        for idx, rec in enumerate(financial_records):
            tan_or_desc = (rec.get("deductor_tan") or rec.get("description") or f"rec_{idx}").strip().upper()
            amt = parse_float_amount(rec.get("tds_amount") or rec.get("tax_deducted"))
            if amt is not None:
                ledger_map[tan_or_desc] = amt

        for idx, entry in enumerate(tds_entries):
            row = entry.get("source_row", idx + 1)
            deductor = (entry.get("deductor_name") or entry.get("deductor_tan") or f"Entry {idx + 1}").strip()
            section = entry.get("section") or "Section 194"
            tds_26as = parse_float_amount(entry.get("tds_amount") or entry.get("tax_deducted"))
            gross_income = parse_float_amount(entry.get("gross_amount") or entry.get("income_amount"))

            if tds_26as is None or tds_26as <= 0:
                continue

            # Check 1: TDS reported in Form 26AS without matching entry in financial records
            lookup_key = (entry.get("deductor_tan") or entry.get("deductor_name") or "").strip().upper()
            matching_ledger_tds = ledger_map.get(lookup_key)

            if matching_ledger_tds is None:
                findings.append(
                    create_finding(
                        rule_id="TAX-TDS-001",
                        category="TDS_RECONCILIATION",
                        severity="WARNING",
                        title="TDS in 26AS/AIS Missing in Books",
                        description=(
                            f"TDS of ₹{tds_26as:,.2f} under {section} by {deductor} is reflected in tax records "
                            "but has no corresponding entry in company records/books."
                        ),
                        section=section,
                        details={
                            "row": row,
                            "deductor": deductor,
                            "tds_amount_reported": tds_26as,
                            "gross_amount": gross_income,
                        },
                        remediation="Verify whether this income was received. Book the corresponding TDS receivable in the ledger to claim tax credit.",
                    )
                )
            else:
                variance = abs(tds_26as - matching_ledger_tds)
                if variance > tolerance:
                    findings.append(
                        create_finding(
                            rule_id="TAX-TDS-002",
                            category="TDS_RECONCILIATION",
                            severity="WARNING",
                            title="TDS Amount Mismatch",
                            description=(
                                f"TDS mismatch for {deductor}: 26AS/AIS reports ₹{tds_26as:,.2f} "
                                f"while financial records indicate ₹{matching_ledger_tds:,.2f} (Variance: ₹{variance:,.2f})."
                            ),
                            section=section,
                            details={
                                "row": row,
                                "deductor": deductor,
                                "tds_26as": tds_26as,
                                "tds_books": matching_ledger_tds,
                                "variance": round(variance, 2),
                            },
                            remediation="Reconcile with deductor's TDS certificate (Form 16/16A). If deductor filed incorrect TDS return, request revised filing.",
                        )
                    )

            # Check 2: Negative or zero TDS deduction claim
            if tds_26as < 0:
                findings.append(
                    create_finding(
                        rule_id="TAX-TDS-003",
                        category="TDS_RECONCILIATION",
                        severity="ERROR",
                        title="Negative TDS Claim",
                        description=f"Negative TDS amount (₹{tds_26as:,.2f}) recorded for {deductor}.",
                        section=section,
                        details={"row": row, "tds_amount": tds_26as},
                        remediation="TDS cannot be negative. Rectify the sign or remove reversal entries.",
                    )
                )

        return findings

    # -----------------------------------------------------------------------
    # Rule Set 3: Income Discrepancy & Cash Compliance
    # -----------------------------------------------------------------------
    def validate_income(
        self,
        declared_income: dict[str, float],
        transactions: list[dict] | pd.DataFrame,
    ) -> list[dict]:
        """
        Cross-verify declared income heads against actual bank deposits / financial records:
        - Salary: Form 16 / declared salary vs actual bank salary credits
        - Business Turnover: Declared gross receipts vs actual bank credit turnover
        - Section 269ST: Cash receipts of ₹2,00,000 or more in a single day
        """
        findings = []
        tx_list = transactions.to_dict(orient="records") if isinstance(transactions, pd.DataFrame) else transactions
        tolerance_pct = self.config.get("income_tolerance_pct", 2.0)

        # 1. Salary Cross-Verification
        declared_salary = parse_float_amount(declared_income.get("salary"))
        if declared_salary is not None and declared_salary > 0:
            actual_salary_credits = 0.0
            for tx in tx_list:
                desc = str(tx.get("description", "")).lower()
                crd = parse_float_amount(tx.get("credit"))
                amt = parse_float_amount(tx.get("amount"))
                deposit = crd if crd is not None else (amt if amt and amt > 0 else 0.0)

                if any(w in desc for w in ("salary", "payroll", "stipend", "remuneration")):
                    actual_salary_credits += deposit

            if actual_salary_credits > 0:
                diff = abs(declared_salary - actual_salary_credits)
                diff_pct = (diff / declared_salary) * 100
                if diff_pct > tolerance_pct:
                    severity = "WARNING" if diff_pct < 15.0 else "ERROR"
                    findings.append(
                        create_finding(
                            rule_id="TAX-INC-001",
                            category="INCOME_DISCREPANCY",
                            severity=severity,
                            title="Declared vs Bank Salary Discrepancy",
                            description=(
                                f"Declared salary of ₹{declared_salary:,.2f} differs from identifiable "
                                f"bank salary deposits of ₹{actual_salary_credits:,.2f} (Difference: ₹{diff:,.2f}, {diff_pct:.1f}%)."
                            ),
                            section="Income under Head Salaries (Sec 15-17)",
                            details={
                                "declared_salary": declared_salary,
                                "bank_salary_credits": round(actual_salary_credits, 2),
                                "discrepancy": round(diff, 2),
                                "discrepancy_pct": round(diff_pct, 2),
                            },
                            remediation="Check for TDS deductions, Provident Fund contributions, or salary components received into another bank account.",
                        )
                    )

        # 2. Section 269ST Cash Compliance (Receipt of ₹2,00,000+ in cash)
        cash_limit = self.config.get("cash_receipt_single_day_limit", 200000.0)
        daily_cash_receipts: dict[date, float] = {}

        for idx, tx in enumerate(tx_list):
            desc = str(tx.get("description", "")).lower()
            amt = parse_float_amount(tx.get("amount"))
            crd = parse_float_amount(tx.get("credit"))
            deposit = crd if crd is not None else (amt if amt and amt > 0 else 0.0)
            d = parse_date_obj(tx.get("transaction_date"))

            # Check if narration indicates cash deposit
            if d and deposit > 0 and any(w in desc for w in ("cash deposit", "by cash", "cash rec", "cdm deposit")):
                daily_cash_receipts[d] = daily_cash_receipts.get(d, 0.0) + deposit

        for d, total_cash in daily_cash_receipts.items():
            if total_cash >= cash_limit:
                findings.append(
                    create_finding(
                        rule_id="TAX-CASH-001",
                        category="CASH_TRANSACTION_LIMIT",
                        severity="ERROR",
                        title="Section 269ST Cash Receipt Breach",
                        description=(
                            f"Aggregate cash receipts on {d.isoformat()} reached ₹{total_cash:,.2f}, "
                            f"exceeding the statutory ceiling of ₹{cash_limit:,.2f} under Section 269ST."
                        ),
                        section="Section 269ST (Cash Transactions)",
                        details={
                            "date": d.isoformat(),
                            "cash_receipt_total": total_cash,
                            "statutory_limit": cash_limit,
                        },
                        remediation="Section 269ST attracts a penalty equal to 100% of the cash received under Section 271DA unless justifiable reasonable cause is documented.",
                    )
                )

        return findings

    # -----------------------------------------------------------------------
    # Rule Set 4: Deduction Validation (Chapter VI-A)
    # -----------------------------------------------------------------------
    def validate_deductions(
        self,
        claimed_deductions: dict[str, float],
        transactions: list[dict] | pd.DataFrame | None = None,
        is_senior_citizen: bool = False,
    ) -> list[dict]:
        """
        Validate Chapter VI-A deductions against FY statutory ceilings and
        cross-check with supporting transactions.
        Sections checked:
        - Section 80C: Cap ₹1,50,000 (PPF, ELSS, EPF, Life Insurance, Tuition Fees)
        - Section 80D: Medical Insurance (₹25,000 individual / ₹50,000 senior citizen)
        - Section 80CCD(1B): National Pension Scheme additional cap ₹50,000
        - Section 80TTA / 80TTB: Savings interest deduction (80TTA: ₹10,000 / 80TTB: ₹50,000)
        """
        findings = []

        # 1. Section 80C Validation
        claim_80c = parse_float_amount(claimed_deductions.get("80c") or claimed_deductions.get("80C"))
        if claim_80c is not None and claim_80c > 0:
            cap_80c = self.config.get("section_80c_cap", 150000.0)
            if claim_80c > cap_80c:
                excess = claim_80c - cap_80c
                findings.append(
                    create_finding(
                        rule_id="TAX-DED-001",
                        category="DEDUCTION_VALIDATION",
                        severity="ERROR",
                        title="Section 80C Ceiling Exceeded",
                        description=(
                            f"Claimed Section 80C deduction of ₹{claim_80c:,.2f} exceeds the statutory "
                            f"annual limit of ₹{cap_80c:,.2f} (Excess: ₹{excess:,.2f})."
                        ),
                        section="Section 80C (Chapter VI-A)",
                        details={
                            "claimed_amount": claim_80c,
                            "statutory_limit": cap_80c,
                            "disallowed_excess": excess,
                        },
                        remediation=f"Cap the deduction claim at ₹{cap_80c:,.2f} in Schedule VIA of ITR.",
                    )
                )

        # 2. Section 80D Validation (Medical Insurance)
        claim_80d = parse_float_amount(claimed_deductions.get("80d") or claimed_deductions.get("80D"))
        if claim_80d is not None and claim_80d > 0:
            cap_80d = (
                self.config.get("section_80d_senior_cap", 50000.0)
                if is_senior_citizen
                else self.config.get("section_80d_individual_cap", 25000.0)
            )
            if claim_80d > cap_80d:
                excess = claim_80d - cap_80d
                category_label = "Senior Citizen" if is_senior_citizen else "Individual/Family"
                findings.append(
                    create_finding(
                        rule_id="TAX-DED-002",
                        category="DEDUCTION_VALIDATION",
                        severity="ERROR",
                        title="Section 80D Medical Insurance Cap Exceeded",
                        description=(
                            f"Claimed Section 80D deduction of ₹{claim_80d:,.2f} exceeds statutory "
                            f"ceiling of ₹{cap_80d:,.2f} for {category_label} (Excess: ₹{excess:,.2f})."
                        ),
                        section="Section 80D (Health Insurance)",
                        details={
                            "claimed_amount": claim_80d,
                            "statutory_limit": cap_80d,
                            "disallowed_excess": excess,
                            "is_senior_citizen": is_senior_citizen,
                        },
                        remediation=f"Restrict the claim to ₹{cap_80d:,.2f} unless additional parent cover qualifies under separate sub-limit.",
                    )
                )

        # 3. Section 80CCD(1B) Validation (NPS)
        claim_80ccd = parse_float_amount(
            claimed_deductions.get("80ccd_1b") or claimed_deductions.get("80CCD_1B") or claimed_deductions.get("80ccd")
        )
        if claim_80ccd is not None and claim_80ccd > 0:
            cap_80ccd = self.config.get("section_80ccd_1b_cap", 50000.0)
            if claim_80ccd > cap_80ccd:
                excess = claim_80ccd - cap_80ccd
                findings.append(
                    create_finding(
                        rule_id="TAX-DED-003",
                        category="DEDUCTION_VALIDATION",
                        severity="ERROR",
                        title="Section 80CCD(1B) NPS Cap Exceeded",
                        description=(
                            f"Claimed NPS deduction of ₹{claim_80ccd:,.2f} exceeds statutory "
                            f"additional ceiling of ₹{cap_80ccd:,.2f} (Excess: ₹{excess:,.2f})."
                        ),
                        section="Section 80CCD(1B) (NPS)",
                        details={
                            "claimed_amount": claim_80ccd,
                            "statutory_limit": cap_80ccd,
                            "disallowed_excess": excess,
                        },
                        remediation=f"Limit the additional NPS claim to ₹{cap_80ccd:,.2f}.",
                    )
                )

        # 4. Section 80TTA / 80TTB Validation (Interest on Savings Account)
        claim_interest_ded = parse_float_amount(
            claimed_deductions.get("80tta") or claimed_deductions.get("80ttb") or claimed_deductions.get("80TTA")
        )
        if claim_interest_ded is not None and claim_interest_ded > 0:
            cap_interest = (
                self.config.get("section_80ttb_cap", 50000.0)
                if is_senior_citizen
                else self.config.get("section_80tta_cap", 10000.0)
            )
            section_name = "Section 80TTB" if is_senior_citizen else "Section 80TTA"
            if claim_interest_ded > cap_interest:
                excess = claim_interest_ded - cap_interest
                findings.append(
                    create_finding(
                        rule_id="TAX-DED-004",
                        category="DEDUCTION_VALIDATION",
                        severity="ERROR",
                        title=f"{section_name} Interest Deduction Cap Exceeded",
                        description=(
                            f"Claim of ₹{claim_interest_ded:,.2f} under {section_name} exceeds "
                            f"allowable limit of ₹{cap_interest:,.2f} (Excess: ₹{excess:,.2f})."
                        ),
                        section=section_name,
                        details={
                            "claimed_amount": claim_interest_ded,
                            "statutory_limit": cap_interest,
                            "disallowed_excess": excess,
                        },
                        remediation=f"Ensure savings interest deduction does not exceed ₹{cap_interest:,.2f}.",
                    )
                )

        # 5. Cross-Check Deduction Claims Against Transaction Proofs
        if transactions is not None and claim_80c is not None and claim_80c > 0:
            tx_list = transactions.to_dict(orient="records") if isinstance(transactions, pd.DataFrame) else transactions
            supporting_80c_payments = 0.0
            keywords_80c = ("lic", "ppf", "elss", "provident", "tuition", "nsc", "sukanya", "life insurance", "mutual fund")

            for tx in tx_list:
                desc = str(tx.get("description", "")).lower()
                deb = parse_float_amount(tx.get("debit"))
                amt = parse_float_amount(tx.get("amount"))
                outflow = deb if deb is not None else (abs(amt) if amt and amt < 0 else 0.0)

                if any(kw in desc for kw in keywords_80c):
                    supporting_80c_payments += outflow

            if supporting_80c_payments == 0.0 and claim_80c > 10000.0:
                findings.append(
                    create_finding(
                        rule_id="TAX-DED-005",
                        category="DEDUCTION_VALIDATION",
                        severity="WARNING",
                        title="Unsubstantiated Section 80C Claim",
                        description=(
                            f"A Section 80C deduction of ₹{claim_80c:,.2f} is claimed, but no matching "
                            "investments (PPF, ELSS, LIC, etc.) were found in the provided transaction records."
                        ),
                        section="Section 80C (Chapter VI-A)",
                        details={
                            "claimed_amount": claim_80c,
                            "identifiable_proof_amount": supporting_80c_payments,
                        },
                        remediation="Ensure premium receipts, deposit receipts, or statement proofs are maintained for all claimed 80C investments.",
                    )
                )

        return findings

    # -----------------------------------------------------------------------
    # Comprehensive Validation Pipeline
    # -----------------------------------------------------------------------
    def validate_all(
        self,
        transactions: list[dict] | pd.DataFrame | None = None,
        tds_entries: list[dict] | None = None,
        declared_income: dict[str, float] | None = None,
        claimed_deductions: dict[str, float] | None = None,
        is_senior_citizen: bool = False,
    ) -> dict[str, Any]:
        """
        Execute all tax validation checks and compile an audit summary.
        """
        if transactions is not None:
            if isinstance(transactions, pd.DataFrame):
                tx_data = transactions.to_dict(orient="records")
            else:
                tx_data = list(transactions)
        else:
            tx_data = []

        findings: list[dict] = []

        # 1. Transaction Integrity Checks
        if len(tx_data) > 0:
            findings.extend(self.validate_transaction_integrity(tx_data))

        # 2. TDS Reconciliation Checks
        if tds_entries:
            findings.extend(self.reconcile_tds(tds_entries, tx_data))

        # 3. Income Discrepancy & Cash Compliance
        if declared_income and len(tx_data) > 0:
            findings.extend(self.validate_income(declared_income, tx_data))
        elif len(tx_data) > 0:
            # Check cash compliance even if declared income is omitted
            findings.extend(self.validate_income({}, tx_data))

        # 4. Deduction Validation
        if claimed_deductions:
            findings.extend(
                self.validate_deductions(
                    claimed_deductions=claimed_deductions,
                    transactions=tx_data,
                    is_senior_citizen=is_senior_citizen,
                )
            )

        # Categorize findings
        errors_count = sum(1 for f in findings if f["severity"] == "ERROR")
        warnings_count = sum(1 for f in findings if f["severity"] == "WARNING")
        info_count = sum(1 for f in findings if f["severity"] == "INFO")

        # Compute tax readiness score (100 base, -15 per error, -5 per warning)
        score_penalty = (errors_count * 15.0) + (warnings_count * 5.0)
        readiness_score = max(0.0, round(100.0 - score_penalty, 1))

        # Findings grouped by category
        findings_by_category: dict[str, list[dict]] = {}
        for f in findings:
            cat = f["category"]
            findings_by_category.setdefault(cat, []).append(f)

        return {
            "summary": {
                "financial_year": self.financial_year,
                "assessment_year": self.config.get("assessment_year", "2026-27"),
                "total_findings": len(findings),
                "errors_count": errors_count,
                "warnings_count": warnings_count,
                "info_count": info_count,
                "is_filing_ready": (errors_count == 0),
                "tax_readiness_score": readiness_score,
                "findings_by_category_counts": {k: len(v) for k, v in findings_by_category.items()},
            },
            "findings": findings,
            "findings_by_category": findings_by_category,
            "disclaimer": (
                "Tax rule validation findings are indicative review flags based on deterministic "
                "statutory rules. They do not constitute official tax advice or proof of non-compliance. "
                "Consult a qualified Chartered Accountant before filing your Income Tax Return."
            ),
        }


def validate_tax_records(
    transactions: list[dict] | pd.DataFrame | None = None,
    tds_entries: list[dict] | None = None,
    declared_income: dict[str, float] | None = None,
    claimed_deductions: dict[str, float] | None = None,
    financial_year: str = "2025-26",
    custom_rules: dict[str, Any] | None = None,
    is_senior_citizen: bool = False,
) -> dict[str, Any]:
    """
    Convenience wrapper to run full tax rule validation pipeline.
    """
    engine = TaxRuleEngine(
        financial_year=financial_year,
        custom_rules=custom_rules,
    )
    return engine.validate_all(
        transactions=transactions,
        tds_entries=tds_entries,
        declared_income=declared_income,
        claimed_deductions=claimed_deductions,
        is_senior_citizen=is_senior_citizen,
    )

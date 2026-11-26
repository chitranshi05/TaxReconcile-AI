"""
backend/app/services/tax_validation/tds_discrepancy_detector.py

Advanced TDS Discrepancy Detection Engine (India – Income Tax Act, 1961).

Supplements the existing basic TDS reconciliation in TaxRuleEngine with six
advanced analytical passes:

Pass 1 — TDS Rate Validation
    Compute expected TDS from gross amount using section-specific statutory
    rates; flag when actual deduction deviates by more than the tolerance.

Pass 2 — Quarter-wise 26AS Reconciliation
    TDS is deposited and reported quarter-by-quarter (Q1: Apr-Jun, Q2: Jul-Sep,
    Q3: Oct-Dec, Q4: Jan-Mar). Detect quarter mismatches and cross-quarter
    posting errors.

Pass 3 — Late Deduction / Late Deposit Detection
    Flag TDS that was deducted in one period but the gross payment occurred in
    an earlier period (delayed deduction), or TDS deposited after the statutory
    due dates (7th of following month / 30 Apr for March).

Pass 4 — Lower Deduction Certificate Conflict
    Flag when TDS is deducted at standard rates despite the deductee holding a
    valid Form 15G / 15H / lower-deduction certificate (Section 197).

Pass 5 — Multi-Deductor PAN Aggregation
    Aggregate TDS credits across all deductors for the same deductee PAN.
    Flag when the aggregate TDS credit in 26AS exceeds the tax liability implied
    by total gross income.

Pass 6 — Unclaimed TDS Credit
    Identify TDS entries in 26AS that do not appear to be claimed in the ITR
    TDS schedule, representing a potential refund left on the table.

Design principles
-----------------
- Pure Python + standard library; no DB access, no network calls.
- Each check is independently callable; run_advanced_tds_analysis() aggregates.
- Uses the same create_finding() schema as TaxRuleEngine for consistent output.
- All monetary comparisons use a configurable tolerance (default ₹100).
- Findings include detailed metadata for the UI/accountant to act on.
"""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime
from typing import Any

import pandas as pd

from app.services.tax_validation.tax_rule_engine import (
    create_finding,
    parse_date_obj,
    parse_float_amount,
)


# ---------------------------------------------------------------------------
# Section-wise Statutory TDS Rates (FY 2025-26)
# Source: Income Tax Act, 1961 – common deduction sections
# ---------------------------------------------------------------------------

TDS_RATE_TABLE: dict[str, dict[str, Any]] = {
    "194A": {
        "description": "Interest other than interest on securities",
        "rate_pct": 10.0,
        "threshold": 40000.0,          # ₹40,000 (₹50,000 for senior citizens)
    },
    "194B": {
        "description": "Lottery / game show winnings",
        "rate_pct": 30.0,
        "threshold": 10000.0,
    },
    "194C": {
        "description": "Payments to contractors",
        "rate_pct": 1.0,               # 1% individual/HUF, 2% others
        "rate_pct_other": 2.0,
        "threshold": 30000.0,
    },
    "194D": {
        "description": "Insurance commission",
        "rate_pct": 5.0,
        "threshold": 15000.0,
    },
    "194H": {
        "description": "Commission or brokerage",
        "rate_pct": 5.0,
        "threshold": 15000.0,
    },
    "194I": {
        "description": "Rent",
        "rate_pct": 10.0,              # 2% for plant/machinery, 10% for land/building
        "threshold": 240000.0,
    },
    "194J": {
        "description": "Professional or technical services fees",
        "rate_pct": 10.0,
        "rate_pct_technical": 2.0,
        "threshold": 30000.0,
    },
    "194LA": {
        "description": "Compensation for compulsory acquisition",
        "rate_pct": 10.0,
        "threshold": 250000.0,
    },
    "192": {
        "description": "Salary",
        "rate_pct": None,              # Slab-based; cannot validate without tax computation
        "threshold": 0.0,
    },
    "194": {
        "description": "Dividend",
        "rate_pct": 10.0,
        "threshold": 5000.0,
    },
    "194N": {
        "description": "Cash withdrawal",
        "rate_pct": 2.0,
        "threshold": 2000000.0,        # ₹20 lakh
    },
    "194O": {
        "description": "E-commerce participant",
        "rate_pct": 1.0,
        "threshold": 500000.0,
    },
    "194Q": {
        "description": "Purchase of goods",
        "rate_pct": 0.1,
        "threshold": 5000000.0,
    },
}

# Quarter boundaries (financial year Apr – Mar)
_QUARTERS: list[tuple[int, int]] = [
    (4, 6),    # Q1: April – June
    (7, 9),    # Q2: July – September
    (10, 12),  # Q3: October – December
    (1, 3),    # Q4: January – March
]

_QUARTER_LABELS: dict[int, str] = {1: "Q1 (Apr-Jun)", 2: "Q2 (Jul-Sep)", 3: "Q3 (Oct-Dec)", 4: "Q4 (Jan-Mar)"}

# TDS deposit due dates: 7th of following month (30 Apr for March)
_TDS_DEPOSIT_GRACE_DAYS = 7


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _quarter_for_month(month: int) -> int:
    """Return FY quarter number (1-4) for a calendar month (1-12)."""
    if 4 <= month <= 6:
        return 1
    if 7 <= month <= 9:
        return 2
    if 10 <= month <= 12:
        return 3
    return 4   # Jan-Mar


def _quarter_label(month: int) -> str:
    return _QUARTER_LABELS[_quarter_for_month(month)]


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _normalize_section(section: str) -> str:
    """Normalise section codes like '194 J', '194-J', 'sec 194J' → '194J'."""
    s = section.strip().upper()
    s = s.replace("SEC ", "").replace("SECTION ", "").replace("-", "").replace(" ", "")
    return s


# ---------------------------------------------------------------------------
# Pass 1 — TDS Rate Validation
# ---------------------------------------------------------------------------

def check_tds_rates(
    tds_entries: list[dict],
    tolerance: float = 100.0,
) -> list[dict]:
    """
    For each TDS entry that has a known section and gross amount, compute the
    expected TDS at the statutory rate and compare to the actual deduction.

    Fields expected per entry (optional where noted):
        - section        : TDS section code (e.g. '194A', '194J')
        - gross_amount   : Gross payment on which TDS is computed
        - tds_amount     : Actual TDS deducted / reported
        - deductor_name  : Name of deductor (for display)
        - is_individual  : bool – affects 194C rate (default True)
        - is_technical   : bool – affects 194J rate (default False)
    """
    findings: list[dict] = []

    for idx, entry in enumerate(tds_entries):
        row = entry.get("source_row", idx + 1)
        raw_section = _safe_str(entry.get("section"), "")
        section = _normalize_section(raw_section) if raw_section else ""
        gross = parse_float_amount(entry.get("gross_amount") or entry.get("income_amount"))
        actual_tds = parse_float_amount(entry.get("tds_amount") or entry.get("tax_deducted"))
        deductor = _safe_str(entry.get("deductor_name") or entry.get("deductor_tan"), f"Entry {idx + 1}")

        if not section or gross is None or actual_tds is None:
            continue

        rule = TDS_RATE_TABLE.get(section)
        if rule is None:
            continue

        # Section 192 (salary) uses slab rates — cannot validate without full computation
        if rule["rate_pct"] is None:
            continue

        # Pick rate variant
        is_individual = bool(entry.get("is_individual", True))
        is_technical = bool(entry.get("is_technical", False))

        if section == "194C" and not is_individual:
            rate = rule.get("rate_pct_other", rule["rate_pct"])
        elif section == "194J" and is_technical:
            rate = rule.get("rate_pct_technical", rule["rate_pct"])
        else:
            rate = rule["rate_pct"]

        # Threshold check
        threshold = rule.get("threshold", 0.0)
        if gross < threshold:
            # Gross below threshold → TDS should be zero
            if actual_tds > tolerance:
                findings.append(create_finding(
                    rule_id="TDS-RATE-001",
                    category="TDS_RATE_DISCREPANCY",
                    severity="WARNING",
                    title="TDS Deducted Below Threshold",
                    description=(
                        f"TDS of ₹{actual_tds:,.2f} deducted by {deductor} under {section} but gross "
                        f"payment ₹{gross:,.2f} is below the ₹{threshold:,.0f} threshold. "
                        "TDS should not have been deducted."
                    ),
                    section=f"Section {section}",
                    details={
                        "row": row, "deductor": deductor, "section": section,
                        "gross_amount": gross, "threshold": threshold,
                        "actual_tds": actual_tds, "expected_tds": 0.0,
                    },
                    remediation="Claim refund of incorrectly deducted TDS via Form 26A correction or file revised return.",
                ))
            continue

        expected_tds = round(gross * rate / 100.0, 2)
        variance = round(abs(actual_tds - expected_tds), 2)

        if variance > tolerance:
            over_under = "over-deducted" if actual_tds > expected_tds else "under-deducted"
            severity = "ERROR" if variance > tolerance * 5 else "WARNING"
            findings.append(create_finding(
                rule_id="TDS-RATE-002",
                category="TDS_RATE_DISCREPANCY",
                severity=severity,
                title=f"TDS Rate Variance ({section})",
                description=(
                    f"TDS {over_under} by {deductor} under {section}: expected ₹{expected_tds:,.2f} "
                    f"at {rate}% on gross ₹{gross:,.2f}; actual deduction ₹{actual_tds:,.2f} "
                    f"(variance ₹{variance:,.2f})."
                ),
                section=f"Section {section}",
                details={
                    "row": row, "deductor": deductor, "section": section,
                    "gross_amount": gross, "statutory_rate_pct": rate,
                    "expected_tds": expected_tds, "actual_tds": actual_tds,
                    "variance": variance, "over_under": over_under,
                },
                remediation=(
                    "Verify applicable TDS rate with deductor's Form 16A. "
                    "If under-deducted, the deductee may bear interest u/s 201(1A)."
                ),
            ))

    return findings


# ---------------------------------------------------------------------------
# Pass 2 — Quarter-wise 26AS Reconciliation
# ---------------------------------------------------------------------------

def check_quarter_wise_reconciliation(
    tds_entries_26as: list[dict],
    tds_entries_books: list[dict],
    tolerance: float = 100.0,
) -> list[dict]:
    """
    Group both 26AS entries and book entries by (deductor_tan, quarter) and
    compare aggregate TDS amounts within each quarter.

    Expected fields per entry:
        - deductor_tan / deductor_name : identifier
        - tds_amount / tax_deducted    : TDS amount
        - transaction_date / credit_date : date to determine quarter
    """
    findings: list[dict] = []

    def _build_quarter_map(entries: list[dict]) -> dict[tuple[str, int], float]:
        qmap: dict[tuple[str, int], float] = defaultdict(float)
        for idx, e in enumerate(entries):
            key = (_safe_str(e.get("deductor_tan") or e.get("deductor_name"), f"unk_{idx}").upper())
            d = parse_date_obj(e.get("transaction_date") or e.get("credit_date"))
            quarter = _quarter_for_month(d.month) if d else 0
            amt = parse_float_amount(e.get("tds_amount") or e.get("tax_deducted")) or 0.0
            qmap[(key, quarter)] += amt
        return dict(qmap)

    map_26as = _build_quarter_map(tds_entries_26as)
    map_books = _build_quarter_map(tds_entries_books)

    all_keys = set(map_26as.keys()) | set(map_books.keys())

    for (deductor, quarter) in sorted(all_keys):
        if quarter == 0:
            continue   # Skip entries with no parseable date
        amt_26as = map_26as.get((deductor, quarter), 0.0)
        amt_books = map_books.get((deductor, quarter), 0.0)
        variance = round(abs(amt_26as - amt_books), 2)

        if variance <= tolerance:
            continue

        q_label = _QUARTER_LABELS.get(quarter, f"Q{quarter}")
        over_under = "higher in 26AS" if amt_26as > amt_books else "lower in 26AS"

        findings.append(create_finding(
            rule_id="TDS-QTR-001",
            category="TDS_QUARTER_MISMATCH",
            severity="WARNING",
            title=f"Quarter-wise TDS Mismatch ({q_label})",
            description=(
                f"TDS for {deductor} in {q_label} differs between 26AS (₹{amt_26as:,.2f}) "
                f"and books (₹{amt_books:,.2f}) — {over_under} by ₹{variance:,.2f}."
            ),
            section="TDS Reconciliation (Form 26AS)",
            details={
                "deductor": deductor,
                "quarter": q_label,
                "tds_26as": round(amt_26as, 2),
                "tds_books": round(amt_books, 2),
                "variance": variance,
            },
            remediation=(
                "Match individual TDS certificates (Form 16A) to 26AS quarter-by-quarter. "
                "Raise a correction request with the deductor if their TRACES filing is incorrect."
            ),
        ))

    return findings


# ---------------------------------------------------------------------------
# Pass 3 — Late Deduction / Late Deposit Detection
# ---------------------------------------------------------------------------

def check_late_tds(
    tds_entries: list[dict],
    financial_year: str = "2025-26",
) -> list[dict]:
    """
    Detect:
    a) Late deduction: TDS credit_date is in a later quarter than payment_date
    b) Late deposit: TDS deposited (deposit_date) after statutory due date
       (7th of following month; for March deductions: 30 April)

    Fields expected per entry:
        - payment_date  : Date when payment was made to deductee
        - credit_date   : Date when TDS was actually deducted / credited
        - deposit_date  : Date when TDS was deposited to government (challan date)
        - tds_amount    : Amount deducted
        - deductor_name : For display
        - section       : TDS section code
    """
    findings: list[dict] = []
    fy_start_year = int(financial_year.split("-")[0])

    for idx, entry in enumerate(tds_entries):
        row = entry.get("source_row", idx + 1)
        deductor = _safe_str(entry.get("deductor_name") or entry.get("deductor_tan"), f"Entry {idx + 1}")
        section = _safe_str(entry.get("section"), "N/A")
        tds_amt = parse_float_amount(entry.get("tds_amount") or entry.get("tax_deducted"))

        payment_date = parse_date_obj(entry.get("payment_date"))
        credit_date = parse_date_obj(entry.get("credit_date") or entry.get("transaction_date"))
        deposit_date = parse_date_obj(entry.get("deposit_date") or entry.get("challan_date"))

        if tds_amt is None or tds_amt <= 0:
            continue

        # --- (a) Late deduction: credit_date quarter later than payment_date quarter ---
        if payment_date and credit_date and credit_date > payment_date:
            pay_q = _quarter_for_month(payment_date.month)
            crd_q = _quarter_for_month(credit_date.month)
            if crd_q != pay_q:
                delay_days = (credit_date - payment_date).days
                findings.append(create_finding(
                    rule_id="TDS-LATE-001",
                    category="TDS_LATE_DEDUCTION",
                    severity="WARNING",
                    title="TDS Deducted in Different Quarter than Payment",
                    description=(
                        f"Payment by {deductor} under {section} was made on {payment_date.isoformat()} "
                        f"({_quarter_label(payment_date.month)}) but TDS was deducted on "
                        f"{credit_date.isoformat()} ({_quarter_label(credit_date.month)}) "
                        f"— {delay_days} day(s) later."
                    ),
                    section=f"Section {section} / Section 201",
                    details={
                        "row": row, "deductor": deductor, "section": section,
                        "payment_date": payment_date.isoformat(),
                        "deduction_date": credit_date.isoformat(),
                        "delay_days": delay_days,
                        "tds_amount": tds_amt,
                        "payment_quarter": _quarter_label(payment_date.month),
                        "deduction_quarter": _quarter_label(credit_date.month),
                    },
                    remediation=(
                        "Interest u/s 201(1A)(i) @ 1% per month is applicable for late deduction. "
                        "Compute and disclose the interest in the TDS return."
                    ),
                ))

        # --- (b) Late deposit: deposit_date after due date ---
        if credit_date and deposit_date and deposit_date > credit_date:
            # Compute due date: 7th of month following deduction; 30 Apr for March
            if credit_date.month == 3:
                # March TDS → due by 30 April of same FY end
                due_year = credit_date.year if credit_date.month <= 3 else credit_date.year + 1
                due_date = date(due_year, 4, 30)
            else:
                # Normal: 7th of following month
                next_month = credit_date.month + 1 if credit_date.month < 12 else 1
                next_year = credit_date.year if credit_date.month < 12 else credit_date.year + 1
                due_date = date(next_year, next_month, 7)

            if deposit_date > due_date:
                delay_days = (deposit_date - due_date).days
                findings.append(create_finding(
                    rule_id="TDS-LATE-002",
                    category="TDS_LATE_DEPOSIT",
                    severity="ERROR",
                    title="TDS Deposited After Due Date",
                    description=(
                        f"TDS of ₹{tds_amt:,.2f} deducted by {deductor} under {section} on "
                        f"{credit_date.isoformat()} was deposited on {deposit_date.isoformat()}, "
                        f"{delay_days} day(s) after the due date of {due_date.isoformat()}."
                    ),
                    section=f"Section {section} / Section 201(1A)(ii)",
                    details={
                        "row": row, "deductor": deductor, "section": section,
                        "deduction_date": credit_date.isoformat(),
                        "deposit_date": deposit_date.isoformat(),
                        "statutory_due_date": due_date.isoformat(),
                        "delay_days": delay_days,
                        "tds_amount": tds_amt,
                    },
                    remediation=(
                        f"Interest u/s 201(1A)(ii) @ 1.5% per month (or part thereof) is payable "
                        f"for {delay_days} day(s) of late deposit. Deposit interest via ITNS 281 challan."
                    ),
                ))

    return findings


# ---------------------------------------------------------------------------
# Pass 4 — Lower Deduction Certificate Conflict
# ---------------------------------------------------------------------------

def check_lower_deduction_certificate(
    tds_entries: list[dict],
    exemption_certificates: list[dict],
    tolerance: float = 100.0,
) -> list[dict]:
    """
    Flag when TDS is deducted at standard rates despite a valid Form 15G/15H
    or lower-deduction certificate (Section 197) being on record.

    tds_entries fields:
        - deductee_pan      : PAN of deductee
        - section           : TDS section
        - tds_amount        : Actual TDS deducted
        - gross_amount      : Gross payment
        - transaction_date  : Date of deduction
        - deductor_name     : For display

    exemption_certificates fields:
        - deductee_pan      : PAN
        - section           : Section covered (or 'ALL')
        - certificate_type  : '15G', '15H', '197'
        - approved_rate_pct : Approved lower rate (0.0 for 15G/15H)
        - valid_from        : Date
        - valid_to          : Date
    """
    findings: list[dict] = []

    # Build lookup: pan → list of certificates
    cert_map: dict[str, list[dict]] = defaultdict(list)
    for cert in exemption_certificates:
        pan = _safe_str(cert.get("deductee_pan"), "").upper()
        if pan:
            cert_map[pan].append(cert)

    for idx, entry in enumerate(tds_entries):
        row = entry.get("source_row", idx + 1)
        pan = _safe_str(entry.get("deductee_pan"), "").upper()
        section = _normalize_section(_safe_str(entry.get("section"), ""))
        actual_tds = parse_float_amount(entry.get("tds_amount") or entry.get("tax_deducted"))
        gross = parse_float_amount(entry.get("gross_amount") or entry.get("income_amount"))
        deductor = _safe_str(entry.get("deductor_name") or entry.get("deductor_tan"), f"Entry {idx + 1}")
        tx_date = parse_date_obj(entry.get("transaction_date") or entry.get("credit_date"))

        if not pan or actual_tds is None or actual_tds <= tolerance:
            continue

        certs = cert_map.get(pan, [])
        for cert in certs:
            cert_section = _normalize_section(_safe_str(cert.get("section"), "ALL"))
            if cert_section != "ALL" and cert_section != section:
                continue

            valid_from = parse_date_obj(cert.get("valid_from"))
            valid_to = parse_date_obj(cert.get("valid_to"))

            if tx_date and valid_from and valid_to:
                if not (valid_from <= tx_date <= valid_to):
                    continue   # Certificate not valid on transaction date

            cert_type = _safe_str(cert.get("certificate_type"), "").upper()
            approved_rate = parse_float_amount(cert.get("approved_rate_pct"))
            if approved_rate is None:
                approved_rate = 0.0

            expected_tds = round((gross or 0.0) * approved_rate / 100.0, 2)
            variance = round(abs(actual_tds - expected_tds), 2)

            if variance > tolerance:
                severity = "ERROR" if cert_type in ("15G", "15H") else "WARNING"
                findings.append(create_finding(
                    rule_id="TDS-CERT-001",
                    category="TDS_EXEMPTION_CONFLICT",
                    severity=severity,
                    title=f"TDS Deducted Despite Form {cert_type} / Lower-Rate Certificate",
                    description=(
                        f"Deductee PAN {pan} has a valid {cert_type} certificate "
                        f"(approved rate: {approved_rate}%) but {deductor} deducted TDS of "
                        f"₹{actual_tds:,.2f} on gross ₹{(gross or 0.0):,.2f} under {section}. "
                        f"Expected deduction: ₹{expected_tds:,.2f} (variance ₹{variance:,.2f})."
                    ),
                    section=f"Section {section} / Section 197 / 206AA",
                    details={
                        "row": row, "deductee_pan": pan, "deductor": deductor,
                        "section": section, "certificate_type": cert_type,
                        "approved_rate_pct": approved_rate,
                        "actual_tds": actual_tds, "expected_tds": expected_tds,
                        "variance": variance,
                        "certificate_valid_from": cert.get("valid_from"),
                        "certificate_valid_to": cert.get("valid_to"),
                    },
                    remediation=(
                        f"Submit Form {cert_type} to the deductor and claim refund of excess TDS "
                        "by filing ITR. The deductor should revise their TDS return on TRACES."
                    ),
                ))
            break  # First matching certificate is sufficient

    return findings


# ---------------------------------------------------------------------------
# Pass 5 — Multi-Deductor PAN Aggregation
# ---------------------------------------------------------------------------

def check_pan_aggregate_tds(
    tds_entries: list[dict],
    declared_income: dict[str, float] | None = None,
    tax_liability: float | None = None,
    tolerance: float = 100.0,
) -> list[dict]:
    """
    Aggregate all 26AS TDS credits per deductee PAN and check:
    1. Total TDS credit > computed tax liability (excess credit → refund due)
    2. Total TDS credit sourced from more than N deductors (potential misreporting)

    Useful for identifying taxpayers who should be filing for a large refund
    but are unaware, or for detecting suspicious multi-deductor patterns.

    tds_entries fields:
        - deductee_pan      : PAN of deductee (optional; aggregates all if absent)
        - deductor_tan      : TAN of deductor
        - tds_amount        : TDS credited
        - gross_amount      : Gross payment
    """
    findings: list[dict] = []

    # Aggregate per deductee PAN
    pan_tds: dict[str, float] = defaultdict(float)
    pan_gross: dict[str, float] = defaultdict(float)
    pan_deductors: dict[str, set[str]] = defaultdict(set)

    for idx, entry in enumerate(tds_entries):
        pan = _safe_str(entry.get("deductee_pan") or entry.get("pan"), "UNKNOWN").upper()
        tan = _safe_str(entry.get("deductor_tan"), f"unk_{idx}").upper()
        tds_amt = parse_float_amount(entry.get("tds_amount") or entry.get("tax_deducted")) or 0.0
        gross = parse_float_amount(entry.get("gross_amount") or entry.get("income_amount")) or 0.0

        pan_tds[pan] += tds_amt
        pan_gross[pan] += gross
        pan_deductors[pan].add(tan)

    for pan, total_tds in pan_tds.items():
        total_gross = pan_gross[pan]
        deductors = pan_deductors[pan]

        # Check 1: TDS credit exceeds stated tax liability
        if tax_liability is not None and total_tds > (tax_liability + tolerance):
            excess = round(total_tds - tax_liability, 2)
            findings.append(create_finding(
                rule_id="TDS-AGG-001",
                category="TDS_EXCESS_CREDIT",
                severity="INFO",
                title="TDS Credit Exceeds Computed Tax Liability",
                description=(
                    f"Aggregate TDS credit for PAN {pan} is ₹{total_tds:,.2f} across "
                    f"{len(deductors)} deductor(s), exceeding the stated tax liability of "
                    f"₹{tax_liability:,.2f}. Excess refund due: ₹{excess:,.2f}."
                ),
                section="Section 237 (Refund)",
                details={
                    "deductee_pan": pan,
                    "total_tds_credit": round(total_tds, 2),
                    "tax_liability": tax_liability,
                    "excess_credit": excess,
                    "deductor_count": len(deductors),
                    "deductor_tans": sorted(deductors),
                    "total_gross_income": round(total_gross, 2),
                },
                remediation=(
                    "File ITR and claim TDS credit in Schedule TDS. "
                    "Refund will be processed after ITR verification."
                ),
            ))

        # Check 2: Unusually high number of deductors
        if len(deductors) >= 5:
            findings.append(create_finding(
                rule_id="TDS-AGG-002",
                category="TDS_MULTI_DEDUCTOR",
                severity="INFO",
                title="High Number of TDS Deductors",
                description=(
                    f"PAN {pan} has TDS deducted by {len(deductors)} separate deductors "
                    f"totalling ₹{total_tds:,.2f} on gross income of ₹{total_gross:,.2f}."
                ),
                section="Form 26AS / AIS Verification",
                details={
                    "deductee_pan": pan,
                    "deductor_count": len(deductors),
                    "deductor_tans": sorted(deductors),
                    "total_tds_credit": round(total_tds, 2),
                    "total_gross_income": round(total_gross, 2),
                },
                remediation=(
                    "Cross-verify all deductor entries in Form 26AS with individual Form 16A certificates. "
                    "Ensure all income sources are declared in ITR."
                ),
            ))

    return findings


# ---------------------------------------------------------------------------
# Pass 6 — Unclaimed TDS Credit
# ---------------------------------------------------------------------------

def check_unclaimed_tds(
    tds_entries_26as: list[dict],
    itr_tds_schedule: list[dict] | None,
    tolerance: float = 100.0,
) -> list[dict]:
    """
    Identify TDS credits in Form 26AS that are not reflected in the ITR's
    TDS schedule. These represent refunds left unclaimed.

    If itr_tds_schedule is None or empty, all 26AS entries are flagged as
    potentially unclaimed.

    Matching key: deductor_tan + quarter (by transaction_date)

    26AS entry fields: deductor_tan, tds_amount, transaction_date, section
    ITR schedule fields: deductor_tan, tds_amount_claimed, quarter (1-4)
    """
    findings: list[dict] = []

    # Build ITR claimed map: (tan, quarter) → amount_claimed
    itr_map: dict[tuple[str, int], float] = defaultdict(float)
    if itr_tds_schedule:
        for entry in itr_tds_schedule:
            tan = _safe_str(entry.get("deductor_tan"), "").upper()
            d = parse_date_obj(entry.get("transaction_date") or entry.get("credit_date"))
            quarter = _quarter_for_month(d.month) if d else int(entry.get("quarter", 0))
            claimed = parse_float_amount(entry.get("tds_amount_claimed") or entry.get("tds_amount")) or 0.0
            itr_map[(tan, quarter)] += claimed

    for idx, entry in enumerate(tds_entries_26as):
        row = entry.get("source_row", idx + 1)
        tan = _safe_str(entry.get("deductor_tan"), "").upper()
        deductor = _safe_str(entry.get("deductor_name") or tan, f"Entry {idx + 1}")
        section = _safe_str(entry.get("section"), "N/A")
        tds_26as = parse_float_amount(entry.get("tds_amount") or entry.get("tax_deducted"))
        d = parse_date_obj(entry.get("transaction_date") or entry.get("credit_date"))
        quarter = _quarter_for_month(d.month) if d else 0

        if tds_26as is None or tds_26as <= 0:
            continue

        if itr_tds_schedule is None:
            # No ITR schedule provided – flag all as potentially unclaimed
            findings.append(create_finding(
                rule_id="TDS-UNCLAIM-001",
                category="TDS_UNCLAIMED_CREDIT",
                severity="INFO",
                title="Potentially Unclaimed TDS Credit",
                description=(
                    f"TDS of ₹{tds_26as:,.2f} by {deductor} under {section} "
                    f"({_quarter_label(d.month) if d else 'unknown quarter'}) "
                    "was not provided in the ITR TDS schedule for verification."
                ),
                section="Schedule TDS / Form 26AS",
                details={
                    "row": row, "deductor_tan": tan, "deductor": deductor,
                    "section": section, "tds_amount_26as": tds_26as,
                    "quarter": _quarter_label(d.month) if d else "Unknown",
                },
                remediation="Ensure all TDS credits from Form 26AS are claimed in Schedule TDS of your ITR.",
            ))
            continue

        if quarter == 0:
            continue

        claimed = itr_map.get((tan, quarter), 0.0)
        unclaimed = round(tds_26as - claimed, 2)

        if unclaimed > tolerance:
            findings.append(create_finding(
                rule_id="TDS-UNCLAIM-002",
                category="TDS_UNCLAIMED_CREDIT",
                severity="WARNING",
                title="TDS Credit in 26AS Not Fully Claimed in ITR",
                description=(
                    f"TDS of ₹{tds_26as:,.2f} by {deductor} under {section} in "
                    f"{_quarter_label(d.month) if d else 'unknown quarter'}: "
                    f"₹{claimed:,.2f} claimed in ITR, ₹{unclaimed:,.2f} unclaimed."
                ),
                section="Schedule TDS / Form 26AS",
                details={
                    "row": row, "deductor_tan": tan, "deductor": deductor,
                    "section": section, "tds_amount_26as": tds_26as,
                    "tds_claimed_itr": round(claimed, 2),
                    "unclaimed_amount": unclaimed,
                    "quarter": _quarter_label(d.month) if d else "Unknown",
                },
                remediation=(
                    "Claim the remaining ₹{:,.2f} TDS credit in Schedule TDS of your ITR. "
                    "This may entitle you to an additional refund.".format(unclaimed)
                ),
            ))

    return findings


# ---------------------------------------------------------------------------
# Main aggregator
# ---------------------------------------------------------------------------

def run_advanced_tds_analysis(
    tds_entries_26as: list[dict],
    tds_entries_books: list[dict] | None = None,
    exemption_certificates: list[dict] | None = None,
    itr_tds_schedule: list[dict] | None = None,
    declared_income: dict[str, float] | None = None,
    tax_liability: float | None = None,
    financial_year: str = "2025-26",
    tolerance: float = 100.0,
) -> dict[str, Any]:
    """
    Run all six advanced TDS discrepancy detection passes and compile results.

    Parameters
    ----------
    tds_entries_26as        : TDS entries from Form 26AS / AIS (required)
    tds_entries_books       : TDS entries from company books/ledger (for quarter reconciliation)
    exemption_certificates  : List of Form 15G/15H/197 certificates
    itr_tds_schedule        : TDS schedule from draft/filed ITR
    declared_income         : Declared income heads (for context)
    tax_liability           : Computed total tax liability (for excess credit check)
    financial_year          : Financial year string e.g. '2025-26'
    tolerance               : Monetary tolerance for comparisons (default ₹100)

    Returns
    -------
    dict with:
        summary         – counts and severity breakdown
        findings        – flat list of all findings
        findings_by_pass – grouped by detection pass
        disclaimer      – advisory disclaimer
    """
    all_findings: list[dict] = []
    findings_by_pass: dict[str, list[dict]] = {}

    # Pass 1: Rate validation
    p1 = check_tds_rates(tds_entries_26as, tolerance=tolerance)
    findings_by_pass["pass_1_rate_validation"] = p1
    all_findings.extend(p1)

    # Pass 2: Quarter-wise reconciliation
    if tds_entries_books:
        p2 = check_quarter_wise_reconciliation(tds_entries_26as, tds_entries_books, tolerance=tolerance)
        findings_by_pass["pass_2_quarter_reconciliation"] = p2
        all_findings.extend(p2)

    # Pass 3: Late deduction / deposit
    p3 = check_late_tds(tds_entries_26as, financial_year=financial_year)
    findings_by_pass["pass_3_late_tds"] = p3
    all_findings.extend(p3)

    # Pass 4: Lower deduction certificate conflict
    if exemption_certificates:
        p4 = check_lower_deduction_certificate(
            tds_entries_26as,
            exemption_certificates,
            tolerance=tolerance,
        )
        findings_by_pass["pass_4_exemption_conflict"] = p4
        all_findings.extend(p4)

    # Pass 5: Multi-deductor PAN aggregation
    p5 = check_pan_aggregate_tds(
        tds_entries_26as,
        declared_income=declared_income,
        tax_liability=tax_liability,
        tolerance=tolerance,
    )
    findings_by_pass["pass_5_pan_aggregation"] = p5
    all_findings.extend(p5)

    # Pass 6: Unclaimed TDS credit
    p6 = check_unclaimed_tds(tds_entries_26as, itr_tds_schedule, tolerance=tolerance)
    findings_by_pass["pass_6_unclaimed_credit"] = p6
    all_findings.extend(p6)

    # Summary
    errors = sum(1 for f in all_findings if f["severity"] == "ERROR")
    warnings = sum(1 for f in all_findings if f["severity"] == "WARNING")
    infos = sum(1 for f in all_findings if f["severity"] == "INFO")

    total_26as_tds = sum(
        parse_float_amount(e.get("tds_amount") or e.get("tax_deducted")) or 0.0
        for e in tds_entries_26as
    )

    return {
        "summary": {
            "financial_year": financial_year,
            "tds_entries_analysed": len(tds_entries_26as),
            "total_26as_tds_amount": round(total_26as_tds, 2),
            "total_findings": len(all_findings),
            "errors_count": errors,
            "warnings_count": warnings,
            "info_count": infos,
            "passes_run": list(findings_by_pass.keys()),
            "findings_by_pass_counts": {k: len(v) for k, v in findings_by_pass.items()},
        },
        "findings": all_findings,
        "findings_by_pass": findings_by_pass,
        "disclaimer": (
            "Advanced TDS discrepancy findings are advisory indicators based on statutory rules "
            "and the data provided. They do not constitute confirmed non-compliance or tax advice. "
            "Consult a qualified Chartered Accountant before taking any corrective action."
        ),
    }


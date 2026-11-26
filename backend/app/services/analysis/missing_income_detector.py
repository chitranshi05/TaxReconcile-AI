"""
backend/app/services/analysis/missing_income_detector.py

Missing Income Detection Engine.
Identifies:
1. Missing periodic income (e.g. skipped salary, missing monthly rent, omitted retainer).
2. Underpaid periodic income (e.g. substantial drop compared to baseline expected amount).
3. Uncollected accrued income (revenue recorded in company ledger with no bank inflow).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
import statistics

import pandas as pd

from app.services.ingestion.entity_normalizer import normalize_transaction_entity
from app.services.reconciliation.reconciliation_engine import (
    normalize_date_to_date,
    normalize_description,
)


@dataclass
class RecurringIncomeStream:
    payer: str
    category: str
    periodicity: str  # "MONTHLY", "QUARTERLY", "IRREGULAR"
    expected_amount: float
    total_received: float
    occurrences_count: int
    first_date: date
    last_date: date
    active_months: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "payer": self.payer,
            "category": self.category,
            "periodicity": self.periodicity,
            "expected_amount": round(self.expected_amount, 2),
            "total_received": round(self.total_received, 2),
            "occurrences_count": self.occurrences_count,
            "first_date": self.first_date.isoformat(),
            "last_date": self.last_date.isoformat(),
            "active_months": self.active_months,
        }


@dataclass
class MissingIncomeFinding:
    finding_type: str  # "MISSING_PERIODIC_INCOME", "UNDERPAID_INCOME", "UNCOLLECTED_ACCRUED_INCOME"
    payer: str
    expected_period: str  # e.g., "2026-06" or specific date string
    expected_amount: float
    actual_amount: float
    deficit_amount: float
    severity: str  # "HIGH", "MEDIUM", "LOW"
    confidence_score: float
    description: str
    recommendation: str
    related_transaction: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_type": self.finding_type,
            "payer": self.payer,
            "expected_period": self.expected_period,
            "expected_amount": round(self.expected_amount, 2),
            "actual_amount": round(self.actual_amount, 2),
            "deficit_amount": round(self.deficit_amount, 2),
            "severity": self.severity,
            "confidence_score": round(self.confidence_score, 2),
            "description": self.description,
            "recommendation": self.recommendation,
            "related_transaction": self.related_transaction,
        }


def _extract_credit_amount(tx: dict) -> float:
    """Extract positive credit/inflow amount from transaction dictionary."""
    credit = tx.get("credit")
    if credit is not None and not pd.isna(credit):
        try:
            val = float(credit)
            if val > 0:
                return round(val, 2)
        except (ValueError, TypeError):
            pass

    amount = tx.get("amount")
    if amount is not None and not pd.isna(amount):
        try:
            val = float(amount)
            if val > 0:
                return round(val, 2)
        except (ValueError, TypeError):
            pass

    return 0.0


def _month_key(d: date) -> str:
    """Return YYYY-MM key."""
    return f"{d.year:04d}-{d.month:02d}"


def _generate_months_between(start_date: date, end_date: date) -> list[str]:
    """Generate all YYYY-MM strings between two dates inclusive."""
    months = []
    curr_year = start_date.year
    curr_month = start_date.month

    while (curr_year < end_date.year) or (curr_year == end_date.year and curr_month <= end_date.month):
        months.append(f"{curr_year:04d}-{curr_month:02d}")
        curr_month += 1
        if curr_month > 12:
            curr_month = 1
            curr_year += 1
    return months


class MissingIncomeDetector:
    """
    Analyzes banking statements and company books to find absent, delayed, or underpaid income.
    """

    def __init__(
        self,
        min_stream_occurrences: int = 2,
        underpayment_ratio_threshold: float = 0.70,
        uncollected_tolerance_days: int = 30,
    ):
        self.min_stream_occurrences = max(2, int(min_stream_occurrences))
        self.underpayment_ratio_threshold = float(underpayment_ratio_threshold)
        self.uncollected_tolerance_days = max(1, int(uncollected_tolerance_days))

    def detect(
        self,
        bank_transactions: list[dict],
        ledger_transactions: list[dict] | None = None,
        as_of_date: date | str | None = None,
        underpayment_ratio_threshold: float | None = None,
        uncollected_tolerance_days: int | None = None,
    ) -> dict[str, Any]:
        """
        Run full missing income detection pipeline across bank and ledger items.
        """
        ref_date = normalize_date_to_date(as_of_date)
        up_thresh = self.underpayment_ratio_threshold if underpayment_ratio_threshold is None else float(underpayment_ratio_threshold)
        uncoll_days = self.uncollected_tolerance_days if uncollected_tolerance_days is None else int(uncollected_tolerance_days)

        # 1. Prepare bank credit transactions
        credit_txs = []
        for tx in bank_transactions:
            amt = _extract_credit_amount(tx)
            d = normalize_date_to_date(tx.get("transaction_date"))
            if amt > 0 and d is not None:
                norm_res = normalize_transaction_entity(tx.get("description", ""))
                norm_ent = norm_res.get("normalized_entity") if isinstance(norm_res, dict) else getattr(norm_res, "normalized_entity", "Unknown")
                clean_desc = norm_res.get("clean_description") if isinstance(norm_res, dict) else getattr(norm_res, "clean_description", "")
                payer = norm_ent if norm_ent and norm_ent != "Unknown" else (clean_desc or "Unknown Payer")
                channel = norm_res.get("channel", "UNKNOWN") if isinstance(norm_res, dict) else getattr(norm_res, "channel", "UNKNOWN")
                credit_txs.append({
                    "raw": tx,
                    "date": d,
                    "month": _month_key(d),
                    "amount": amt,
                    "payer": payer,
                    "channel": channel,
                    "category": self._infer_income_category(tx.get("description", ""), payer),
                })

        # 2. Identify Recurring Streams & Periodic Gaps
        streams, stream_findings = self._analyze_recurring_streams(credit_txs, ref_date, up_thresh)

        # 3. Cross-Check with Ledger (Uncollected Income)
        ledger_findings = []
        if ledger_transactions:
            ledger_findings = self._detect_uncollected_ledger_income(credit_txs, ledger_transactions, uncoll_days)
            ledger_findings = self._detect_uncollected_ledger_income(credit_txs, ledger_transactions)

        all_findings = stream_findings + ledger_findings

        # 4. Summary calculation
        total_actual_income = round(sum(tx["amount"] for tx in credit_txs), 2)
        total_missing_amount = round(sum(f.deficit_amount for f in all_findings), 2)

        return {
            "summary": {
                "total_credit_transactions": len(credit_txs),
                "total_actual_income": total_actual_income,
                "recurring_streams_count": len(streams),
                "total_missing_income_amount": total_missing_amount,
                "findings_count": len(all_findings),
                "missing_periodic_gaps_count": sum(1 for f in all_findings if f.finding_type == "MISSING_PERIODIC_INCOME"),
                "underpaid_income_count": sum(1 for f in all_findings if f.finding_type == "UNDERPAID_INCOME"),
                "uncollected_ledger_income_count": sum(1 for f in all_findings if f.finding_type == "UNCOLLECTED_ACCRUED_INCOME"),
            },
            "recurring_streams": [s.to_dict() for s in streams],
            "findings": [f.to_dict() for f in all_findings],
        }

    def _infer_income_category(self, desc: str, payer: str) -> str:
        text = f"{desc} {payer}".lower()
        if any(k in text for k in ("salary", "payroll", "stipend", "wages", "remuneration")):
            return "SALARY"
        if any(k in text for k in ("rent", "lease", "rental", "tenant", "premises")):
            return "RENTAL_INCOME"
        if any(k in text for k in ("dividend", "interest", "fd int", "yield", "coupon")):
            return "INVESTMENT_INCOME"
        if any(k in text for k in ("retainer", "consulting", "advisory", "professional", "fees")):
            return "PROFESSIONAL_FEES"
        return "GENERAL_INCOME"

    def _analyze_recurring_streams(
        self,
        credit_txs: list[dict],
        ref_date: date | None,
        underpayment_ratio: float | None = None,
    ) -> tuple[list[RecurringIncomeStream], list[MissingIncomeFinding]]:
        """Group credits by payer, detect recurrence, and identify calendar gaps."""
        up_ratio = self.underpayment_ratio_threshold if underpayment_ratio is None else float(underpayment_ratio)
        # Group by payer
        groups: dict[str, list[dict]] = {}
        for tx in credit_txs:
            payer_key = tx["payer"].strip().upper()
            groups.setdefault(payer_key, []).append(tx)

        streams: list[RecurringIncomeStream] = []
        findings: list[MissingIncomeFinding] = []

        for payer, tx_list in groups.items():
            if len(tx_list) < self.min_stream_occurrences:
                continue

            tx_list.sort(key=lambda x: x["date"])
            dates = [t["date"] for t in tx_list]
            amounts = [t["amount"] for t in tx_list]

            # Measure intervals between payments
            intervals = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
            median_interval = statistics.median(intervals) if intervals else 0

            # Determine periodicity
            if 20 <= median_interval <= 40:
                periodicity = "MONTHLY"
            elif 75 <= median_interval <= 105:
                periodicity = "QUARTERLY"
            else:
                periodicity = "MONTHLY" if len(tx_list) >= 3 and (dates[-1] - dates[0]).days >= 60 else "IRREGULAR"

            if periodicity == "IRREGULAR":
                continue

            median_amount = statistics.median(amounts)
            category = tx_list[0]["category"]
            first_date = dates[0]
            last_date = dates[-1]
            end_boundary = max(last_date, ref_date) if ref_date else last_date

            # Group payments by month
            months_present: dict[str, list[dict]] = {}
            for t in tx_list:
                months_present.setdefault(t["month"], []).append(t)

            expected_months = _generate_months_between(first_date, end_boundary)

            stream = RecurringIncomeStream(
                payer=payer,
                category=category,
                periodicity=periodicity,
                expected_amount=median_amount,
                total_received=sum(amounts),
                occurrences_count=len(tx_list),
                first_date=first_date,
                last_date=last_date,
                active_months=sorted(months_present.keys()),
            )
            streams.append(stream)

            # Detect Gaps and Underpayments
            for m in expected_months:
                if m not in months_present:
                    # Missing Month Gap
                    severity = "HIGH" if category in ("SALARY", "RENTAL_INCOME") else "MEDIUM"
                    findings.append(
                        MissingIncomeFinding(
                            finding_type="MISSING_PERIODIC_INCOME",
                            payer=payer,
                            expected_period=m,
                            expected_amount=median_amount,
                            actual_amount=0.0,
                            deficit_amount=median_amount,
                            severity=severity,
                            confidence_score=0.90,
                            description=(
                                f"Expected {periodicity.lower()} {category.lower().replace('_', ' ')} of ₹{median_amount:,.2f} "
                                f"from {payer} is missing for {m}."
                            ),
                            recommendation=(
                                f"Verify whether payment for {m} was delayed, diverted to another account, "
                                f"or remains unpaid by {payer}."
                            ),
                        )
                    )
                else:
                    month_total = sum(t["amount"] for t in months_present[m])
                    if month_total < (median_amount * up_ratio):
                        deficit = round(median_amount - month_total, 2)
                        findings.append(
                            MissingIncomeFinding(
                                finding_type="UNDERPAID_INCOME",
                                payer=payer,
                                expected_period=m,
                                expected_amount=median_amount,
                                actual_amount=month_total,
                                deficit_amount=deficit,
                                severity="MEDIUM",
                                confidence_score=0.85,
                                description=(
                                    f"Received ₹{month_total:,.2f} from {payer} in {m}, which is significantly below "
                                    f"the expected baseline of ₹{median_amount:,.2f} (shortfall of ₹{deficit:,.2f})."
                                ),
                                recommendation=(
                                    f"Review partial payment deductions (TDS, disputes, adjustments) with {payer}."
                                ),
                                related_transaction=months_present[m][0]["raw"],
                            )
                        )

        return streams, findings

    def _detect_uncollected_ledger_income(
        self,
        bank_credits: list[dict],
        ledger_transactions: list[dict],
        tolerance_days: int | None = None,
    ) -> list[MissingIncomeFinding]:
        """Detect income entries recorded in ledger that have no matching bank inflow."""
        tol_days = self.uncollected_tolerance_days if tolerance_days is None else int(tolerance_days)
        findings = []

        for l_tx in ledger_transactions:
            l_amt = _extract_credit_amount(l_tx)
            l_date = normalize_date_to_date(l_tx.get("transaction_date"))
            if l_amt <= 0 or l_date is None:
                continue

            l_desc = normalize_description(l_tx.get("description", ""))

            # Look for matching credit in bank statement within grace period
            found_match = False
            for b in bank_credits:
                amt_match = abs(b["amount"] - l_amt) <= 1.0  # ₹1 rounding tolerance
                date_diff = abs((b["date"] - l_date).days)
                if amt_match and date_diff <= tol_days:
                    found_match = True
                    break

            if not found_match:
                findings.append(
                    MissingIncomeFinding(
                        finding_type="UNCOLLECTED_ACCRUED_INCOME",
                        payer=l_tx.get("description", "Ledger Revenue Entry"),
                        expected_period=l_date.isoformat(),
                        expected_amount=l_amt,
                        actual_amount=0.0,
                        deficit_amount=l_amt,
                        severity="HIGH" if l_amt >= 50000.0 else "MEDIUM",
                        confidence_score=0.88,
                        description=(
                            f"Ledger records accrued income of ₹{l_amt:,.2f} on {l_date.isoformat()} "
                            f"('{l_tx.get('description', '')}'), but no corresponding bank credit was found "
                            f"within {tol_days} days."
                        ),
                        recommendation=(
                            "Reconcile against accounts receivable; confirm if invoice is outstanding, "
                            "disputed, or deposited into a different bank account."
                        ),
                        related_transaction=l_tx,
                    )
                )

        return findings


# Module-level convenience function
def detect_missing_income(
    bank_transactions: list[dict],
    ledger_transactions: list[dict] | None = None,
    as_of_date: date | str | None = None,
    underpayment_ratio_threshold: float = 0.70,
    uncollected_tolerance_days: int = 30,
) -> dict[str, Any]:
    """Convenience helper to run missing income detection pipeline."""
    detector = MissingIncomeDetector(
        underpayment_ratio_threshold=underpayment_ratio_threshold,
        uncollected_tolerance_days=uncollected_tolerance_days,
    )
    return detector.detect(
        bank_transactions=bank_transactions,
        ledger_transactions=ledger_transactions,
        as_of_date=as_of_date,
    )

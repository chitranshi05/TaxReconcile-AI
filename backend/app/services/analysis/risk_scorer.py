"""
backend/app/services/analysis/risk_scorer.py

Financial & Tax Risk Scoring Engine.

Calculates explainable, calibrated financial risk scores (0 to 100) for:
1. Individual Transactions: Multi-signal scoring combining statutory penalties,
   reconciliation discrepancy state, anomaly indicators, and monetary magnitude.
2. Reconciliation Runs / Portfolios: Aggregate risk score, audit exposure index,
   and qualitative grade (A, B, C, D, F).
"""

from __future__ import annotations

import math
from typing import Any


class RiskScorer:
    """
    Calculates explainable financial and statutory tax risk scores.
    """

    @classmethod
    def score_transaction(cls, tx: dict[str, Any]) -> dict[str, Any]:
        """
        Calculate an explainable risk score (0 - 100) for a single transaction.
        """
        base_score = 0.0
        risk_components: dict[str, float] = {}
        risk_factors: list[str] = []

        amt = abs(float(tx.get("amount") or tx.get("net_amount") or tx.get("debit") or tx.get("credit") or 0.0))
        desc = str(tx.get("description", "")).lower()
        status = str(tx.get("status", "")).upper()
        is_deductible = tx.get("is_tax_deductible")

        # 1. Statutory Compliance Triggers (0 - 50 pts)
        statutory_score = 0.0

        # Section 269ST: Cash receipt >= 2,00,000
        if any(w in desc for w in ("cash", "cdm deposit", "by cash")) and amt >= 200000.0:
            statutory_score += 45.0
            risk_factors.append("Section 269ST breach: Cash receipt of ₹2,00,000+ attracts 100% penalty u/s 271DA.")

        # Section 40A(3): Cash business payment > 10,000
        if any(w in desc for w in ("cash", "atm")) and amt > 10000.0 and is_deductible is True:
            statutory_score += 30.0
            risk_factors.append("Section 40A(3) disallowance: Cash payment > ₹10,000 cannot be claimed as business expense.")

        # High-value SFT reportable (₹10 Lakh+)
        if amt >= 1000000.0:
            statutory_score += 20.0
            risk_factors.append("High-value transaction (₹10 Lakh+) routinely flagged for SFT scrutiny u/s 285BA.")

        # Section 68: Unexplained bank credit
        if status == "BANK_ONLY" and (tx.get("credit") or (tx.get("amount") and float(tx.get("amount", 0)) > 0)):
            statutory_score += 25.0
            risk_factors.append("Unexplained bank deposit without ledger entry risks addition as income under Section 68.")

        statutory_score = min(50.0, statutory_score)
        risk_components["statutory_compliance"] = round(statutory_score, 1)

        # 2. Reconciliation Discrepancy Risk (0 - 30 pts)
        rec_score = 0.0
        if status == "AMOUNT_MISMATCH":
            variance = abs(float(tx.get("amount_variance", 0.0)))
            rec_score = min(30.0, 20.0 + min(10.0, variance / 1000.0))
            risk_factors.append(f"Reconciliation variance of ₹{variance:,.2f} between bank and ledger.")
        elif status == "BANK_ONLY":
            rec_score = 25.0
            risk_factors.append("Transaction appears in bank statement with no corresponding ledger booking.")
        elif status == "LEDGER_ONLY":
            rec_score = 15.0
            risk_factors.append("Transaction entered in ledger but never realized or cleared in bank account.")
        elif status == "POTENTIAL_MATCH":
            rec_score = 8.0
            risk_factors.append("Tentative reconciliation match requiring human review.")
        elif status == "MATCHED":
            rec_score = 0.0

        risk_components["reconciliation_discrepancy"] = round(rec_score, 1)

        # 3. Anomaly & Outlier Risk (0 - 25 pts)
        anom_score = 0.0
        if tx.get("is_anomaly"):
            flags = tx.get("anomaly_flags", [])
            if "UNUSUALLY_LARGE_AMOUNT" in flags:
                anom_score += 15.0
                risk_factors.append("Statistical outlier: Amount significantly exceeds dataset normal upper bound.")
            if "REPEATED_ROUND_AMOUNT" in flags:
                anom_score += 10.0
                risk_factors.append("Repeated round monetary figure observed across statements.")
            if "HIGH_TRANSACTION_FREQUENCY" in flags:
                anom_score += 8.0
                risk_factors.append("High-frequency transaction burst on the same date.")
            if "UNUSUAL_DEBIT" in flags or "UNUSUAL_CREDIT" in flags:
                anom_score += 10.0
                risk_factors.append("Directional statistical outlier.")

        if tx.get("is_ml_anomaly"):
            ml_score = float(tx.get("ml_anomaly_score", 0.5))
            anom_score += min(15.0, ml_score * 15.0)
            risk_factors.append(f"Unsupervised ML Isolation Forest flagged multivariate anomaly ({ml_score:.2f}).")

        anom_score = min(25.0, anom_score)
        risk_components["anomaly_signals"] = round(anom_score, 1)

        # 4. Monetary Magnitude Multiplier
        # Larger amounts scale the final score slightly up to 10 pts
        magnitude_score = 0.0
        if amt > 0:
            # Scale log10: ₹10,000 = 4, ₹1,00,000 = 5, ₹10,00,000 = 6
            magnitude_score = min(10.0, max(0.0, (math.log10(amt) - 3.0) * 2.5))
        risk_components["monetary_exposure"] = round(magnitude_score, 1)

        total_score = min(100.0, round(statutory_score + rec_score + anom_score + magnitude_score, 1))

        risk_tier = cls.score_to_tier(total_score)

        return {
            "risk_score": total_score,
            "risk_tier": risk_tier,
            "components": risk_components,
            "risk_factors": risk_factors,
            "audit_scrutiny_priority": "CRITICAL" if total_score >= 80 else ("HIGH" if total_score >= 60 else ("MEDIUM" if total_score >= 35 else "LOW")),
        }

    @classmethod
    def score_reconciliation_run(
        cls,
        summary: dict[str, Any],
        matches: list[dict[str, Any]],
        bank_only: list[dict[str, Any]],
        ledger_only: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Compute an aggregate risk score and health grade for an entire reconciliation run.
        """
        total_tx = max(1, summary.get("total_bank_transactions", 0) + summary.get("total_ledger_transactions", 0))
        mismatched_cnt = summary.get("amount_mismatch_count", 0)
        bank_only_cnt = len(bank_only)
        ledger_only_cnt = len(ledger_only)
        potential_cnt = summary.get("potential_match_count", 0)

        # Discrepancy ratios
        unreconciled_ratio = (mismatched_cnt + bank_only_cnt + ledger_only_cnt) / total_tx
        net_discrepancy = abs(float(summary.get("net_discrepancy", 0.0)))
        total_amount = max(1.0, float(summary.get("total_bank_amount", 0.0)) + float(summary.get("total_ledger_amount", 0.0)))
        amount_exposure_ratio = min(1.0, net_discrepancy / total_amount)

        # Component scores
        discrepancy_score = min(50.0, unreconciled_ratio * 100.0)
        financial_exposure_score = min(30.0, amount_exposure_ratio * 100.0 * 2.0)
        review_overhead_score = min(20.0, (potential_cnt / total_tx) * 50.0)

        total_run_risk = min(100.0, round(discrepancy_score + financial_exposure_score + review_overhead_score, 1))

        grade = cls.score_to_grade(total_run_risk)

        return {
            "overall_risk_score": total_run_risk,
            "health_grade": grade,
            "risk_level": cls.score_to_tier(total_run_risk),
            "unreconciled_transactions_count": mismatched_cnt + bank_only_cnt + ledger_only_cnt,
            "unreconciled_ratio_pct": round(unreconciled_ratio * 100.0, 1),
            "net_financial_discrepancy": round(net_discrepancy, 2),
            "risk_breakdown": {
                "unreconciled_volume_risk": round(discrepancy_score, 1),
                "financial_exposure_risk": round(financial_exposure_score, 1),
                "review_overhead_risk": round(review_overhead_score, 1),
            },
        }

    @staticmethod
    def score_to_tier(score: float) -> str:
        """Map a numeric risk score (0-100) to qualitative risk tier."""
        if score >= 75.0:
            return "CRITICAL"
        if score >= 50.0:
            return "HIGH"
        if score >= 25.0:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def score_to_grade(score: float) -> str:
        """Map a run risk score (0-100) to an audit readiness grade."""
        if score <= 15.0:
            return "A"
        if score <= 30.0:
            return "B"
        if score <= 50.0:
            return "C"
        if score <= 70.0:
            return "D"
        return "F"


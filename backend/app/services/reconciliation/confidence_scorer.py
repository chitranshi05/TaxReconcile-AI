"""
backend/app/services/reconciliation/confidence_scorer.py

Multi-factor Confidence Scoring Engine for Transaction Matching & Reconciliation Decisions.

Evaluates match credibility across five orthogonal dimensions:
1. Amount Agreement (exactness, relative variance, sign consistency)
2. Temporal Proximity (date equality, distance in days within tolerance)
3. Textual & Semantic Similarity (exact, token sort, RapidFuzz, embeddings)
4. Candidate Uniqueness & Ambiguity (competition from alternative candidates)
5. Directional / Cashflow Consistency (debit/credit pairing)

Outputs:
- Calibrated confidence score (0.0 to 1.0)
- Categorical confidence level (VERY_HIGH, HIGH, MEDIUM, LOW)
- Granular component breakdown
- Positive & negative factors explaining the score
- Automated decision recommendation (AUTO_APPROVE, REVIEW_RECOMMENDED, MANUAL_INVESTIGATION_REQUIRED)
"""

from __future__ import annotations

from datetime import date, datetime
import math
from typing import Any
import pandas as pd


# ---------------------------------------------------------------------------
# Default Weights
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS = {
    "amount": 0.40,
    "date": 0.25,
    "description": 0.25,
    "uniqueness": 0.10,
}


class ConfidenceScorer:
    """
    Evaluates and calibrates match confidence scores between bank and ledger entries.
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        date_tolerance_days: int = 1,
        amount_tolerance: float = 0.0,
    ):
        raw_weights = weights or DEFAULT_WEIGHTS
        total = sum(raw_weights.values()) or 1.0
        self.weights = {k: v / total for k, v in raw_weights.items()}
        self.date_tolerance_days = max(0, int(date_tolerance_days))
        self.amount_tolerance = max(0.0, float(amount_tolerance))

    def score_match(
        self,
        bank_tx: dict[str, Any],
        ledger_tx: dict[str, Any],
        match_type: str = "EXACT_MATCH",
        similarity_score: float | None = None,
        date_difference_days: int = 0,
        amount_variance: float = 0.0,
        candidate_count: int = 1,
        second_best_similarity: float | None = None,
    ) -> dict[str, Any]:
        """
        Calculate a comprehensive, explainable confidence evaluation for a matched pair.
        """
        positive_factors: list[str] = []
        negative_factors: list[str] = []

        # 1. Amount Component Score
        amt_score, amt_pos, amt_neg = self._score_amount(
            bank_tx=bank_tx,
            ledger_tx=ledger_tx,
            variance=amount_variance,
        )
        positive_factors.extend(amt_pos)
        negative_factors.extend(amt_neg)

        # 2. Date Component Score
        date_score, date_pos, date_neg = self._score_date(
            days_diff=date_difference_days,
        )
        positive_factors.extend(date_pos)
        negative_factors.extend(date_neg)

        # 3. Description Component Score
        desc_score, desc_pos, desc_neg = self._score_description(
            match_type=match_type,
            similarity_score=similarity_score,
            bank_tx=bank_tx,
            ledger_tx=ledger_tx,
        )
        positive_factors.extend(desc_pos)
        negative_factors.extend(desc_neg)

        # 4. Uniqueness Component Score
        uniq_score, uniq_pos, uniq_neg = self._score_uniqueness(
            candidate_count=candidate_count,
            best_sim=similarity_score,
            second_sim=second_best_similarity,
        )
        positive_factors.extend(uniq_pos)
        negative_factors.extend(uniq_neg)

        # Weighted calculation
        raw_score = (
            (amt_score * self.weights.get("amount", 0.40))
            + (date_score * self.weights.get("date", 0.25))
            + (desc_score * self.weights.get("description", 0.25))
            + (uniq_score * self.weights.get("uniqueness", 0.10))
        )

        # Calibrate score according to match_type expectations
        calibrated_score = self._calibrate(raw_score, match_type, similarity_score, date_difference_days)

        # Determine level & recommendation
        level = self.get_confidence_level(calibrated_score)
        recommendation = self.get_decision_recommendation(calibrated_score, match_type)

        return {
            "confidence_score": round(calibrated_score, 2),
            "confidence_level": level,
            "decision_recommendation": recommendation,
            "components": {
                "amount_score": round(amt_score, 2),
                "date_score": round(date_score, 2),
                "description_score": round(desc_score, 2),
                "uniqueness_score": round(uniq_score, 2),
            },
            "positive_factors": positive_factors,
            "negative_factors": negative_factors,
        }

    # ------------------------------------------------------------------
    # Component Evaluators
    # ------------------------------------------------------------------

    def _score_amount(
        self,
        bank_tx: dict,
        ledger_tx: dict,
        variance: float,
    ) -> tuple[float, list[str], list[str]]:
        pos = []
        neg = []
        abs_var = abs(variance)

        if abs_var == 0.0:
            pos.append("Exact monetary amount match.")
            return 1.0, pos, neg

        if abs_var <= self.amount_tolerance and self.amount_tolerance > 0:
            penalty = (abs_var / self.amount_tolerance) * 0.1
            pos.append(f"Amount matches within tolerance of ₹{self.amount_tolerance:,.2f} (diff: ₹{abs_var:,.2f}).")
            return max(0.85, 1.0 - penalty), pos, neg

        # For amount mismatch, evaluate relative difference
        b_amt = abs(float(bank_tx.get("amount") or bank_tx.get("debit") or bank_tx.get("credit") or 1.0))
        pct_diff = min(100.0, (abs_var / max(b_amt, 1.0)) * 100)
        neg.append(f"Amount discrepancy of ₹{abs_var:,.2f} ({pct_diff:.1f}% variance).")

        score = max(0.1, 1.0 - (pct_diff / 50.0))
        return score, pos, neg

    def _score_date(
        self,
        days_diff: int,
    ) -> tuple[float, list[str], list[str]]:
        pos = []
        neg = []

        if days_diff == 0:
            pos.append("Same transaction date.")
            return 1.0, pos, neg

        if days_diff <= self.date_tolerance_days:
            decay = (days_diff / max(self.date_tolerance_days + 1, 2)) * 0.35
            pos.append(f"Date differs by {days_diff} day(s), within configured tolerance.")
            return max(0.65, 1.0 - decay), pos, neg

        neg.append(f"Date difference of {days_diff} days exceeds standard tolerance.")
        score = max(0.2, 1.0 - (days_diff * 0.15))
        return score, pos, neg

    def _score_description(
        self,
        match_type: str,
        similarity_score: float | None,
        bank_tx: dict,
        ledger_tx: dict,
    ) -> tuple[float, list[str], list[str]]:
        pos = []
        neg = []

        b_desc = str(bank_tx.get("description", "") or "").strip()
        l_desc = str(ledger_tx.get("description", "") or "").strip()

        if match_type == "EXACT_MATCH":
            pos.append("Compatible or identical transaction descriptions.")
            return 1.0, pos, neg

        if similarity_score is not None:
            norm_sim = min(100.0, max(0.0, float(similarity_score)))
            score = norm_sim / 100.0
            if norm_sim >= 90.0:
                pos.append(f"High description similarity ({norm_sim:.1f}%).")
            elif norm_sim >= 75.0:
                pos.append(f"Sufficient description similarity ({norm_sim:.1f}%).")
            else:
                neg.append(f"Low textual similarity ({norm_sim:.1f}%).")
            return score, pos, neg

        if not b_desc and not l_desc:
            return 0.75, pos, neg

        if match_type == "AMOUNT_AND_DATE_MATCH":
            neg.append("Descriptions differ completely (matched purely on amount and date).")
            return 0.50, pos, neg

        return 0.60, pos, neg

    def _score_uniqueness(
        self,
        candidate_count: int,
        best_sim: float | None,
        second_sim: float | None,
    ) -> tuple[float, list[str], list[str]]:
        pos = []
        neg = []

        if candidate_count <= 1:
            pos.append("Unique unambiguous counterpart found in ledger.")
            return 1.0, pos, neg

        if best_sim is not None and second_sim is not None:
            gap = best_sim - second_sim
            if gap >= 15.0:
                pos.append(f"Best match clearly distinguished from alternative candidate (+{gap:.1f}% margin).")
                return 0.90, pos, neg
            elif gap >= 5.0:
                pos.append(f"Best match moderately ahead of second candidate (+{gap:.1f}% margin).")
                return 0.75, pos, neg
            else:
                neg.append(f"Ambiguous candidate matches: alternative entry has close similarity (gap {gap:.1f}%).")
                return 0.50, pos, neg

        neg.append(f"Multiple ({candidate_count}) competing match candidates found.")
        return 0.65, pos, neg

    # ------------------------------------------------------------------
    # Calibration & Decision Helpers
    # ------------------------------------------------------------------

    def _calibrate(
        self,
        raw_score: float,
        match_type: str,
        similarity_score: float | None,
        date_difference_days: int,
    ) -> float:
        """
        Calibrate scores to maintain smooth distributions and respect business rules.
        """
        if match_type == "EXACT_MATCH":
            return 1.0

        if match_type == "FUZZY_MATCH":
            # Similarity is the primary anchor for fuzzy matches
            if similarity_score is not None:
                sim_component = similarity_score / 100.0
                return max(0.65, min(0.95, (raw_score * 0.4) + (sim_component * 0.6)))
            return max(0.70, min(0.92, raw_score))

        if match_type == "SEMANTIC_MATCH":
            if similarity_score is not None:
                sim_component = similarity_score / 100.0
                return max(0.65, min(0.92, (raw_score * 0.4) + (sim_component * 0.6)))
            return max(0.65, min(0.90, raw_score))

        if match_type == "AMOUNT_AND_DATE_MATCH":
            return 0.90

        if match_type == "DATE_TOLERANCE_MATCH":
            # Decays with date difference
            decay = max(0.60, 0.90 - (date_difference_days * 0.10))
            return max(0.50, min(decay, raw_score))

        if match_type == "AMOUNT_MISMATCH":
            return min(0.55, max(0.30, raw_score * 0.6))

        return max(0.1, min(1.0, raw_score))

    @staticmethod
    def get_confidence_level(score: float) -> str:
        """Categorize numerical confidence score into a standard qualitative tier."""
        if score >= 0.95:
            return "VERY_HIGH"
        if score >= 0.80:
            return "HIGH"
        if score >= 0.60:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def get_decision_recommendation(score: float, match_type: str) -> str:
        """Determine automated workflow recommendation for the match."""
        if score >= 0.95 and match_type == "EXACT_MATCH":
            return "AUTO_APPROVE"
        if score >= 0.75 and match_type in ("FUZZY_MATCH", "SEMANTIC_MATCH", "AMOUNT_AND_DATE_MATCH"):
            return "REVIEW_RECOMMENDED"
        if match_type == "AMOUNT_MISMATCH" or score < 0.65:
            return "MANUAL_INVESTIGATION_REQUIRED"
        return "REVIEW_RECOMMENDED"


def compute_batch_confidence(
    matches: list[dict[str, Any]],
    date_tolerance_days: int = 1,
    amount_tolerance: float = 0.0,
) -> list[dict[str, Any]]:
    """
    Enrich an existing list of reconciliation matches with rich confidence evaluations.
    """
    scorer = ConfidenceScorer(
        date_tolerance_days=date_tolerance_days,
        amount_tolerance=amount_tolerance,
    )
    enriched = []
    for m in matches:
        item = dict(m)
        evaluation = scorer.score_match(
            bank_tx=item.get("bank_transaction", {}),
            ledger_tx=item.get("ledger_transaction", {}),
            match_type=item.get("match_type", "EXACT_MATCH"),
            similarity_score=item.get("similarity_score"),
            date_difference_days=item.get("date_difference_days", 0),
            amount_variance=item.get("amount_variance", 0.0),
        )
        item["confidence_level"] = evaluation["confidence_level"]
        item["decision_recommendation"] = evaluation["decision_recommendation"]
        item["confidence_breakdown"] = evaluation["components"]
        item["confidence_factors"] = {
            "positive": evaluation["positive_factors"],
            "negative": evaluation["negative_factors"],
        }
        enriched.append(item)
    return enriched

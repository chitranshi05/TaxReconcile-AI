from app.services.reconciliation.confidence_scorer import ConfidenceScorer
from datetime import date, datetime
import re
from typing import Any
import pandas as pd

from app.services.reconciliation.semantic_matcher import (
    compute_semantic_similarity,
    get_shared_concepts,
)

try:
    from rapidfuzz import fuzz
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False
    from difflib import SequenceMatcher


def normalize_date_to_date(value: Any) -> date | None:
    """
    Normalize various date representations into a python datetime.date object.
    Accepts datetime, date, pandas Timestamp, or strings.
    """
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


def normalize_description(value: Any) -> str:
    """
    Clean and normalize transaction descriptions for comparison.
    Lowercases, strips leading/trailing spaces, and collapses whitespace.
    """
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip().lower()
    return re.sub(r"\s+", " ", text)


def compute_description_similarity(desc1: Any, desc2: Any) -> float:
    """
    Compute a normalized similarity score (0.0 to 100.0) between two transaction descriptions.
    Uses RapidFuzz (combining fuzz.ratio and fuzz.token_sort_ratio) when available,
    falling back to difflib.SequenceMatcher.

    Handles character-level differences and token reordering (e.g. 'AMAZON PAYMENTS INDIA'
    vs 'INDIA AMAZON PAYMENTS').
    """
    d1 = normalize_description(desc1)
    d2 = normalize_description(desc2)

    if not d1 and not d2:
        return 100.0
    if not d1 or not d2:
        return 0.0
    if d1 == d2:
        return 100.0

    if _HAS_RAPIDFUZZ:
        char_ratio = fuzz.ratio(d1, d2)
        token_ratio = fuzz.token_sort_ratio(d1, d2)
        return float(max(char_ratio, token_ratio))
    else:
        char_ratio = SequenceMatcher(None, d1, d2).ratio() * 100.0
        sorted_d1 = " ".join(sorted(d1.split()))
        sorted_d2 = " ".join(sorted(d2.split()))
        token_ratio = SequenceMatcher(None, sorted_d1, sorted_d2).ratio() * 100.0
        return float(max(char_ratio, token_ratio))


def descriptions_match(desc1: str, desc2: str) -> bool:
    """
    Check if two normalized descriptions match or are substantially compatible for exact matching.
    Returns True if:
    - Exactly identical
    - One contains the other
    - Both have high token overlap
    """
    d1 = normalize_description(desc1)
    d2 = normalize_description(desc2)

    if not d1 or not d2:
        return True  # If either is missing, do not penalize matching

    if d1 == d2:
        return True

    if d1 in d2 or d2 in d1:
        return True

    tokens1 = set(d1.split())
    tokens2 = set(d2.split())

    if not tokens1 or not tokens2:
        return True

    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)

    return (len(intersection) / len(union)) >= 0.4


def extract_amount(tx: dict) -> float | None:
    """
    Extract a normalized numerical monetary amount from a transaction dict.
    Supports 'amount' field or 'debit'/'credit' fields.
    """
    amount = tx.get("amount")
    if amount is not None and not pd.isna(amount) and str(amount).strip() != "":
        try:
            return round(float(amount), 2)
        except (ValueError, TypeError):
            pass

    debit = tx.get("debit")
    credit = tx.get("credit")

    def _to_float(v):
        if v is None or pd.isna(v) or str(v).strip() == "":
            return 0.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

    deb_val = _to_float(debit)
    crd_val = _to_float(credit)

    if deb_val > 0 and crd_val == 0:
        return round(-deb_val, 2)
    if crd_val > 0 and deb_val == 0:
        return round(crd_val, 2)
    if deb_val > 0 and crd_val > 0:
        return round(crd_val - deb_val, 2)

    return None


def extract_absolute_amount(tx: dict) -> float | None:
    """
    Extract absolute magnitude of transaction amount for direction-agnostic comparison.
    """
    amt = extract_amount(tx)
    return abs(amt) if amt is not None else None


class ReconciliationEngine:
    """
    Deterministic Bank vs Ledger Reconciliation Engine with Fuzzy Description Matching.
    Classifies transactions into:
    - MATCHED: Exact amount, exact date, matching description (or amount & date fallback).
    - POTENTIAL_MATCH: Exact amount with fuzzy description similarity (>= threshold) or date difference within tolerance.
    - AMOUNT_MISMATCH: Matching date and description with differing amounts.
    - BANK_ONLY: Transaction found only in the bank statement.
    - LEDGER_ONLY: Transaction found only in the company ledger.
    """

    def __init__(
        self,
        date_tolerance_days: int = 1,
        amount_tolerance: float = 0.0,
        fuzzy_threshold: float = 75.0,
        semantic_threshold: float = 70.0,
    ):
        self.date_tolerance_days = max(0, int(date_tolerance_days))
        self.amount_tolerance = max(0.0, float(amount_tolerance))
        self.fuzzy_threshold = max(0.0, min(100.0, float(fuzzy_threshold)))
        self.semantic_threshold = max(0.0, min(100.0, float(semantic_threshold)))

    def reconcile(
        self,
        bank_transactions: list[dict],
        ledger_transactions: list[dict],
    ) -> dict:
        """
        Execute deterministic reconciliation across bank and ledger entries.
        """
        bank_items = [dict(tx) for tx in bank_transactions]
        ledger_items = [dict(tx) for tx in ledger_transactions]

        # Enrich items with normalized dates and amounts
        for tx in bank_items:
            tx["_norm_date"] = normalize_date_to_date(tx.get("transaction_date"))
            tx["_norm_desc"] = normalize_description(tx.get("description"))
            tx["_norm_amt"] = extract_amount(tx)
            tx["_abs_amt"] = extract_absolute_amount(tx)

        for tx in ledger_items:
            tx["_norm_date"] = normalize_date_to_date(tx.get("transaction_date"))
            tx["_norm_desc"] = normalize_description(tx.get("description"))
            tx["_norm_amt"] = extract_amount(tx)
            tx["_abs_amt"] = extract_absolute_amount(tx)

        matched_bank_indices = set()
        matched_ledger_indices = set()

        matches = []

        def _amounts_match(amt1, amt2, abs1, abs2):
            if amt1 is None or amt2 is None:
                return False
            if abs(amt1 - amt2) <= self.amount_tolerance:
                return True
            if abs1 is not None and abs2 is not None:
                if abs(abs1 - abs2) <= self.amount_tolerance:
                    return True
            return False

        # Pass 1: Exact matches (Same date, matching description, matching amount)
        for b_idx, b_tx in enumerate(bank_items):
            if b_idx in matched_bank_indices:
                continue
            if b_tx["_norm_date"] is None or b_tx["_norm_amt"] is None:
                continue

            best_l_idx = None
            for l_idx, l_tx in enumerate(ledger_items):
                if l_idx in matched_ledger_indices:
                    continue
                if l_tx["_norm_date"] is None or l_tx["_norm_amt"] is None:
                    continue

                if b_tx["_norm_date"] == l_tx["_norm_date"]:
                    if _amounts_match(b_tx["_norm_amt"], l_tx["_norm_amt"], b_tx["_abs_amt"], l_tx["_abs_amt"]):
                        if descriptions_match(b_tx["_norm_desc"], l_tx["_norm_desc"]):
                            best_l_idx = l_idx
                            break

            if best_l_idx is not None:
                matched_bank_indices.add(b_idx)
                matched_ledger_indices.add(best_l_idx)
                matches.append({
                    "status": "MATCHED",
                    "match_type": "EXACT_MATCH",
                    "bank_transaction": self._clean_internal_keys(b_tx),
                    "ledger_transaction": self._clean_internal_keys(ledger_items[best_l_idx]),
                    "amount_variance": round(abs(b_tx["_abs_amt"] - ledger_items[best_l_idx]["_abs_amt"]), 2),
                    "date_difference_days": 0,
                    "confidence_score": 1.0,
                    "notes": "Exact match on date, normalized description, and amount.",
                })

        # Pass 2: Fuzzy Description Match (Same date, matching amount, description similarity >= fuzzy_threshold)
        # Evaluated before blind amount-and-date matching to prevent arbitrary assignment
        for b_idx, b_tx in enumerate(bank_items):
            if b_idx in matched_bank_indices:
                continue
            if b_tx["_norm_date"] is None or b_tx["_norm_amt"] is None:
                continue

            candidates = []
            for l_idx, l_tx in enumerate(ledger_items):
                if l_idx in matched_ledger_indices:
                    continue
                if l_tx["_norm_date"] is None or l_tx["_norm_amt"] is None:
                    continue

                if b_tx["_norm_date"] == l_tx["_norm_date"]:
                    if _amounts_match(b_tx["_norm_amt"], l_tx["_norm_amt"], b_tx["_abs_amt"], l_tx["_abs_amt"]):
                        similarity = compute_description_similarity(b_tx["_norm_desc"], l_tx["_norm_desc"])
                        if similarity >= self.fuzzy_threshold:
                            candidates.append((similarity, l_idx))

            if candidates:
                # Sort candidates by similarity descending
                candidates.sort(key=lambda x: x[0], reverse=True)
                best_sim, best_l_idx = candidates[0]

                # Check for ambiguity among candidates
                ambiguity_note = ""
                if len(candidates) > 1:
                    second_sim, _ = candidates[1]
                    if (best_sim - second_sim) < 5.0:
                        ambiguity_note = (
                            f" Note: multiple candidate ledger entries detected with close similarity "
                            f"({round(best_sim, 1)}% vs {round(second_sim, 1)}%)."
                        )

                matched_bank_indices.add(b_idx)
                matched_ledger_indices.add(best_l_idx)
                confidence = round(best_sim / 100.0, 2)
                notes = (
                    f"Fuzzy description match with similarity {round(best_sim, 1)}% "
                    f"(threshold {self.fuzzy_threshold}%).{ambiguity_note} Flagged for review."
                )

                matches.append({
                    "status": "POTENTIAL_MATCH",
                    "match_type": "FUZZY_MATCH",
                    "bank_transaction": self._clean_internal_keys(b_tx),
                    "ledger_transaction": self._clean_internal_keys(ledger_items[best_l_idx]),
                    "amount_variance": round(abs(b_tx["_abs_amt"] - ledger_items[best_l_idx]["_abs_amt"]), 2),
                    "date_difference_days": 0,
                    "confidence_score": confidence,
                    "similarity_score": round(best_sim, 2),
                    "notes": notes,
                })

        # Pass 3: Semantic Description Match (Same date, matching amount, semantic similarity >= semantic_threshold)
        # Identifies transactions with different wording but equivalent accounting/business meaning
        for b_idx, b_tx in enumerate(bank_items):
            if b_idx in matched_bank_indices:
                continue
            if b_tx["_norm_date"] is None or b_tx["_norm_amt"] is None:
                continue

            candidates = []
            for l_idx, l_tx in enumerate(ledger_items):
                if l_idx in matched_ledger_indices:
                    continue
                if l_tx["_norm_date"] is None or l_tx["_norm_amt"] is None:
                    continue

                if b_tx["_norm_date"] == l_tx["_norm_date"]:
                    if _amounts_match(b_tx["_norm_amt"], l_tx["_norm_amt"], b_tx["_abs_amt"], l_tx["_abs_amt"]):
                        sem_score = compute_semantic_similarity(b_tx["_norm_desc"], l_tx["_norm_desc"])
                        if sem_score >= self.semantic_threshold:
                            candidates.append((sem_score, l_idx))

            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                best_sim, best_l_idx = candidates[0]

                shared_concepts = get_shared_concepts(b_tx["_norm_desc"], ledger_items[best_l_idx]["_norm_desc"])
                concept_str = f" [Concept: {', '.join(shared_concepts)}]" if shared_concepts else ""

                ambiguity_note = ""
                if len(candidates) > 1:
                    second_sim, _ = candidates[1]
                    if (best_sim - second_sim) < 5.0:
                        ambiguity_note = (
                            f" Note: multiple candidate ledger entries detected with close semantic similarity "
                            f"({round(best_sim, 1)}% vs {round(second_sim, 1)}%)."
                        )

                matched_bank_indices.add(b_idx)
                matched_ledger_indices.add(best_l_idx)
                confidence = round(best_sim / 100.0, 2)
                notes = (
                    f"Semantic description match with similarity {round(best_sim, 1)}% "
                    f"(threshold {self.semantic_threshold}%){concept_str}.{ambiguity_note} Flagged for review."
                )

                matches.append({
                    "status": "POTENTIAL_MATCH",
                    "match_type": "SEMANTIC_MATCH",
                    "bank_transaction": self._clean_internal_keys(b_tx),
                    "ledger_transaction": self._clean_internal_keys(ledger_items[best_l_idx]),
                    "amount_variance": round(abs(b_tx["_abs_amt"] - ledger_items[best_l_idx]["_abs_amt"]), 2),
                    "date_difference_days": 0,
                    "confidence_score": confidence,
                    "similarity_score": round(best_sim, 2),
                    "matched_concepts": shared_concepts,
                    "notes": notes,
                })

        # Pass 4: Amount and Date Match (regardless of description differences)
        for b_idx, b_tx in enumerate(bank_items):
            if b_idx in matched_bank_indices:
                continue
            if b_tx["_norm_date"] is None or b_tx["_norm_amt"] is None:
                continue

            best_l_idx = None
            for l_idx, l_tx in enumerate(ledger_items):
                if l_idx in matched_ledger_indices:
                    continue
                if l_tx["_norm_date"] is None or l_tx["_norm_amt"] is None:
                    continue

                if b_tx["_norm_date"] == l_tx["_norm_date"]:
                    if _amounts_match(b_tx["_norm_amt"], l_tx["_norm_amt"], b_tx["_abs_amt"], l_tx["_abs_amt"]):
                        best_l_idx = l_idx
                        break

            if best_l_idx is not None:
                matched_bank_indices.add(b_idx)
                matched_ledger_indices.add(best_l_idx)
                matches.append({
                    "status": "MATCHED",
                    "match_type": "AMOUNT_AND_DATE_MATCH",
                    "bank_transaction": self._clean_internal_keys(b_tx),
                    "ledger_transaction": self._clean_internal_keys(ledger_items[best_l_idx]),
                    "amount_variance": round(abs(b_tx["_abs_amt"] - ledger_items[best_l_idx]["_abs_amt"]), 2),
                    "date_difference_days": 0,
                    "confidence_score": 0.9,
                    "notes": "Exact match on date and amount with differing descriptions.",
                })

        # Pass 5: Date tolerance matches (Potential match when dates differ within tolerance)
        if self.date_tolerance_days > 0:
            for b_idx, b_tx in enumerate(bank_items):
                if b_idx in matched_bank_indices:
                    continue
                if b_tx["_norm_date"] is None or b_tx["_norm_amt"] is None:
                    continue

                best_l_idx = None
                min_diff = None

                for l_idx, l_tx in enumerate(ledger_items):
                    if l_idx in matched_ledger_indices:
                        continue
                    if l_tx["_norm_date"] is None or l_tx["_norm_amt"] is None:
                        continue

                    if _amounts_match(b_tx["_norm_amt"], l_tx["_norm_amt"], b_tx["_abs_amt"], l_tx["_abs_amt"]):
                        diff_days = abs((b_tx["_norm_date"] - l_tx["_norm_date"]).days)
                        if 1 <= diff_days <= self.date_tolerance_days:
                            if min_diff is None or diff_days < min_diff:
                                min_diff = diff_days
                                best_l_idx = l_idx

                if best_l_idx is not None:
                    matched_bank_indices.add(b_idx)
                    matched_ledger_indices.add(best_l_idx)
                    matches.append({
                        "status": "POTENTIAL_MATCH",
                        "match_type": "DATE_TOLERANCE_MATCH",
                        "bank_transaction": self._clean_internal_keys(b_tx),
                        "ledger_transaction": self._clean_internal_keys(ledger_items[best_l_idx]),
                        "amount_variance": round(abs(b_tx["_abs_amt"] - ledger_items[best_l_idx]["_abs_amt"]), 2),
                        "date_difference_days": min_diff,
                        "confidence_score": round(max(0.6, 0.9 - (min_diff * 0.1)), 2),
                        "notes": (
                            f"Amount matches; transaction dates differ by {min_diff} day(s) "
                            f"(within tolerance of {self.date_tolerance_days} days). Flagged for review."
                        ),
                    })

        # Pass 6: Amount Mismatch (Same date and matching description, but differing amounts)
        for b_idx, b_tx in enumerate(bank_items):
            if b_idx in matched_bank_indices:
                continue
            if b_tx["_norm_date"] is None:
                continue

            best_l_idx = None
            for l_idx, l_tx in enumerate(ledger_items):
                if l_idx in matched_ledger_indices:
                    continue
                if l_tx["_norm_date"] is None:
                    continue

                if b_tx["_norm_date"] == l_tx["_norm_date"]:
                    if descriptions_match(b_tx["_norm_desc"], l_tx["_norm_desc"]):
                        best_l_idx = l_idx
                        break

            if best_l_idx is not None:
                matched_bank_indices.add(b_idx)
                matched_ledger_indices.add(best_l_idx)
                b_amt = b_tx["_abs_amt"] if b_tx["_abs_amt"] is not None else 0.0
                l_amt = ledger_items[best_l_idx]["_abs_amt"] if ledger_items[best_l_idx]["_abs_amt"] is not None else 0.0
                variance = round(b_amt - l_amt, 2)
                matches.append({
                    "status": "AMOUNT_MISMATCH",
                    "match_type": "AMOUNT_MISMATCH",
                    "bank_transaction": self._clean_internal_keys(b_tx),
                    "ledger_transaction": self._clean_internal_keys(ledger_items[best_l_idx]),
                    "amount_variance": variance,
                    "date_difference_days": 0,
                    "confidence_score": 0.5,
                    "notes": (
                        f"Matching date and description, but amounts differ "
                        f"(Bank: {b_amt}, Ledger: {l_amt}, Variance: {variance}). Flagged for review."
                    ),
                })

        # Unmatched entries
        bank_only = []
        for b_idx, b_tx in enumerate(bank_items):
            if b_idx not in matched_bank_indices:
                b_clean = self._clean_internal_keys(b_tx)
                b_clean["status"] = "BANK_ONLY"
                b_clean["notes"] = "Transaction appears in bank statement with no corresponding ledger entry."
                bank_only.append(b_clean)

        ledger_only = []
        for l_idx, l_tx in enumerate(ledger_items):
            if l_idx not in matched_ledger_indices:
                l_clean = self._clean_internal_keys(l_tx)
                l_clean["status"] = "LEDGER_ONLY"
                l_clean["notes"] = "Transaction appears in ledger with no corresponding bank statement entry."
                ledger_only.append(l_clean)

        # Enrich matches with multi-factor confidence scoring
        scorer = ConfidenceScorer(
            date_tolerance_days=self.date_tolerance_days,
            amount_tolerance=self.amount_tolerance,
        )
        for m in matches:
            evaluation = scorer.score_match(
                bank_tx=m.get("bank_transaction", {}),
                ledger_tx=m.get("ledger_transaction", {}),
                match_type=m.get("match_type", "EXACT_MATCH"),
                similarity_score=m.get("similarity_score"),
                date_difference_days=m.get("date_difference_days", 0),
                amount_variance=m.get("amount_variance", 0.0),
            )
            if "confidence_score" not in m:
                m["confidence_score"] = evaluation["confidence_score"]
            m["confidence_level"] = evaluation["confidence_level"]
            m["decision_recommendation"] = evaluation["decision_recommendation"]
            m["confidence_breakdown"] = evaluation["components"]
            m["confidence_factors"] = {
                "positive": evaluation["positive_factors"],
                "negative": evaluation["negative_factors"],
            }

        # Summary calculations
        matched_count = sum(1 for m in matches if m["status"] == "MATCHED")
        potential_match_count = sum(1 for m in matches if m["status"] == "POTENTIAL_MATCH")
        amount_mismatch_count = sum(1 for m in matches if m["status"] == "AMOUNT_MISMATCH")
        bank_only_count = len(bank_only)
        ledger_only_count = len(ledger_only)

        total_bank = len(bank_items)
        total_ledger = len(ledger_items)
        max_total = max(total_bank, total_ledger, 1)

        reconciliation_rate = round(
            ((matched_count + (potential_match_count * 0.5)) / max_total) * 100, 2
        )

        total_bank_amount = round(sum(tx["_abs_amt"] or 0.0 for tx in bank_items), 2)
        total_ledger_amount = round(sum(tx["_abs_amt"] or 0.0 for tx in ledger_items), 2)
        matched_amount = round(
            sum(m["bank_transaction"].get("amount") or 0.0 for m in matches if m["status"] == "MATCHED"), 2
        )
        net_discrepancy = round(total_bank_amount - total_ledger_amount, 2)

        return {
            "summary": {
                "total_bank_transactions": total_bank,
                "total_ledger_transactions": total_ledger,
                "matched_count": matched_count,
                "potential_match_count": potential_match_count,
                "amount_mismatch_count": amount_mismatch_count,
                "bank_only_count": bank_only_count,
                "ledger_only_count": ledger_only_count,
                "reconciliation_rate": reconciliation_rate,
                "total_bank_amount": total_bank_amount,
                "total_ledger_amount": total_ledger_amount,
                "matched_amount": matched_amount,
                "net_discrepancy": net_discrepancy,
            },
            "matches": matches,
            "bank_only": bank_only,
            "ledger_only": ledger_only,
        }

    @staticmethod
    def _clean_internal_keys(tx: dict) -> dict:
        """Remove temporary normalization keys from returned dictionary."""
        return {k: v for k, v in tx.items() if not k.startswith("_")}


def reconcile_transactions(
    bank_transactions: list[dict],
    ledger_transactions: list[dict],
    date_tolerance_days: int = 1,
    amount_tolerance: float = 0.0,
    fuzzy_threshold: float = 75.0,
    semantic_threshold: float = 70.0,
) -> dict:
    """Convenience helper to reconcile bank and ledger transactions."""
    engine = ReconciliationEngine(
        date_tolerance_days=date_tolerance_days,
        amount_tolerance=amount_tolerance,
        fuzzy_threshold=fuzzy_threshold,
        semantic_threshold=semantic_threshold,
    )
    return engine.reconcile(bank_transactions, ledger_transactions)

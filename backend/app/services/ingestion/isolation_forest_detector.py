"""
backend/app/services/ingestion/isolation_forest_detector.py

Isolation Forest – Unsupervised ML Anomaly Detector for Financial Transactions.

This module supplements the existing rule-based AnomalyDetector with an
unsupervised machine-learning pass. Isolation Forest works by randomly
partitioning the feature space; anomalous transactions are isolated
(require fewer partitions) and receive a low anomaly score.

Feature vector per transaction
-------------------------------
1. abs_amount          – Absolute monetary value (log-scaled)
2. day_of_month        – 1-31 (captures month-end clustering)
3. day_of_week         – 0-6 (Mon=0 … Sun=6)
4. is_round_number     – 1 if amount is a multiple of 1,000, else 0
5. daily_tx_count      – How many transactions share the same date
6. debit_flag          – 1 for debit, 0 for credit / unknown
7. amount_z_score      – Signed z-score within the dataset

Design principles
------------------
- Pure NumPy / scikit-learn; no network calls, no DB access.
- Graceful fallback: if scikit-learn is unavailable, detection is skipped
  and a clear warning note is returned.
- Minimum sample guard: requires at least `min_samples` transactions;
  otherwise returns an INSUFFICIENT_DATA note.
- Results are designed to be merged into the existing AnomalyDetector
  output dict rather than replace it.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from datetime import date, datetime
from typing import Any

import pandas as pd

try:
    import numpy as np
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_SAMPLES: int = 10          # Must have at least this many transactions
_DEFAULT_CONTAMINATION: float = 0.05  # Expected fraction of anomalies
_DEFAULT_N_ESTIMATORS: int = 100
_DEFAULT_RANDOM_STATE: int = 42
_ROUND_DENOM: float = 1000.0    # Multiples of ₹1,000 count as round numbers


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_date(value: Any) -> date | None:
    """Return a datetime.date from various input types, or None."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        text = str(value).strip()
        parsed = pd.to_datetime(text, errors="coerce", dayfirst=False)
        if pd.notna(parsed):
            return parsed.date()
    except Exception:
        pass
    return None


def _extract_abs_amount(tx: dict) -> float | None:
    """Return absolute monetary amount from a transaction dict, or None."""
    for key in ("amount", "abs_amount"):
        val = tx.get(key)
        if val is not None:
            try:
                v = float(str(val).replace(",", "").replace("₹", "").strip())
                if not math.isnan(v):
                    return abs(v)
            except (ValueError, TypeError):
                pass

    debit = tx.get("debit")
    credit = tx.get("credit")

    def _safe_float(v: Any) -> float:
        try:
            return float(str(v).replace(",", "").replace("₹", "").strip())
        except (ValueError, TypeError):
            return 0.0

    d = _safe_float(debit) if debit is not None else 0.0
    c = _safe_float(credit) if credit is not None else 0.0

    if d > 0 or c > 0:
        return abs(c - d) if (d > 0 and c > 0) else max(d, c)
    return None


def _is_debit(tx: dict) -> int:
    """Return 1 if transaction is a debit, 0 otherwise."""
    amount = tx.get("amount")
    if amount is not None:
        try:
            return 1 if float(amount) < 0 else 0
        except (ValueError, TypeError):
            pass
    return 1 if tx.get("debit") is not None and tx.get("credit") is None else 0


def _build_feature_matrix(
    tx_list: list[dict],
    date_counts: Counter,
) -> tuple[list[list[float]], list[int]]:
    """
    Build a 2-D feature matrix for the Isolation Forest.

    Returns
    -------
    features : list[list[float]]   – One row per transaction (may be empty)
    valid_indices : list[int]      – Original indices of rows included
    """
    abs_amounts: list[float] = []
    for tx in tx_list:
        a = _extract_abs_amount(tx)
        abs_amounts.append(a if a is not None else 0.0)

    # Compute z-scores inline to avoid extra numpy dependency at module level
    if _HAS_SKLEARN:
        arr = np.array(abs_amounts, dtype=float)
        mean = arr.mean()
        std = arr.std() if arr.std() > 0 else 1.0
        z_scores = ((arr - mean) / std).tolist()
    else:
        z_scores = [0.0] * len(tx_list)

    features: list[list[float]] = []
    valid_indices: list[int] = []

    for idx, tx in enumerate(tx_list):
        abs_amt = abs_amounts[idx]
        if abs_amt is None or abs_amt == 0.0:
            continue  # Skip transactions with no usable amount

        tx_date = _parse_date(tx.get("transaction_date"))
        dom = tx_date.day if tx_date else 15          # Day of month (default mid)
        dow = tx_date.weekday() if tx_date else 2     # Day of week (default Wed)
        date_str = tx_date.strftime("%Y-%m-%d") if tx_date else ""
        daily_count = date_counts.get(date_str, 1)

        log_amount = math.log1p(abs_amt)              # log(1+x) for stability
        is_round = 1.0 if (abs_amt >= _ROUND_DENOM and abs_amt % _ROUND_DENOM == 0) else 0.0
        debit_flag = float(_is_debit(tx))
        z = z_scores[idx]

        features.append([
            log_amount,     # 0 – log-scaled absolute amount
            float(dom),     # 1 – day of month
            float(dow),     # 2 – day of week
            is_round,       # 3 – round number indicator
            float(daily_count),  # 4 – daily transaction frequency
            debit_flag,     # 5 – debit flag
            z,              # 6 – z-score of amount
        ])
        valid_indices.append(idx)

    return features, valid_indices


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class IsolationForestDetector:
    """
    Wraps scikit-learn's IsolationForest to flag unusual financial transactions.

    Parameters
    ----------
    contamination : float
        Expected fraction of outliers in the data (0.0–0.5).
        Default 0.05 means roughly 5 % of transactions are expected to be
        anomalous.
    n_estimators : int
        Number of base estimators (trees) in the forest.
    random_state : int
        Seed for reproducibility.
    min_samples : int
        Minimum number of transactions needed to train the model.
    round_amount_min : float
        Amounts below this value are not counted as round numbers.
    """

    def __init__(
        self,
        contamination: float = _DEFAULT_CONTAMINATION,
        n_estimators: int = _DEFAULT_N_ESTIMATORS,
        random_state: int = _DEFAULT_RANDOM_STATE,
        min_samples: int = _MIN_SAMPLES,
        round_amount_min: float = _ROUND_DENOM,
    ):
        self.contamination = max(0.01, min(0.5, float(contamination)))
        self.n_estimators = max(10, int(n_estimators))
        self.random_state = int(random_state)
        self.min_samples = max(5, int(min_samples))
        self.round_amount_min = max(100.0, float(round_amount_min))

    def detect(self, transactions: list[dict] | pd.DataFrame) -> dict:
        """
        Run Isolation Forest anomaly detection on a list of transactions.

        Parameters
        ----------
        transactions : list[dict] or pd.DataFrame

        Returns
        -------
        dict with keys:
            ml_available      – bool
            status            – "SUCCESS" | "INSUFFICIENT_DATA" | "UNAVAILABLE"
            model_params      – dict of model configuration
            total_transactions – int
            anomalous_count   – int
            normal_count      – int
            anomaly_rate      – float (percentage)
            anomalies         – list[dict] – transactions flagged as anomalous
            all_scored        – list[dict] – every transaction with scores
            notes             – list[str]
            disclaimer        – str
        """
        if not _HAS_SKLEARN:
            return self._unavailable_result("scikit-learn is not installed. "
                                            "Run: pip install scikit-learn numpy")

        if isinstance(transactions, pd.DataFrame):
            tx_list = transactions.to_dict(orient="records")
        else:
            tx_list = [dict(t) for t in transactions]

        if len(tx_list) < self.min_samples:
            return self._insufficient_data_result(
                len(tx_list),
                f"Isolation Forest requires at least {self.min_samples} transactions; "
                f"got {len(tx_list)}.",
            )

        # Build date-frequency counter
        date_counts: Counter = Counter()
        for tx in tx_list:
            d = _parse_date(tx.get("transaction_date"))
            if d:
                date_counts[d.strftime("%Y-%m-%d")] += 1

        # Build feature matrix
        features, valid_indices = _build_feature_matrix(tx_list, date_counts)

        if len(features) < self.min_samples:
            return self._insufficient_data_result(
                len(features),
                f"Only {len(features)} transactions had parseable amounts; "
                f"need at least {self.min_samples} for a reliable model.",
            )

        X = np.array(features, dtype=float)

        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Train + predict
        model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=1,
        )
        predictions = model.fit_predict(X_scaled)        # +1 = normal, -1 = anomaly
        raw_scores = model.score_samples(X_scaled)       # More negative = more anomalous
        # Normalize scores to [0, 1] where 1 = most anomalous
        min_score = raw_scores.min()
        max_score = raw_scores.max()
        score_range = max_score - min_score if (max_score - min_score) > 0 else 1.0
        anomaly_scores = (1.0 - (raw_scores - min_score) / score_range)

        # Map results back to original transactions
        result_map: dict[int, dict] = {}
        for arr_idx, orig_idx in enumerate(valid_indices):
            is_anomaly = bool(predictions[arr_idx] == -1)
            score = float(round(anomaly_scores[arr_idx], 4))
            severity = _score_to_severity(score, is_anomaly)
            result_map[orig_idx] = {
                "is_ml_anomaly": is_anomaly,
                "ml_anomaly_score": score,     # 0 = normal, 1 = most anomalous
                "ml_severity": severity,
                "ml_flag": "ML_ISOLATION_FOREST" if is_anomaly else None,
                "ml_reason": (
                    _build_reason(features[arr_idx], score)
                    if is_anomaly else None
                ),
            }

        # Compose enriched transactions
        all_scored: list[dict] = []
        anomalies: list[dict] = []

        for orig_idx, tx in enumerate(tx_list):
            enriched = dict(tx)
            ml_info = result_map.get(orig_idx, {
                "is_ml_anomaly": False,
                "ml_anomaly_score": None,
                "ml_severity": "NORMAL",
                "ml_flag": None,
                "ml_reason": "No parseable amount; excluded from ML scoring.",
            })
            enriched.update(ml_info)
            # Serialise dates
            for key in ("transaction_date", "created_at", "updated_at"):
                val = enriched.get(key)
                if val is not None and hasattr(val, "isoformat"):
                    enriched[key] = val.isoformat()
            all_scored.append(enriched)
            if ml_info["is_ml_anomaly"]:
                anomalies.append(enriched)

        total = len(tx_list)
        anomaly_count = len(anomalies)
        anomaly_rate = round(anomaly_count / total * 100, 2) if total > 0 else 0.0

        return {
            "ml_available": True,
            "status": "SUCCESS",
            "model_params": {
                "algorithm": "IsolationForest",
                "contamination": self.contamination,
                "n_estimators": self.n_estimators,
                "random_state": self.random_state,
                "feature_names": [
                    "log_abs_amount",
                    "day_of_month",
                    "day_of_week",
                    "is_round_number",
                    "daily_tx_count",
                    "debit_flag",
                    "amount_z_score",
                ],
            },
            "total_transactions": total,
            "anomalous_count": anomaly_count,
            "normal_count": total - anomaly_count,
            "anomaly_rate": anomaly_rate,
            "anomalies": anomalies,
            "all_scored": all_scored,
            "notes": [
                "Isolation Forest detects multivariate outliers independent of rule-based heuristics.",
                "Scores are normalized to [0, 1]; higher scores indicate greater abnormality.",
                f"Contamination parameter set to {self.contamination} "
                f"(≈{int(self.contamination * 100)}% of transactions expected to be anomalous).",
            ],
            "disclaimer": (
                "ML anomaly scores indicate statistical unusualness, not confirmed fraud or errors. "
                "Human review is required before taking any action on flagged transactions."
            ),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _unavailable_result(self, reason: str) -> dict:
        return {
            "ml_available": False,
            "status": "UNAVAILABLE",
            "model_params": {},
            "total_transactions": 0,
            "anomalous_count": 0,
            "normal_count": 0,
            "anomaly_rate": 0.0,
            "anomalies": [],
            "all_scored": [],
            "notes": [reason],
            "disclaimer": "",
        }

    def _insufficient_data_result(self, count: int, reason: str) -> dict:
        return {
            "ml_available": True,
            "status": "INSUFFICIENT_DATA",
            "model_params": {
                "algorithm": "IsolationForest",
                "contamination": self.contamination,
                "n_estimators": self.n_estimators,
                "min_samples_required": self.min_samples,
                "actual_samples": count,
            },
            "total_transactions": count,
            "anomalous_count": 0,
            "normal_count": count,
            "anomaly_rate": 0.0,
            "anomalies": [],
            "all_scored": [],
            "notes": [reason],
            "disclaimer": (
                "Isolation Forest requires a minimum number of samples to produce "
                "reliable results. Add more transactions and retry."
            ),
        }


# ---------------------------------------------------------------------------
# Helpers used only internally
# ---------------------------------------------------------------------------

def _score_to_severity(score: float, is_anomaly: bool) -> str:
    """Map normalized anomaly score to a human-readable severity label."""
    if not is_anomaly:
        return "NORMAL"
    if score >= 0.80:
        return "HIGH"
    if score >= 0.60:
        return "MEDIUM"
    return "LOW"


def _build_reason(feature_row: list[float], score: float) -> str:
    """Generate a human-readable explanation for why a transaction was flagged."""
    log_amt, dom, dow, is_round, daily_count, debit_flag, z = feature_row
    abs_amt = math.expm1(log_amt)   # Reverse log1p

    parts: list[str] = [
        f"ML anomaly score: {score:.2f}/1.00."
    ]

    if abs(z) > 2.5:
        direction = "above" if z > 0 else "below"
        parts.append(f"Amount ₹{abs_amt:,.0f} is {abs(z):.1f}σ {direction} the dataset mean.")

    if daily_count >= 5:
        parts.append(f"Occurred on a high-activity date ({int(daily_count)} transactions that day).")

    if is_round:
        parts.append(f"Round-number amount ₹{abs_amt:,.0f}.")

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    dow_name = day_names[int(dow)] if 0 <= int(dow) <= 6 else "?"
    if int(dow) >= 5:
        parts.append(f"Transaction on a weekend ({dow_name}).")

    if int(dom) >= 28:
        parts.append(f"Month-end transaction (day {int(dom)}).")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def run_isolation_forest(
    transactions: list[dict] | pd.DataFrame,
    contamination: float = _DEFAULT_CONTAMINATION,
    n_estimators: int = _DEFAULT_N_ESTIMATORS,
    random_state: int = _DEFAULT_RANDOM_STATE,
    min_samples: int = _MIN_SAMPLES,
) -> dict:
    """
    Functional convenience wrapper around IsolationForestDetector.

    Parameters
    ----------
    transactions  : list of raw transaction dicts or a pandas DataFrame
    contamination : fraction of data expected to be anomalous (0.01–0.50)
    n_estimators  : number of trees in the ensemble
    random_state  : random seed for reproducibility
    min_samples   : minimum dataset size for model training

    Returns
    -------
    Detection result dict (see IsolationForestDetector.detect for schema).
    """
    detector = IsolationForestDetector(
        contamination=contamination,
        n_estimators=n_estimators,
        random_state=random_state,
        min_samples=min_samples,
    )
    return detector.detect(transactions)


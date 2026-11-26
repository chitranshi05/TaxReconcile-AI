"""
backend/app/services/ingestion/test_isolation_forest_detector.py

Unit tests for the Isolation Forest anomaly detector.

Tests cover:
- Happy-path detection with enough samples
- Insufficient data guard
- Feature extraction helpers
- Severity classification
- Reason generation
- Functional wrapper (run_isolation_forest)
- Graceful handling of transactions with missing amounts / dates
"""

from datetime import date
from unittest.mock import patch

import pytest

from app.services.ingestion.isolation_forest_detector import (
    IsolationForestDetector,
    _build_feature_matrix,
    _extract_abs_amount,
    _is_debit,
    _parse_date,
    _score_to_severity,
    run_isolation_forest,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_tx(
    amount: float | None = None,
    debit: float | None = None,
    credit: float | None = None,
    date_str: str = "2024-01-15",
    description: str = "Test transaction",
) -> dict:
    tx: dict = {"transaction_date": date_str, "description": description}
    if amount is not None:
        tx["amount"] = amount
    if debit is not None:
        tx["debit"] = debit
    if credit is not None:
        tx["credit"] = credit
    return tx


def _make_normal_dataset(n: int = 20) -> list[dict]:
    """Return n normal-ish transactions plus 1 obvious outlier."""
    txs = [
        _make_tx(amount=1000.0 + (i * 50), date_str=f"2024-01-{(i % 28) + 1:02d}")
        for i in range(n)
    ]
    # Inject one clear outlier
    txs.append(_make_tx(amount=9_999_999.0, date_str="2024-01-01"))
    return txs


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_iso_string(self):
        result = _parse_date("2024-03-15")
        assert result == date(2024, 3, 15)

    def test_datetime_object(self):
        from datetime import datetime
        result = _parse_date(datetime(2024, 6, 1, 10, 30))
        assert result == date(2024, 6, 1)

    def test_date_object(self):
        result = _parse_date(date(2024, 1, 1))
        assert result == date(2024, 1, 1)

    def test_none(self):
        assert _parse_date(None) is None

    def test_invalid_string(self):
        assert _parse_date("not-a-date") is None


# ---------------------------------------------------------------------------
# _extract_abs_amount
# ---------------------------------------------------------------------------

class TestExtractAbsAmount:
    def test_positive_amount(self):
        assert _extract_abs_amount({"amount": 5000.0}) == 5000.0

    def test_negative_amount(self):
        assert _extract_abs_amount({"amount": -3000.0}) == 3000.0

    def test_debit_only(self):
        assert _extract_abs_amount({"debit": 2500.0}) == 2500.0

    def test_credit_only(self):
        assert _extract_abs_amount({"credit": 1800.0}) == 1800.0

    def test_both_debit_credit(self):
        result = _extract_abs_amount({"debit": 100.0, "credit": 300.0})
        assert result == 200.0

    def test_no_amount(self):
        assert _extract_abs_amount({"description": "No amount"}) is None

    def test_string_amount(self):
        assert _extract_abs_amount({"amount": "₹1,500"}) == 1500.0


# ---------------------------------------------------------------------------
# _is_debit
# ---------------------------------------------------------------------------

class TestIsDebit:
    def test_negative_amount_is_debit(self):
        assert _is_debit({"amount": -500.0}) == 1

    def test_positive_amount_is_credit(self):
        assert _is_debit({"amount": 500.0}) == 0

    def test_debit_field_no_credit(self):
        assert _is_debit({"debit": 300.0}) == 1

    def test_credit_field(self):
        assert _is_debit({"credit": 300.0}) == 0


# ---------------------------------------------------------------------------
# _score_to_severity
# ---------------------------------------------------------------------------

class TestScoreToSeverity:
    def test_normal_transaction(self):
        assert _score_to_severity(0.9, is_anomaly=False) == "NORMAL"

    def test_high_severity(self):
        assert _score_to_severity(0.85, is_anomaly=True) == "HIGH"

    def test_medium_severity(self):
        assert _score_to_severity(0.65, is_anomaly=True) == "MEDIUM"

    def test_low_severity(self):
        assert _score_to_severity(0.40, is_anomaly=True) == "LOW"


# ---------------------------------------------------------------------------
# _build_feature_matrix
# ---------------------------------------------------------------------------

class TestBuildFeatureMatrix:
    def test_basic_matrix(self):
        txs = [
            _make_tx(amount=1000.0, date_str="2024-01-10"),
            _make_tx(amount=2000.0, date_str="2024-01-11"),
            _make_tx(amount=3000.0, date_str="2024-01-12"),
        ]
        from collections import Counter
        date_counts = Counter({"2024-01-10": 1, "2024-01-11": 1, "2024-01-12": 1})
        features, indices = _build_feature_matrix(txs, date_counts)
        assert len(features) == 3
        assert indices == [0, 1, 2]
        assert all(len(row) == 7 for row in features)

    def test_skips_no_amount(self):
        txs = [
            _make_tx(amount=1000.0, date_str="2024-01-10"),
            {"description": "No amount", "transaction_date": "2024-01-10"},
        ]
        from collections import Counter
        features, indices = _build_feature_matrix(txs, Counter())
        assert len(features) == 1
        assert indices == [0]


# ---------------------------------------------------------------------------
# IsolationForestDetector.detect
# ---------------------------------------------------------------------------

class TestIsolationForestDetector:
    def test_happy_path(self):
        txs = _make_normal_dataset(n=20)
        detector = IsolationForestDetector(contamination=0.05, min_samples=10)
        result = detector.detect(txs)

        assert result["status"] == "SUCCESS"
        assert result["ml_available"] is True
        assert result["total_transactions"] == 21
        assert result["anomalous_count"] >= 1          # The outlier should be caught
        assert 0.0 <= result["anomaly_rate"] <= 100.0
        assert len(result["all_scored"]) == 21
        assert len(result["anomalies"]) == result["anomalous_count"]

    def test_every_transaction_has_ml_fields(self):
        txs = _make_normal_dataset(n=15)
        detector = IsolationForestDetector(min_samples=10)
        result = detector.detect(txs)
        for tx in result["all_scored"]:
            assert "is_ml_anomaly" in tx
            assert "ml_severity" in tx

    def test_insufficient_data(self):
        txs = [_make_tx(amount=1000.0)] * 5
        detector = IsolationForestDetector(min_samples=10)
        result = detector.detect(txs)
        assert result["status"] == "INSUFFICIENT_DATA"
        assert result["anomalous_count"] == 0

    def test_empty_transactions(self):
        detector = IsolationForestDetector(min_samples=10)
        result = detector.detect([])
        assert result["status"] == "INSUFFICIENT_DATA"

    def test_dataframe_input(self):
        import pandas as pd
        txs = _make_normal_dataset(n=15)
        df = pd.DataFrame(txs)
        detector = IsolationForestDetector(min_samples=10)
        result = detector.detect(df)
        assert result["total_transactions"] == 16

    def test_sklearn_unavailable(self):
        txs = _make_normal_dataset(n=15)
        detector = IsolationForestDetector(min_samples=10)
        with patch(
            "app.services.ingestion.isolation_forest_detector._HAS_SKLEARN",
            False,
        ):
            result = detector.detect(txs)
        assert result["status"] == "UNAVAILABLE"
        assert result["ml_available"] is False

    def test_transactions_without_dates(self):
        """Transactions missing dates should not crash the detector."""
        txs = [{"amount": 1000.0 + i * 100} for i in range(15)]
        txs.append({"amount": 9_999_999.0})
        detector = IsolationForestDetector(min_samples=10)
        result = detector.detect(txs)
        assert result["status"] == "SUCCESS"

    def test_mixed_debit_credit_fields(self):
        txs = [
            _make_tx(debit=1000.0 + i * 50) for i in range(10)
        ] + [
            _make_tx(credit=800.0 + i * 30) for i in range(10)
        ]
        txs.append(_make_tx(debit=5_000_000.0))
        detector = IsolationForestDetector(min_samples=10)
        result = detector.detect(txs)
        assert result["status"] == "SUCCESS"

    def test_anomaly_score_range(self):
        txs = _make_normal_dataset(n=20)
        detector = IsolationForestDetector(min_samples=10)
        result = detector.detect(txs)
        for tx in result["all_scored"]:
            score = tx.get("ml_anomaly_score")
            if score is not None:
                assert 0.0 <= score <= 1.0

    def test_model_params_in_response(self):
        txs = _make_normal_dataset(n=15)
        detector = IsolationForestDetector(contamination=0.1, n_estimators=50)
        result = detector.detect(txs)
        params = result["model_params"]
        assert params["algorithm"] == "IsolationForest"
        assert params["contamination"] == 0.1
        assert params["n_estimators"] == 50


# ---------------------------------------------------------------------------
# run_isolation_forest (functional wrapper)
# ---------------------------------------------------------------------------

class TestRunIsolationForest:
    def test_wrapper_returns_dict(self):
        txs = _make_normal_dataset(n=15)
        result = run_isolation_forest(txs)
        assert isinstance(result, dict)
        assert "status" in result

    def test_wrapper_passes_params(self):
        txs = _make_normal_dataset(n=15)
        result = run_isolation_forest(
            txs,
            contamination=0.10,
            n_estimators=50,
            random_state=7,
            min_samples=10,
        )
        assert result["model_params"]["contamination"] == 0.10
        assert result["model_params"]["n_estimators"] == 50

    def test_outlier_flagged(self):
        """The 9.9M outlier should appear in the anomalies list."""
        txs = _make_normal_dataset(n=20)
        result = run_isolation_forest(txs, contamination=0.05, min_samples=10)
        if result["status"] == "SUCCESS":
            flagged_amounts = [
                tx.get("amount") for tx in result["anomalies"]
            ]
            assert 9_999_999.0 in flagged_amounts


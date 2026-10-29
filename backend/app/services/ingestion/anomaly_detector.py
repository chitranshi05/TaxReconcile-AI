"""
Transaction Anomaly Detection Engine.

Goal: Identify unusual financial transactions that may require investigation before tax filing:
1. Unusually large transactions (Statistical Outliers via IQR on absolute amounts).
2. Unusual debit or credit amounts (Separate IQR evaluations for debits and credits).
3. Repeated round amounts (Frequent round-figure transfers e.g. ₹50,000 or ₹1,00,000).
4. Unusual transaction frequency (Abnormally high count of transactions in a short period).
5. Comprehensive statistical summary & human-friendly review reasons.

Important: An anomaly is not necessarily fraud or a tax violation. The system
flags suspicious patterns for human review rather than declaring a transaction fraudulent.
"""

from collections import Counter
from datetime import date, datetime
import re
from typing import Any
import pandas as pd


# ---------------------------------------------------------------------------
# Helper Normalization Functions
# ---------------------------------------------------------------------------

def normalize_date_str(value: Any) -> str | None:
    """
    Extract a normalized 'YYYY-MM-DD' date string from various representations
    (datetime, date, pandas Timestamp, or strings).
    """
    if value is None or pd.isna(value):
        return None

    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")

    try:
        text = str(value).strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}", text):
            parsed = pd.to_datetime(text, errors="coerce")
        else:
            parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)

        if pd.notna(parsed):
            return parsed.strftime("%Y-%m-%d")
    except Exception:
        pass

    return None


def extract_amount_details(tx: dict) -> dict:
    """
    Extract normalized monetary details from a transaction dict.
    Returns:
        {
            "net_amount": float | None,
            "abs_amount": float | None,
            "debit": float | None,
            "credit": float | None,
            "type": "DEBIT" | "CREDIT" | "NET" | "UNKNOWN"
        }
    """
    def _parse_num(val: Any) -> float | None:
        if val is None or pd.isna(val) or str(val).strip() == "":
            return None
        text = str(val).strip()
        # Clean currency symbols
        for sym in ("₹", "$", "€", "£", ","):
            text = text.replace(sym, "")
        try:
            return round(float(text), 2)
        except (ValueError, TypeError):
            return None

    amt_val = _parse_num(tx.get("amount"))
    deb_val = _parse_num(tx.get("debit"))
    crd_val = _parse_num(tx.get("credit"))

    net_amt = None
    abs_amt = None
    tx_type = "UNKNOWN"

    if amt_val is not None:
        net_amt = amt_val
        abs_amt = abs(amt_val)
        tx_type = "DEBIT" if net_amt < 0 else "CREDIT"
    elif deb_val is not None or crd_val is not None:
        d = deb_val or 0.0
        c = crd_val or 0.0
        if d > 0 and c == 0:
            net_amt = -d
            abs_amt = d
            tx_type = "DEBIT"
        elif c > 0 and d == 0:
            net_amt = c
            abs_amt = c
            tx_type = "CREDIT"
        else:
            net_amt = round(c - d, 2)
            abs_amt = abs(net_amt)
            tx_type = "DEBIT" if net_amt < 0 else "CREDIT"

    return {
        "net_amount": net_amt,
        "abs_amount": abs_amt,
        "debit": deb_val,
        "credit": crd_val,
        "type": tx_type,
    }


def compute_iqr_bounds(
    values: list[float],
    multiplier: float = 1.5,
    min_samples: int = 4,
) -> dict:
    """
    Compute statistical distribution metrics using the Interquartile Range (IQR):
    - Q1 = 25th percentile
    - Q3 = 75th percentile
    - IQR = Q3 - Q1
    - Lower bound = Q1 - (multiplier * IQR)
    - Upper bound = Q3 + (multiplier * IQR)

    If sample size is smaller than min_samples, returns an insufficient status.
    """
    clean_values = [float(v) for v in values if v is not None and pd.notna(v)]

    if len(clean_values) < min_samples:
        return {
            "status": "INSUFFICIENT_DATA",
            "count": len(clean_values),
            "min_samples_required": min_samples,
            "q1": None,
            "q3": None,
            "iqr": None,
            "lower_bound": None,
            "upper_bound": None,
            "mean": round(float(pd.Series(clean_values).mean()), 2) if clean_values else None,
            "median": round(float(pd.Series(clean_values).median()), 2) if clean_values else None,
            "min": min(clean_values) if clean_values else None,
            "max": max(clean_values) if clean_values else None,
        }

    series = pd.Series(clean_values)
    q1 = float(series.quantile(0.25))
    q3 = float(series.quantile(0.75))
    iqr = q3 - q1
    lower_bound = round(q1 - (multiplier * iqr), 2)
    upper_bound = round(q3 + (multiplier * iqr), 2)

    return {
        "status": "VALID",
        "count": len(clean_values),
        "q1": round(q1, 2),
        "q3": round(q3, 2),
        "iqr": round(iqr, 2),
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "mean": round(float(series.mean()), 2),
        "median": round(float(series.median()), 2),
        "min": round(float(series.min()), 2),
        "max": round(float(series.max()), 2),
    }


def is_round_number(amount: float | None, min_value: float = 1000.0) -> bool:
    """
    Determine if an amount represents a clean round monetary figure
    (e.g., ₹1,000, ₹5,000, ₹10,000, ₹50,000, ₹1,00,000).
    """
    if amount is None or amount < min_value:
        return False

    # Check common round denominations: 1000, 5000, 10000, 50000, 100000
    if amount % 1000 == 0:
        return True

    return False


# ---------------------------------------------------------------------------
# Main Anomaly Detection Class and Runner
# ---------------------------------------------------------------------------

class AnomalyDetector:
    """
    Configurable Anomaly Detector for financial transactions.
    """

    def __init__(
        self,
        iqr_multiplier: float = 1.5,
        min_samples_for_iqr: int = 4,
        frequency_threshold: int = 10,
        round_amount_min: float = 5000.0,
        round_amount_min_occurrences: int = 2,
        separate_debit_credit: bool = True,
    ):
        self.iqr_multiplier = max(1.0, float(iqr_multiplier))
        self.min_samples_for_iqr = max(3, int(min_samples_for_iqr))
        self.frequency_threshold = max(2, int(frequency_threshold))
        self.round_amount_min = max(100.0, float(round_amount_min))
        self.round_amount_min_occurrences = max(2, int(round_amount_min_occurrences))
        self.separate_debit_credit = bool(separate_debit_credit)

    def detect(self, transactions: list[dict] | pd.DataFrame) -> dict:
        """
        Run anomaly detection across transaction list or dataframe.
        """
        if isinstance(transactions, pd.DataFrame):
            tx_list = transactions.to_dict(orient="records")
        else:
            tx_list = [dict(t) for t in transactions]

        if not tx_list:
            return self._empty_result()

        notes = []

        # Step 1: Preprocessing & Normalization
        enriched_items = []
        all_abs_amounts = []
        all_debits = []
        all_credits = []
        date_counts: Counter = Counter()

        for idx, tx in enumerate(tx_list):
            amt_info = extract_amount_details(tx)
            date_str = normalize_date_str(tx.get("transaction_date"))
            source_row = tx.get("source_row", idx + 1)

            if date_str:
                date_counts[date_str] += 1

            if amt_info["abs_amount"] is not None:
                all_abs_amounts.append(amt_info["abs_amount"])

            if amt_info["debit"] is not None and amt_info["debit"] > 0:
                all_debits.append(amt_info["debit"])

            if amt_info["credit"] is not None and amt_info["credit"] > 0:
                all_credits.append(amt_info["credit"])

            enriched_items.append({
                "raw": tx,
                "amt_info": amt_info,
                "date_str": date_str,
                "source_row": source_row,
                "flags": [],
                "reasons": [],
            })

        # Step 2: Statistical IQR Boundaries
        amount_stats = compute_iqr_bounds(
            all_abs_amounts,
            multiplier=self.iqr_multiplier,
            min_samples=self.min_samples_for_iqr,
        )
        if amount_stats["status"] == "INSUFFICIENT_DATA":
            notes.append(
                f"Dataset contains {amount_stats['count']} amount sample(s); "
                f"at least {self.min_samples_for_iqr} are required for reliable statistical IQR bounds."
            )

        debit_stats = compute_iqr_bounds(
            all_debits,
            multiplier=self.iqr_multiplier,
            min_samples=self.min_samples_for_iqr,
        )
        credit_stats = compute_iqr_bounds(
            all_credits,
            multiplier=self.iqr_multiplier,
            min_samples=self.min_samples_for_iqr,
        )

        # Step 3: Round Amount Clustering
        round_amount_counts: Counter = Counter()
        for item in enriched_items:
            abs_amt = item["amt_info"]["abs_amount"]
            if abs_amt is not None and is_round_number(abs_amt, min_value=self.round_amount_min):
                round_amount_counts[abs_amt] += 1

        repeated_round_amounts = {
            amt: count
            for amt, count in round_amount_counts.items()
            if count >= self.round_amount_min_occurrences
        }

        # Step 4: High Daily Frequency Detection
        high_freq_dates = {
            dt: count
            for dt, count in date_counts.items()
            if count >= self.frequency_threshold
        }

        # Step 5: Evaluate Each Transaction Against Rules
        flag_counts: Counter = Counter()
        flagged_transactions = []
        anomalies_only = []

        for item in enriched_items:
            tx = item["raw"]
            amt_info = item["amt_info"]
            abs_amt = amt_info["abs_amount"]
            deb = amt_info["debit"]
            crd = amt_info["credit"]
            date_str = item["date_str"]

            flags = []
            reasons = []

            # Rule 1: Statistical Outlier (Overall Amount)
            if amount_stats["status"] == "VALID" and abs_amt is not None:
                upper = amount_stats["upper_bound"]
                if abs_amt > upper:
                    flags.append("UNUSUALLY_LARGE_AMOUNT")
                    reasons.append(
                        f"Amount ₹{abs_amt:,.2f} is an extreme statistical outlier exceeding "
                        f"upper bound of ₹{upper:,.2f} (Q3: ₹{amount_stats['q3']:,.2f}, IQR: ₹{amount_stats['iqr']:,.2f})."
                    )

            # Rule 2: Unusual Debit
            if self.separate_debit_credit and debit_stats["status"] == "VALID" and deb is not None:
                if deb > debit_stats["upper_bound"]:
                    flags.append("UNUSUAL_DEBIT")
                    reasons.append(
                        f"Debit of ₹{deb:,.2f} is significantly larger than normal debits "
                        f"(upper bound: ₹{debit_stats['upper_bound']:,.2f}, median: ₹{debit_stats['median']:,.2f})."
                    )

            # Rule 3: Unusual Credit
            if self.separate_debit_credit and credit_stats["status"] == "VALID" and crd is not None:
                if crd > credit_stats["upper_bound"]:
                    flags.append("UNUSUAL_CREDIT")
                    reasons.append(
                        f"Credit of ₹{crd:,.2f} is significantly larger than normal credits "
                        f"(upper bound: ₹{credit_stats['upper_bound']:,.2f}, median: ₹{credit_stats['median']:,.2f})."
                    )

            # Rule 4: Repeated Round Amounts
            if abs_amt is not None and abs_amt in repeated_round_amounts:
                count = repeated_round_amounts[abs_amt]
                flags.append("REPEATED_ROUND_AMOUNT")
                reasons.append(
                    f"Round amount of ₹{abs_amt:,.2f} observed {count} times across the period. "
                    "Repeated round sums may indicate non-invoiced transfers, loans, or structuring."
                )

            # Rule 5: Unusual Transaction Frequency
            if date_str and date_str in high_freq_dates:
                daily_total = high_freq_dates[date_str]
                flags.append("HIGH_TRANSACTION_FREQUENCY")
                reasons.append(
                    f"Transaction occurred on {date_str} during a burst of {daily_total} transactions "
                    f"(frequency threshold: {self.frequency_threshold} txs/day)."
                )

            # Assign flags and severity
            is_anomaly = len(flags) > 0
            if is_anomaly:
                for f in flags:
                    flag_counts[f] += 1

                # Severity classification
                if len(flags) >= 2 or (
                    "UNUSUALLY_LARGE_AMOUNT" in flags
                    and amount_stats.get("q3")
                    and abs_amt > (amount_stats["q3"] * 5)
                ):
                    severity = "HIGH"
                else:
                    severity = "MEDIUM"
            else:
                severity = "NORMAL"

            # Enrich transaction record
            tx["is_anomaly"] = is_anomaly
            tx["anomaly_flags"] = flags
            tx["anomaly_reasons"] = reasons
            tx["severity"] = severity
            tx["requires_review"] = is_anomaly

            flagged_transactions.append(tx)
            if is_anomaly:
                anomalies_only.append(tx)

        # Step 6: Summary Statistics
        total_tx = len(tx_list)
        anomalous_count = len(anomalies_only)
        normal_count = total_tx - anomalous_count
        anomaly_rate = round((anomalous_count / total_tx * 100), 2) if total_tx > 0 else 0.0

        daily_counts_list = list(date_counts.values()) if date_counts else [0]
        frequency_stats = {
            "unique_dates": len(date_counts),
            "max_daily_transactions": max(daily_counts_list),
            "avg_daily_transactions": round(sum(daily_counts_list) / max(len(daily_counts_list), 1), 2),
            "busiest_dates": [
                {"date": d, "count": c}
                for d, c in date_counts.most_common(5)
            ] if date_counts else [],
            "burst_dates_flagged": list(high_freq_dates.keys()),
        }

        return {
            "total_transactions": total_tx,
            "anomalous_transactions_count": anomalous_count,
            "normal_transactions_count": normal_count,
            "anomaly_rate": anomaly_rate,
            "flag_counts": dict(flag_counts),
            "statistics": {
                "amount": amount_stats,
                "debit": debit_stats,
                "credit": credit_stats,
                "frequency": frequency_stats,
            },
            "anomalies": anomalies_only,
            "flagged_transactions": flagged_transactions,
            "notes": notes,
            "disclaimer": (
                "Anomalies indicate unusual statistical or behavioral patterns flagged for human review. "
                "They do not constitute confirmed fraud, errors, or tax violations."
            ),
        }

    def _empty_result(self) -> dict:
        return {
            "total_transactions": 0,
            "anomalous_transactions_count": 0,
            "normal_transactions_count": 0,
            "anomaly_rate": 0.0,
            "flag_counts": {},
            "statistics": {
                "amount": compute_iqr_bounds([]),
                "debit": compute_iqr_bounds([]),
                "credit": compute_iqr_bounds([]),
                "frequency": {
                    "unique_dates": 0,
                    "max_daily_transactions": 0,
                    "avg_daily_transactions": 0.0,
                    "busiest_dates": [],
                    "burst_dates_flagged": [],
                },
            },
            "anomalies": [],
            "flagged_transactions": [],
            "notes": ["Empty transaction list provided."],
            "disclaimer": (
                "Anomalies indicate unusual statistical or behavioral patterns flagged for human review."
            ),
        }


def detect_anomalies(
    transactions: list[dict] | pd.DataFrame,
    iqr_multiplier: float = 1.5,
    min_samples_for_iqr: int = 4,
    frequency_threshold: int = 10,
    round_amount_min: float = 5000.0,
    round_amount_min_occurrences: int = 2,
    separate_debit_credit: bool = True,
) -> dict:
    """
    Convenience functional interface for transaction anomaly detection.
    """
    detector = AnomalyDetector(
        iqr_multiplier=iqr_multiplier,
        min_samples_for_iqr=min_samples_for_iqr,
        frequency_threshold=frequency_threshold,
        round_amount_min=round_amount_min,
        round_amount_min_occurrences=round_amount_min_occurrences,
        separate_debit_credit=separate_debit_credit,
    )
    return detector.detect(transactions)

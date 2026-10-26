from datetime import date, datetime
import re
from typing import Any
import pandas as pd


def normalize_description(description: Any) -> str:
    """
    Normalize transaction description:
    - Handle null/None/empty values
    - Convert to lowercase
    - Trim leading and trailing whitespace
    - Collapse internal consecutive whitespace characters
    """
    if description is None or pd.isna(description):
        return ""
    text = str(description).strip().lower()
    return re.sub(r"\s+", " ", text)


def normalize_date(value: Any) -> str | None:
    """
    Normalize transaction date to 'YYYY-MM-DD' format.
    Accepts datetime, date, string, or pandas Timestamp objects.
    """
    if value is None or pd.isna(value):
        return None

    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")

    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.notna(parsed):
            return parsed.strftime("%Y-%m-%d")
    except Exception:
        pass

    text = str(value).strip()
    return text if text else None


def get_monetary_signature(transaction: dict) -> tuple:
    """
    Generate a normalized representation for monetary values.
    Handles explicit amount or debit/credit column pairs.
    Amounts are rounded to 2 decimal places to prevent float precision issues.
    """
    amount = transaction.get("amount")
    debit = transaction.get("debit")
    credit = transaction.get("credit")

    def _parse_float(val: Any) -> float | None:
        if val is None or pd.isna(val) or val == "":
            return None
        try:
            return round(float(val), 2)
        except (ValueError, TypeError):
            return None

    amt_val = _parse_float(amount)
    deb_val = _parse_float(debit)
    crd_val = _parse_float(credit)

    if amt_val is not None:
        return ("amount", amt_val)

    if deb_val is not None or crd_val is not None:
        # Canonical debit/credit representation
        return ("debit_credit", deb_val or 0.0, crd_val or 0.0)

    return ("none", None)


def build_duplicate_signature(transaction: dict) -> tuple:
    """
    Build a deterministic hashable signature tuple for duplicate detection:
    (normalized_date, normalized_description, monetary_signature)
    """
    date_sig = normalize_date(transaction.get("transaction_date"))
    desc_sig = normalize_description(transaction.get("description"))
    money_sig = get_monetary_signature(transaction)
    return (date_sig, desc_sig, money_sig)


def detect_duplicates(transactions: list[dict] | pd.DataFrame) -> dict:
    """
    Deterministic duplicate transaction detection.

    Identifies transactions with identical:
    - Transaction date
    - Normalized description
    - Amount or debit/credit values

    Classification:
    - "UNIQUE": No other transactions match this signature.
    - "ORIGINAL": The first occurrence in a group of duplicates.
    - "POTENTIAL_DUPLICATE": Subsequent occurrences flagged for user review.

    Returns:
    {
        "total_transactions": int,
        "unique_count": int,
        "original_count": int,
        "duplicate_count": int,
        "duplicate_groups_count": int,
        "flagged_transactions": list[dict],
        "duplicates": list[dict],
        "duplicate_groups": dict[str, list[dict]]
    }
    """
    if isinstance(transactions, pd.DataFrame):
        tx_list = transactions.to_dict(orient="records")
    else:
        # Create shallow copies of dicts so we don't mutate input dictionaries unexpectedly
        tx_list = [dict(t) for t in transactions]

    if not tx_list:
        return {
            "total_transactions": 0,
            "unique_count": 0,
            "original_count": 0,
            "duplicate_count": 0,
            "duplicate_groups_count": 0,
            "flagged_transactions": [],
            "duplicates": [],
            "duplicate_groups": {},
        }

    # Step 1: Group transaction indices by deterministic signature
    signature_indices: dict[tuple, list[int]] = {}
    for idx, tx in enumerate(tx_list):
        sig = build_duplicate_signature(tx)
        signature_indices.setdefault(sig, []).append(idx)

    # Step 2: Assign duplicate status and metadata
    duplicate_groups: dict[str, list[dict]] = {}
    duplicates: list[dict] = []
    group_counter = 0

    unique_count = 0
    original_count = 0
    duplicate_count = 0

    for sig, indices in signature_indices.items():
        if len(indices) == 1:
            # Single transaction matching this signature -> UNIQUE
            idx = indices[0]
            tx = tx_list[idx]
            tx["is_duplicate"] = False
            tx["duplicate_status"] = "UNIQUE"
            tx["duplicate_group_id"] = None
            tx["duplicate_of_row"] = None
            tx["duplicate_reason"] = None
            unique_count += 1
        else:
            # Group has multiple matching transactions
            group_counter += 1
            group_id = f"dup_group_{group_counter}"
            group_txs = []

            # First occurrence is ORIGINAL
            first_idx = indices[0]
            first_tx = tx_list[first_idx]
            first_row = first_tx.get("source_row", first_idx + 1)

            first_tx["is_duplicate"] = False
            first_tx["duplicate_status"] = "ORIGINAL"
            first_tx["duplicate_group_id"] = group_id
            first_tx["duplicate_of_row"] = None
            first_tx["duplicate_reason"] = (
                f"Original transaction for {len(indices) - 1} potential duplicate(s)."
            )
            original_count += 1
            group_txs.append(first_tx)

            # Subsequent occurrences are POTENTIAL_DUPLICATE
            for idx in indices[1:]:
                tx = tx_list[idx]
                tx["is_duplicate"] = True
                tx["duplicate_status"] = "POTENTIAL_DUPLICATE"
                tx["duplicate_group_id"] = group_id
                tx["duplicate_of_row"] = first_row
                tx["duplicate_reason"] = (
                    f"Matches transaction on {sig[0]} with description '{sig[1]}' "
                    f"(row {first_row}). Flagged for review."
                )
                duplicate_count += 1
                duplicates.append(tx)
                group_txs.append(tx)

            duplicate_groups[group_id] = group_txs

    return {
        "total_transactions": len(tx_list),
        "unique_count": unique_count,
        "original_count": original_count,
        "duplicate_count": duplicate_count,
        "duplicate_groups_count": len(duplicate_groups),
        "flagged_transactions": tx_list,
        "duplicates": duplicates,
        "duplicate_groups": duplicate_groups,
    }

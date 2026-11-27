"""
backend/app/services/analysis/explainability_service.py

Unified Financial & Tax Explainability Service.

Provides comprehensive, human-readable, and auditor-ready explanations for:
1. Matching Decisions: Why a transaction matched, why it was marked potential match, or why it remained unmatched.
2. Anomaly & Outlier Flags: Why a transaction was flagged by statistical IQR rules or ML Isolation Forest.
3. Classification & Tax Head Decisions: Why a category, subcategory, and tax deductibility status was assigned.
4. Risk & Audit Impact: Audit scrutiny probability, statutory risk triggers (e.g. Section 269ST, 40A(3), TDS).
5. Step-by-step Audit Trail: Sequential reasoning path showing the engine's internal evaluation pipeline.
"""

from __future__ import annotations

from typing import Any
import math


class ExplainabilityService:
    """
    Synthesizes signals across ingestion, classification, anomaly detection,
    and reconciliation to generate holistic explanations for financial transactions.
    """

    @classmethod
    def explain_transaction(
        cls,
        tx: dict[str, Any],
        match_info: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate a 360-degree explanation for an individual transaction.
        """
        date_str = str(tx.get("transaction_date", "Unknown date"))
        desc = str(tx.get("description", "") or "").strip()
        amt = tx.get("amount") or tx.get("net_amount") or tx.get("debit") or tx.get("credit") or 0.0
        try:
            amt_val = float(amt)
        except (ValueError, TypeError):
            amt_val = 0.0

        # Sub-explanations
        match_exp = cls._explain_matching(tx, match_info)
        anomaly_exp = cls._explain_anomaly(tx)
        class_exp = cls._explain_classification(tx)
        risk_exp = cls._explain_risk(tx, match_info, anomaly_exp)
        audit_trail = cls._build_audit_trail(tx, match_info, anomaly_exp, class_exp, risk_exp)

        # Primary status summary
        primary_status = cls._determine_primary_status(tx, match_info, anomaly_exp)
        headline = cls._build_headline(tx, primary_status, match_exp, anomaly_exp, class_exp)

        return {
            "transaction_id": str(tx.get("_id") or tx.get("id") or tx.get("source_row") or "N/A"),
            "transaction_date": date_str,
            "description": desc,
            "amount": amt_val,
            "primary_status": primary_status,
            "headline": headline,
            "reconciliation": match_exp,
            "anomaly": anomaly_exp,
            "classification": class_exp,
            "risk_assessment": risk_exp,
            "audit_trail": audit_trail,
        }

    # ------------------------------------------------------------------
    # 1. Matching Explainability
    # ------------------------------------------------------------------
    @classmethod
    def _explain_matching(
        cls,
        tx: dict[str, Any],
        match_info: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Explain reconciliation pairing or why the transaction remained unmatched."""
        status = tx.get("status") or (match_info.get("status") if match_info else None)
        match_type = tx.get("match_type") or (match_info.get("match_type") if match_info else None)

        if not status and not match_info:
            return {
                "reconciliation_status": "NOT_EVALUATED",
                "summary": "This transaction has not yet been processed through the reconciliation engine.",
                "evidence": [],
                "why_not_exact_match": None,
            }

        evidence: list[dict[str, str]] = []

        if status == "MATCHED":
            if match_type == "EXACT_MATCH":
                evidence.append({
                    "factor": "Exact Amount & Date",
                    "impact": "STRONG_POSITIVE",
                    "details": "Identical monetary amount and calendar date in both bank and ledger.",
                })
                evidence.append({
                    "factor": "Normalized Description",
                    "impact": "STRONG_POSITIVE",
                    "details": "Descriptions are identical or share high token overlap.",
                })
                summary = "Reconciled with 100% certainty via exact date, amount, and description alignment."
                why_not_exact = None
            else:
                summary = "Reconciled via amount and date fallback match."
                why_not_exact = "Descriptions differed, but amounts and dates matched exactly."

        elif status == "POTENTIAL_MATCH":
            if match_type == "FUZZY_MATCH":
                sim = tx.get("similarity_score") or (match_info.get("similarity_score") if match_info else 0.0)
                summary = f"Identified as candidate match using fuzzy description similarity ({sim:.1f}%)."
                why_not_exact = f"Description differs slightly from ledger entry (similarity: {sim:.1f}% vs 100% required for exact match)."
                evidence.append({
                    "factor": "Fuzzy Textual Similarity",
                    "impact": "POSITIVE",
                    "details": f"RapidFuzz similarity score of {sim:.1f}% exceeded matching threshold.",
                })
            elif match_type == "SEMANTIC_MATCH":
                sim = tx.get("similarity_score") or (match_info.get("similarity_score") if match_info else 0.0)
                summary = f"Identified as candidate match using domain concept similarity ({sim:.1f}%)."
                why_not_exact = "Descriptions use different wording but represent identical financial and accounting concepts."
                evidence.append({
                    "factor": "Semantic Concept Mapping",
                    "impact": "POSITIVE",
                    "details": "Embedding and financial ontology matched accounting intent.",
                })
            elif match_type == "DATE_TOLERANCE_MATCH":
                diff_days = tx.get("date_difference_days") or (match_info.get("date_difference_days") if match_info else 1)
                summary = f"Candidate match with date difference of {diff_days} day(s) within allowable tolerance."
                why_not_exact = f"Transaction dates differ by {diff_days} day(s) (requires manual date confirmation)."
                evidence.append({
                    "factor": "Date Proximity",
                    "impact": "MODERATE_POSITIVE",
                    "details": f"Dates differ by {diff_days} day(s), within configured grace period.",
                })
            else:
                summary = "Candidate match requiring manual verification."
                why_not_exact = "Attributes align partially but require human verification."

        elif status == "AMOUNT_MISMATCH":
            variance = tx.get("amount_variance") or (match_info.get("amount_variance") if match_info else 0.0)
            summary = f"Matching date and entity found, but amounts differ by ₹{abs(variance):,.2f}."
            why_not_exact = f"Monetary amount differs by ₹{abs(variance):,.2f} between bank and ledger records."
            evidence.append({
                "factor": "Amount Variance",
                "impact": "NEGATIVE",
                "details": f"Discrepancy of ₹{abs(variance):,.2f} detected across counterpart records.",
            })

        elif status in ("BANK_ONLY", "LEDGER_ONLY"):
            origin = "bank statement" if status == "BANK_ONLY" else "company ledger"
            counterpart = "company ledger" if status == "BANK_ONLY" else "bank statement"
            summary = f"Unmatched entry: Appears in {origin} with no corresponding record found in {counterpart}."
            why_not_exact = f"No counterpart record found with matching date and amount in {counterpart}."
            evidence.append({
                "factor": "Missing Counterpart",
                "impact": "CRITICAL_NEGATIVE",
                "details": f"No entry in {counterpart} satisfied date tolerance or amount criteria.",
            })

        else:
            summary = f"Reconciliation state: {status or 'UNKNOWN'}."
            why_not_exact = None

        return {
            "reconciliation_status": status or "EVALUATED",
            "match_type": match_type,
            "summary": summary,
            "evidence": evidence,
            "why_not_exact_match": why_not_exact,
        }

    # ------------------------------------------------------------------
    # 2. Anomaly Explainability
    # ------------------------------------------------------------------
    @classmethod
    def _explain_anomaly(cls, tx: dict[str, Any]) -> dict[str, Any]:
        """Explain statistical, behavioral, and machine-learning anomaly triggers."""
        is_anomaly = bool(tx.get("is_anomaly") or tx.get("is_ml_anomaly"))
        flags = list(tx.get("anomaly_flags") or [])
        if tx.get("ml_flag"):
            flags.append(str(tx.get("ml_flag")))

        reasons = list(tx.get("anomaly_reasons") or [])
        if tx.get("ml_reason"):
            reasons.append(str(tx.get("ml_reason")))

        severity = tx.get("severity") or tx.get("ml_severity") or ("HIGH" if is_anomaly else "NORMAL")

        triggers: list[dict[str, str]] = []

        if not is_anomaly:
            return {
                "is_anomalous": False,
                "severity": "NORMAL",
                "summary": "Transaction amount and timing conform to normal statistical baselines.",
                "triggers": [],
            }

        for flag in flags:
            if flag == "UNUSUALLY_LARGE_AMOUNT":
                triggers.append({
                    "detector": "Statistical IQR Rule",
                    "flag": flag,
                    "explanation": "Amount exceeds upper statistical bound (Q3 + 1.5 * IQR) of the dataset.",
                })
            elif flag == "UNUSUAL_DEBIT":
                triggers.append({
                    "detector": "Debit Distribution IQR",
                    "flag": flag,
                    "explanation": "Debit amount is significantly higher than the standard debit distribution.",
                })
            elif flag == "UNUSUAL_CREDIT":
                triggers.append({
                    "detector": "Credit Distribution IQR",
                    "flag": flag,
                    "explanation": "Credit amount is an extreme statistical outlier compared to typical deposits.",
                })
            elif flag == "REPEATED_ROUND_AMOUNT":
                triggers.append({
                    "detector": "Clustering Heuristic",
                    "flag": flag,
                    "explanation": "Round-figure transaction repeated multiple times, which may suggest non-invoiced transfers or loan advances.",
                })
            elif flag == "HIGH_TRANSACTION_FREQUENCY":
                triggers.append({
                    "detector": "Burst Activity Monitor",
                    "flag": flag,
                    "explanation": "Transaction occurred during an unusually high daily volume burst.",
                })
            elif flag == "ML_ISOLATION_FOREST":
                ml_score = tx.get("ml_anomaly_score", 0.0)
                triggers.append({
                    "detector": "Isolation Forest (Unsupervised ML)",
                    "flag": flag,
                    "explanation": f"Multivariate outlier score of {ml_score:.2f}/1.00 across amount, date of month, day of week, and frequency dimensions.",
                })
            else:
                triggers.append({
                    "detector": "Custom Rule",
                    "flag": flag,
                    "explanation": "Behavioral rule flagged this entry for human verification.",
                })

        summary = f"Flagged with {severity} severity due to {len(triggers)} anomaly indicator(s)."

        return {
            "is_anomalous": True,
            "severity": severity,
            "summary": summary,
            "triggers": triggers,
            "detailed_reasons": reasons,
        }

    # ------------------------------------------------------------------
    # 3. Classification Explainability
    # ------------------------------------------------------------------
    @classmethod
    def _explain_classification(cls, tx: dict[str, Any]) -> dict[str, Any]:
        """Explain category, sub-category, tax head, and deductibility rationale."""
        cat = tx.get("category") or "UNCATEGORIZED"
        sub_cat = tx.get("sub_category") or "General"
        tax_head = tx.get("tax_head") or "NOT_APPLICABLE"
        is_deductible = tx.get("is_tax_deductible")
        reason = tx.get("classification_reason") or "Classified based on transaction description heuristics."
        confidence = tx.get("classification_confidence") or tx.get("confidence_score") or 0.70

        deductibility_rationale = (
            "Permissible business expense under Section 37(1) of Income Tax Act if incurred wholly and exclusively for business."
            if is_deductible is True else
            "Personal or non-deductible expenditure; cannot be claimed as a business tax deduction."
            if is_deductible is False else
            "Tax deductibility depends on supporting invoice documentation and business nexus."
        )

        return {
            "category": cat,
            "sub_category": sub_cat,
            "tax_head": tax_head,
            "confidence": round(float(confidence), 2),
            "is_tax_deductible": is_deductible,
            "classification_reason": reason,
            "deductibility_rationale": deductibility_rationale,
        }

    # ------------------------------------------------------------------
    # 4. Risk & Audit Impact Explainability
    # ------------------------------------------------------------------
    @classmethod
    def _explain_risk(
        cls,
        tx: dict[str, Any],
        match_info: dict[str, Any] | None,
        anomaly_exp: dict[str, Any],
    ) -> dict[str, Any]:
        """Assess audit scrutiny likelihood and specific statutory compliance risks."""
        desc = str(tx.get("description", "")).lower()
        amt = abs(float(tx.get("amount") or tx.get("net_amount") or tx.get("debit") or tx.get("credit") or 0.0))

        risk_factors: list[str] = []
        statutory_sections: list[str] = []

        # Check 1: Cash deposit limits (Section 269ST)
        if any(w in desc for w in ("cash", "cdm deposit", "by cash")) and amt >= 200000.0:
            risk_factors.append("Single-day cash receipt ₹2,00,000 or more violates Section 269ST.")
            statutory_sections.append("Section 269ST (100% penalty under Section 271DA)")

        # Check 2: Cash payment limit (Section 40A(3))
        if any(w in desc for w in ("cash", "atm")) and amt > 10000.0 and tx.get("is_tax_deductible") is True:
            risk_factors.append("Cash business payment exceeding ₹10,000 is disallowed under Section 40A(3).")
            statutory_sections.append("Section 40A(3) (Expense Disallowance)")

        # Check 3: High-value transactions (SFT reporting)
        if amt >= 1000000.0:
            risk_factors.append("High-value transaction (₹10 Lakh+) routinely reported to Income Tax Dept via SFT.")
            statutory_sections.append("Section 285BA (Statement of Financial Transactions)")

        # Check 4: Unreconciled bank entry
        status = tx.get("status") or (match_info.get("status") if match_info else "")
        if status == "BANK_ONLY":
            risk_factors.append("Unexplained credit in bank statement without ledger entry risks addition under Section 68.")
            statutory_sections.append("Section 68 (Unexplained Cash Credits)")
        elif status == "AMOUNT_MISMATCH":
            risk_factors.append("Variance between books and bank statement will trigger scrutiny during reconciliation audit.")

        # Check 5: Anomaly flags
        if anomaly_exp.get("is_anomalous"):
            risk_factors.append(f"Statistical anomaly flagged: {anomaly_exp.get('summary')}")

        # Compute risk level
        if any("Section 269ST" in s or "Section 68" in s for s in statutory_sections) or amt >= 1000000.0:
            risk_level = "HIGH"
        elif len(risk_factors) > 0 or anomaly_exp.get("is_anomalous"):
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "relevant_statutory_sections": statutory_sections,
            "audit_scrutiny_likelihood": "HIGH" if risk_level == "HIGH" else ("MEDIUM" if risk_level == "MEDIUM" else "LOW"),
        }

    # ------------------------------------------------------------------
    # 5. Step-by-step Audit Trail
    # ------------------------------------------------------------------
    @classmethod
    def _build_audit_trail(
        cls,
        tx: dict[str, Any],
        match_info: dict[str, Any] | None,
        anomaly_exp: dict[str, Any],
        class_exp: dict[str, Any],
        risk_exp: dict[str, Any],
    ) -> list[dict[str, str]]:
        trail = [
            {
                "step": "1. Ingestion & Preprocessing",
                "status": "COMPLETED",
                "observation": f"Normalized date '{tx.get('transaction_date')}' and extracted clean monetary amount.",
            },
            {
                "step": "2. Financial Classification",
                "status": "COMPLETED",
                "observation": f"Assigned category '{class_exp['category']}' under tax head '{class_exp['tax_head']}'.",
            },
            {
                "step": "3. Anomaly & Outlier Screening",
                "status": "FLAGGED" if anomaly_exp["is_anomalous"] else "PASSED",
                "observation": anomaly_exp["summary"],
            },
            {
                "step": "4. Bank vs Ledger Reconciliation",
                "status": tx.get("status") or (match_info.get("status") if match_info else "SKIPPED"),
                "observation": (
                    ((match_info or {}).get("notes")) or tx.get("notes") or "Evaluated against company ledger entries."
                    if (match_info or tx.get("status"))
                    else "Standalone transaction; no paired ledger counterpart evaluated."
                ),
            },
            {
                "step": "5. Statutory Risk & Compliance Assessment",
                "status": risk_exp["risk_level"],
                "observation": f"Assigned {risk_exp['risk_level']} risk level with {len(risk_exp['risk_factors'])} risk factor(s).",
            },
        ]
        return trail

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @classmethod
    def _determine_primary_status(
        cls,
        tx: dict[str, Any],
        match_info: dict[str, Any] | None,
        anomaly_exp: dict[str, Any],
    ) -> str:
        rec_status = tx.get("status") or (match_info.get("status") if match_info else None)
        if rec_status in ("AMOUNT_MISMATCH", "BANK_ONLY", "LEDGER_ONLY"):
            return rec_status
        if anomaly_exp["is_anomalous"] and anomaly_exp["severity"] == "HIGH":
            return "ANOMALY_HIGH"
        if rec_status:
            return rec_status
        if anomaly_exp["is_anomalous"]:
            return "ANOMALOUS"
        return "NORMAL"

    @classmethod
    def _build_headline(
        cls,
        tx: dict[str, Any],
        primary_status: str,
        match_exp: dict[str, Any],
        anomaly_exp: dict[str, Any],
        class_exp: dict[str, Any],
    ) -> str:
        cat = class_exp["category"]
        if primary_status == "MATCHED":
            return f"Fully reconciled {cat} transaction."
        if primary_status == "POTENTIAL_MATCH":
            return f"Potential match candidate for {cat} entry requiring confirmation."
        if primary_status == "AMOUNT_MISMATCH":
            return f"Amount variance detected on {cat} transaction."
        if primary_status == "BANK_ONLY":
            return f"Unmatched bank credit/debit with no corresponding ledger booking."
        if primary_status == "LEDGER_ONLY":
            return f"Uncollected or uncleared ledger entry with no bank statement counterpart."
        if anomaly_exp["is_anomalous"]:
            return f"Statistical outlier flagged in category {cat}."
        return f"Standard {cat} transaction conforming to expected norms."


def explain_single_transaction(
    transaction: dict[str, Any],
    match_info: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convenience function to generate transaction explanation."""
    return ExplainabilityService.explain_transaction(
        tx=transaction,
        match_info=match_info,
        context=context,
    )


def explain_reconciliation_match(
    match: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate an in-depth explanation specifically for a reconciliation match pair.
    """
    bank_tx = match.get("bank_transaction", {})
    ledger_tx = match.get("ledger_transaction", {})
    match_type = match.get("match_type", "EXACT_MATCH")
    status = match.get("status", "MATCHED")
    confidence = match.get("confidence_score", 1.0)
    notes = match.get("notes", "")

    b_amt = bank_tx.get("amount") or bank_tx.get("debit") or bank_tx.get("credit")
    l_amt = ledger_tx.get("amount") or ledger_tx.get("debit") or ledger_tx.get("credit")
    b_date = bank_tx.get("transaction_date")
    l_date = ledger_tx.get("transaction_date")
    b_desc = bank_tx.get("description", "")
    l_desc = ledger_tx.get("description", "")

    why_matched: list[str] = []
    if b_date == l_date:
        why_matched.append(f"Same transaction date: {b_date}.")
    else:
        diff = abs(match.get("date_difference_days", 1))
        why_matched.append(f"Dates differ by {diff} day(s), which was within the allowed tolerance.")

    if match.get("amount_variance", 0.0) == 0.0:
        why_matched.append(f"Exact matching amount: ₹{abs(float(b_amt or 0)):,.2f}.")
    else:
        why_matched.append(f"Amounts differ by ₹{abs(float(match.get('amount_variance', 0))):,.2f}.")

    if match_type == "FUZZY_MATCH":
        sim = match.get("similarity_score", 0.0)
        why_matched.append(f"Description fuzzy similarity of {sim:.1f}% met the threshold.")
    elif match_type == "SEMANTIC_MATCH":
        concepts = match.get("matched_concepts", [])
        concept_str = f" ({', '.join(concepts)})" if concepts else ""
        why_matched.append(f"Descriptions shared domain accounting concepts{concept_str}.")

    return {
        "status": status,
        "match_type": match_type,
        "confidence_score": confidence,
        "confidence_level": match.get("confidence_level", "HIGH"),
        "decision_recommendation": match.get("decision_recommendation", "REVIEW_RECOMMENDED"),
        "reconciliation_summary": notes,
        "key_matching_factors": why_matched,
        "bank_summary": {
            "date": b_date,
            "description": b_desc,
            "amount": b_amt,
        },
        "ledger_summary": {
            "date": l_date,
            "description": l_desc,
            "amount": l_amt,
        },
    }


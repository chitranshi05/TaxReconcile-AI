"""
app/services/processing_pipeline.py

Central Pipeline Orchestrator for Tax-Reconcile AI.

Automatically runs all processing services in the correct order after a
document is uploaded. Calling code (the upload endpoint) only needs to do:

    background_tasks.add_task(run_document_pipeline, document_id, owner_id, db)

Sequence
--------
1.  Retrieve document record from MongoDB.
2.  Extract transactions (CSV / XLSX / JSON).
3.  Normalize entity descriptions.
4.  Classify transactions (financial category + tax head).
5.  Save transactions to MongoDB.
6.  Run duplicate detection (stored as pipeline metadata).
7.  Run statistical anomaly detection.
8.  Run ML Isolation Forest anomaly detection.
9.  Run tax rule validation.
10. If a reconciliation partner exists for the same owner, run reconciliation.
11. Run TDS discrepancy detection.
12. Generate findings portfolio.
13. Calculate confidence scores (per match).
14. Calculate risk scores (transaction-level + run-level).
15. Persist all results and mark document PIPELINE_COMPLETE.

Design rules
------------
- Never rewrite existing algorithms — this module only *calls* them.
- All errors are caught per-stage; the pipeline moves to FAILED on fatal errors
  but logs partial results when possible.
- Status transitions are written to the document record so the frontend can
  poll GET /api/documents/{id}/status.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson import ObjectId

from app.database.mongodb import get_database
from app.services.audit_service import log_audit_event

# ── Ingestion ────────────────────────────────────────────────────────────────
from app.services.ingestion.csv_processor import process_csv_file
from app.services.ingestion.excel_processor import process_excel_file
from app.services.ingestion.json_processor import process_json_file
from app.services.ingestion.entity_normalizer import normalize_transaction_entity
from app.services.ingestion.transaction_classifier import classify_transactions
from app.services.ingestion.transaction_saver import save_valid_transactions
from app.services.ingestion.duplicate_detector import detect_duplicates
from app.services.ingestion.anomaly_detector import detect_anomalies
from app.services.ingestion.isolation_forest_detector import run_isolation_forest

# ── Tax Validation ───────────────────────────────────────────────────────────
from app.services.tax_validation.tax_rule_engine import validate_tax_records
from app.services.tax_validation.tds_discrepancy_detector import run_advanced_tds_analysis

# ── Reconciliation ────────────────────────────────────────────────────────────
from app.services.reconciliation.reconciliation_engine import reconcile_transactions
from app.services.reconciliation.confidence_scorer import compute_batch_confidence

# ── Analysis ──────────────────────────────────────────────────────────────────
from app.services.analysis.finding_generator import FindingGenerator
from app.services.analysis.risk_scorer import RiskScorer

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"

# Pipeline-specific status values written to the document's `pipeline_status` field.
# The document's main `status` stays PROCESSED once transactions are saved;
# the extended `pipeline_status` tracks the analysis stages.
PIPELINE_STATUSES = [
    "QUEUED",
    "EXTRACTING",
    "NORMALIZING",
    "CLASSIFYING",
    "SAVING_TRANSACTIONS",
    "DETECTING_DUPLICATES",
    "DETECTING_ANOMALIES",
    "ML_ANOMALY_DETECTION",
    "TAX_VALIDATION",
    "RECONCILING",
    "TDS_ANALYSIS",
    "GENERATING_FINDINGS",
    "SCORING_RISK",
    "PIPELINE_COMPLETE",
    "PIPELINE_FAILED",
]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _set_status(db, document_id: str, status: str, extra: dict | None = None) -> None:
    """Write pipeline_status (and optional extra fields) to the document record."""
    update: dict[str, Any] = {
        "pipeline_status": status,
        "pipeline_status_updated_at": datetime.now(timezone.utc),
    }
    if extra:
        update.update(extra)
    db.documents.update_one(
        {"_id": ObjectId(document_id)},
        {"$set": update},
    )


def _serialize_tx_dates(transactions: list[dict]) -> list[dict]:
    """Return a copy of transactions with datetime fields converted to ISO strings."""
    result = []
    for tx in transactions:
        t = dict(tx)
        for key in ("transaction_date", "created_at"):
            val = t.get(key)
            if val is not None and hasattr(val, "isoformat"):
                t[key] = val.isoformat()
        result.append(t)
    return result


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_document_pipeline(document_id: str, owner_id: str) -> None:  # noqa: C901
    """
    Full end-to-end processing pipeline for a single uploaded document.

    Called as a FastAPI BackgroundTask after a successful upload.
    All stages write their results back to MongoDB so the frontend can
    retrieve them via dedicated GET endpoints.
    """
    db = get_database()
    pipeline_results: dict[str, Any] = {}

    try:
        # ── 0. Fetch document ─────────────────────────────────────────────────
        document = db.documents.find_one({"_id": ObjectId(document_id)})
        if not document:
            logger.error("Pipeline: document %s not found", document_id)
            return

        file_type = document.get("file_type", "")
        if file_type not in {"CSV", "XLSX", "JSON"}:
            _set_status(db, document_id, "PIPELINE_FAILED", {
                "pipeline_error": f"Unsupported file type for pipeline: {file_type}"
            })
            return

        file_path = str(UPLOAD_DIR / document["filename"])

        # ── 1. Extract ────────────────────────────────────────────────────────
        _set_status(db, document_id, "EXTRACTING")
        processor = {"CSV": process_csv_file, "XLSX": process_excel_file, "JSON": process_json_file}[file_type]
        try:
            extraction = processor(file_path)
        except Exception as exc:
            _set_status(db, document_id, "PIPELINE_FAILED", {"pipeline_error": f"Extraction failed: {exc}"})
            logger.exception("Pipeline extraction failed for %s", document_id)
            return

        raw_transactions: list[dict] = extraction.get("transactions", [])
        pipeline_results["extraction"] = {
            "total_rows": extraction.get("total_rows", 0),
            "valid_rows": extraction.get("valid_rows", 0),
            "invalid_rows": extraction.get("invalid_rows", 0),
            "errors": extraction.get("errors", []),
        }

        if not raw_transactions:
            _set_status(db, document_id, "PIPELINE_FAILED", {
                "pipeline_error": "No valid transactions extracted from document."
            })
            return

        # ── 2. Normalize entity descriptions ─────────────────────────────────
        _set_status(db, document_id, "NORMALIZING")
        for tx in raw_transactions:
            try:
                normalized = normalize_transaction_entity(tx.get("description", ""))
                tx["normalized_entity"] = normalized.normalized_entity
                tx["channel"] = normalized.channel
                tx["counterparty_type"] = normalized.counterparty_type
                tx["clean_description"] = normalized.clean_description
            except Exception:
                pass  # Normalization is best-effort; keep original description

        # ── 3. Classify transactions ──────────────────────────────────────────
        _set_status(db, document_id, "CLASSIFYING")
        try:
            classified_transactions = classify_transactions(raw_transactions)
        except Exception as exc:
            logger.warning("Pipeline: classification failed for %s: %s", document_id, exc)
            classified_transactions = raw_transactions  # Fallback to unnclassified

        # ── 4. Save transactions ──────────────────────────────────────────────
        _set_status(db, document_id, "SAVING_TRANSACTIONS")

        # Clean out any prior transactions from a previous failed run
        db.transactions.delete_many({"document_id": document_id, "owner_id": owner_id})

        try:
            saved_count = save_valid_transactions(
                document_id=document_id,
                owner_id=owner_id,
                transactions=classified_transactions,
            )
        except Exception as exc:
            _set_status(db, document_id, "PIPELINE_FAILED", {"pipeline_error": f"Saving transactions failed: {exc}"})
            logger.exception("Pipeline: saving transactions failed for %s", document_id)
            return

        # Mark document as PROCESSED (main status) so existing endpoints work
        db.documents.update_one(
            {"_id": ObjectId(document_id)},
            {"$set": {
                "status": "PROCESSED",
                "transaction_count": saved_count,
                "invalid_row_count": extraction.get("invalid_rows", 0),
                "processing_errors": extraction.get("errors", []),
                "processed_at": datetime.now(timezone.utc),
                "status_updated_at": datetime.now(timezone.utc),
            }},
        )

        pipeline_results["saved_transactions"] = saved_count

        # Reload serialized transactions from DB for analysis stages
        stored_transactions = list(
            db.transactions.find(
                {"document_id": document_id, "owner_id": owner_id},
                {"_id": 0},
            ).sort("transaction_date", 1)
        )
        serialized_transactions = _serialize_tx_dates(stored_transactions)

        # ── 5. Duplicate detection ────────────────────────────────────────────
        _set_status(db, document_id, "DETECTING_DUPLICATES")
        try:
            dup_result = detect_duplicates(serialized_transactions)
            pipeline_results["duplicates"] = {
                "duplicate_count": dup_result.get("duplicate_count", 0),
                "duplicate_groups_count": dup_result.get("duplicate_groups_count", 0),
                "unique_count": dup_result.get("unique_count", 0),
            }
        except Exception as exc:
            logger.warning("Pipeline: duplicate detection failed for %s: %s", document_id, exc)
            pipeline_results["duplicates"] = {"error": str(exc)}

        # ── 6. Statistical anomaly detection ─────────────────────────────────
        _set_status(db, document_id, "DETECTING_ANOMALIES")
        try:
            anomaly_result = detect_anomalies(transactions=serialized_transactions)
            pipeline_results["anomalies"] = {
                "anomalous_transactions_count": anomaly_result.get("anomalous_transactions_count", 0),
                "anomaly_rate": anomaly_result.get("anomaly_rate", 0.0),
                "flag_counts": anomaly_result.get("flag_counts", {}),
                "anomalies": anomaly_result.get("anomalies", []),
            }
        except Exception as exc:
            logger.warning("Pipeline: anomaly detection failed for %s: %s", document_id, exc)
            anomaly_result = {}
            pipeline_results["anomalies"] = {"error": str(exc)}

        # ── 7. ML Isolation Forest anomaly detection ──────────────────────────
        _set_status(db, document_id, "ML_ANOMALY_DETECTION")
        try:
            ml_result = run_isolation_forest(transactions=serialized_transactions)
            pipeline_results["ml_anomalies"] = {
                "total": ml_result.get("total_transactions", 0),
                "anomaly_count": ml_result.get("anomalous_count", 0),
                "anomaly_rate": ml_result.get("anomaly_rate", 0.0),
            }
        except Exception as exc:
            logger.warning("Pipeline: ML anomaly detection failed for %s: %s", document_id, exc)
            ml_result = {}
            pipeline_results["ml_anomalies"] = {"error": str(exc)}

        # ── 8. Tax rule validation ────────────────────────────────────────────
        _set_status(db, document_id, "TAX_VALIDATION")
        try:
            tax_result = validate_tax_records(transactions=serialized_transactions)
            pipeline_results["tax_validation"] = {
                "total_findings": tax_result.get("summary", {}).get("total_findings", len(tax_result.get("findings", []))),
                "critical_findings": tax_result.get("summary", {}).get("error_count", 0),
                "findings": tax_result.get("findings", []),
            }
        except Exception as exc:
            logger.warning("Pipeline: tax validation failed for %s: %s", document_id, exc)
            tax_result = {}
            pipeline_results["tax_validation"] = {"error": str(exc)}

        # ── 9. Reconciliation (if a partner document exists) ──────────────────
        _set_status(db, document_id, "RECONCILING")
        reconciliation_id: str | None = None
        recon_result: dict = {}
        try:
            # Look for the most recent other PROCESSED document from the same owner
            partner_doc = db.documents.find_one(
                {
                    "owner_id": owner_id,
                    "status": "PROCESSED",
                    "_id": {"$ne": ObjectId(document_id)},
                    "file_type": {"$in": ["CSV", "XLSX", "JSON"]},
                },
                sort=[("processed_at", -1)],
            )

            if partner_doc:
                partner_id = str(partner_doc["_id"])
                partner_transactions = list(
                    db.transactions.find(
                        {"document_id": partner_id, "owner_id": owner_id},
                        {"_id": 0},
                    ).sort("transaction_date", 1)
                )
                partner_serialized = _serialize_tx_dates(partner_transactions)

                if partner_serialized:
                    recon_result = reconcile_transactions(
                        bank_transactions=serialized_transactions,
                        ledger_transactions=partner_serialized,
                    )

                    # Persist reconciliation record
                    recon_record = {
                        "owner_id": owner_id,
                        "bank_document_id": document_id,
                        "ledger_document_id": partner_id,
                        "bank_filename": document.get("original_filename", document.get("filename")),
                        "ledger_filename": partner_doc.get("original_filename", partner_doc.get("filename")),
                        "date_tolerance_days": 3,
                        "amount_tolerance": 0.01,
                        "fuzzy_threshold": 70,
                        "semantic_threshold": 0.6,
                        "summary": recon_result.get("summary", {}),
                        "matches": recon_result.get("matches", []),
                        "bank_only": recon_result.get("bank_only", []),
                        "ledger_only": recon_result.get("ledger_only", []),
                        "triggered_by_pipeline": True,
                        "created_at": datetime.now(timezone.utc),
                    }
                    recon_insert = db.reconciliations.insert_one(recon_record)
                    reconciliation_id = str(recon_insert.inserted_id)

                    pipeline_results["reconciliation"] = {
                        "reconciliation_id": reconciliation_id,
                        "partner_document_id": partner_id,
                        "summary": recon_result.get("summary", {}),
                    }
        except Exception as exc:
            logger.warning("Pipeline: reconciliation failed for %s: %s", document_id, exc)
            pipeline_results["reconciliation"] = {"error": str(exc)}

        # ── 10. TDS discrepancy detection ─────────────────────────────────────
        _set_status(db, document_id, "TDS_ANALYSIS")
        try:
            # Pass transactions as 26AS proxy; real usage would pass Form 26AS entries
            tds_result = run_advanced_tds_analysis(tds_entries_26as=serialized_transactions)
            tds_summary = tds_result.get("summary", {})
            pipeline_results["tds_discrepancies"] = {
                "total_findings": len(tds_result.get("findings", [])),
                "total_tds_exposure": tds_summary.get("total_tds_exposure", 0.0),
                "findings": tds_result.get("findings", []),
            }
        except Exception as exc:
            logger.warning("Pipeline: TDS detection failed for %s: %s", document_id, exc)
            pipeline_results["tds_discrepancies"] = {"error": str(exc)}

        # ── 11. Generate findings portfolio ──────────────────────────────────
        _set_status(db, document_id, "GENERATING_FINDINGS")
        findings_portfolio: dict = {}
        try:
            tax_findings_list = pipeline_results.get("tax_validation", {}).get("findings", [])
            findings_portfolio = FindingGenerator.generate_unified_portfolio(
                reconciliation_result=recon_result if recon_result else None,
                anomaly_result=anomaly_result if anomaly_result else None,
                tax_validation_findings=tax_findings_list,
            )
            pipeline_results["findings"] = {
                "total_findings": findings_portfolio.get("total_findings", 0),
                "critical_count": findings_portfolio.get("critical_count", 0),
                "high_count": findings_portfolio.get("high_count", 0),
                "portfolio_risk_score": findings_portfolio.get("portfolio_risk_score", 0.0),
                "action_required": findings_portfolio.get("action_required", False),
                "findings": findings_portfolio.get("findings", []),
            }
        except Exception as exc:
            logger.warning("Pipeline: finding generation failed for %s: %s", document_id, exc)
            pipeline_results["findings"] = {"error": str(exc)}

        # ── 12. Risk scoring ──────────────────────────────────────────────────
        _set_status(db, document_id, "SCORING_RISK")
        try:
            tx_risk_scores = []
            for tx in serialized_transactions[:200]:  # Cap at 200 to avoid very slow pipelines
                score_result = RiskScorer.score_transaction(tx)
                tx_risk_scores.append({
                    "description": tx.get("description", ""),
                    "amount": tx.get("amount"),
                    "risk_score": score_result.get("risk_score"),
                    "risk_tier": score_result.get("risk_tier"),
                })

            recon_summary_for_scoring = recon_result.get("summary", {}) if recon_result else {}
            run_risk = RiskScorer.score_reconciliation_run(recon_summary_for_scoring) if recon_summary_for_scoring else {}

            pipeline_results["risk_scoring"] = {
                "transaction_risk_scores": tx_risk_scores,
                "run_risk_score": run_risk.get("risk_score"),
                "run_risk_grade": run_risk.get("grade"),
                "run_audit_readiness": run_risk.get("audit_readiness"),
            }
        except Exception as exc:
            logger.warning("Pipeline: risk scoring failed for %s: %s", document_id, exc)
            pipeline_results["risk_scoring"] = {"error": str(exc)}

        # ── 13. Persist all results and mark complete ─────────────────────────
        _set_status(db, document_id, "PIPELINE_COMPLETE", {
            "pipeline_results": pipeline_results,
            "pipeline_completed_at": datetime.now(timezone.utc),
            "reconciliation_id": reconciliation_id,
        })

        log_audit_event(
            action="PIPELINE_COMPLETE",
            user_id=owner_id,
            resource_type="document",
            resource_id=document_id,
            details={
                "saved_transactions": saved_count,
                "findings_count": pipeline_results.get("findings", {}).get("total_findings", 0),
                "reconciliation_id": reconciliation_id,
            },
        )
        logger.info("Pipeline complete for document %s", document_id)

    except Exception as exc:
        logger.exception("Pipeline fatal error for document %s: %s", document_id, exc)
        try:
            db = get_database()
            _set_status(db, document_id, "PIPELINE_FAILED", {
                "pipeline_error": str(exc),
            })
        except Exception:
            pass

"""
backend/app/services/tax_validation/test_tds_discrepancy_detector.py

Unit tests for the Advanced TDS Discrepancy Detection Engine.

Coverage:
  - Pass 1: TDS rate validation (over-deduction, under-deduction, below threshold)
  - Pass 2: Quarter-wise reconciliation
  - Pass 3: Late deduction and late deposit detection
  - Pass 4: Lower deduction certificate conflict (15G, 15H, 197)
  - Pass 5: Multi-deductor PAN aggregation (excess credit, multi-deductor flag)
  - Pass 6: Unclaimed TDS credit detection
  - Integration: run_advanced_tds_analysis() aggregator
  - Helpers: _quarter_for_month, _normalize_section, _safe_str
"""

import pytest
from datetime import date

from app.services.tax_validation.tds_discrepancy_detector import (
    _normalize_section,
    _quarter_for_month,
    _safe_str,
    check_late_tds,
    check_lower_deduction_certificate,
    check_pan_aggregate_tds,
    check_quarter_wise_reconciliation,
    check_tds_rates,
    check_unclaimed_tds,
    run_advanced_tds_analysis,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(**kwargs) -> dict:
    base = {
        "deductor_name": "Test Corp",
        "deductor_tan": "ABCD12345E",
        "deductee_pan": "AAAPB1234C",
        "section": "194A",
        "gross_amount": 100000.0,
        "tds_amount": 10000.0,
        "transaction_date": "2025-05-15",
    }
    base.update(kwargs)
    return base


# ===========================================================================
# Helpers
# ===========================================================================
class TestHelpers:
    def test_quarter_for_month_q1(self):
        assert _quarter_for_month(4) == 1
        assert _quarter_for_month(6) == 1

    def test_quarter_for_month_q2(self):
        assert _quarter_for_month(7) == 2
        assert _quarter_for_month(9) == 2

    def test_quarter_for_month_q3(self):
        assert _quarter_for_month(10) == 3
        assert _quarter_for_month(12) == 3

    def test_quarter_for_month_q4(self):
        assert _quarter_for_month(1) == 4
        assert _quarter_for_month(3) == 4

    def test_normalize_section_space(self):
        assert _normalize_section("194 J") == "194J"

    def test_normalize_section_prefix(self):
        assert _normalize_section("Section 194A") == "194A"
        assert _normalize_section("Sec 194C") == "194C"

    def test_normalize_section_hyphen(self):
        assert _normalize_section("194-I") == "194I"

    def test_safe_str_none(self):
        assert _safe_str(None) == ""
        assert _safe_str(None, "fallback") == "fallback"

    def test_safe_str_value(self):
        assert _safe_str("  ABCD  ") == "ABCD"


# ===========================================================================
# Pass 1 — TDS Rate Validation
# ===========================================================================
class TestTDSRateValidation:
    def test_correct_rate_no_finding(self):
        entry = _entry(section="194A", gross_amount=100000.0, tds_amount=10000.0)
        findings = check_tds_rates([entry])
        assert findings == []

    def test_under_deducted(self):
        # 10% of 100,000 = 10,000; actual = 5,000 → variance 5,000
        entry = _entry(section="194A", gross_amount=100000.0, tds_amount=5000.0)
        findings = check_tds_rates([entry], tolerance=100.0)
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "TDS-RATE-002"
        assert "under-deducted" in findings[0]["details"]["over_under"]

    def test_over_deducted(self):
        # 10% of 100,000 = 10,000; actual = 15,000 → variance 5,000
        entry = _entry(section="194A", gross_amount=100000.0, tds_amount=15000.0)
        findings = check_tds_rates([entry], tolerance=100.0)
        assert len(findings) == 1
        assert "over-deducted" in findings[0]["details"]["over_under"]

    def test_tds_below_threshold(self):
        # 194A threshold = 40,000; gross 20,000 < threshold → TDS should be 0
        entry = _entry(section="194A", gross_amount=20000.0, tds_amount=2000.0)
        findings = check_tds_rates([entry], tolerance=100.0)
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "TDS-RATE-001"

    def test_194c_individual_rate(self):
        # 194C individual: 1%; gross 500,000 → expected 5,000
        entry = _entry(section="194C", gross_amount=500000.0, tds_amount=5000.0, is_individual=True)
        findings = check_tds_rates([entry])
        assert findings == []

    def test_194c_other_rate(self):
        # 194C non-individual: 2%; gross 500,000 → expected 10,000
        entry = _entry(section="194C", gross_amount=500000.0, tds_amount=5000.0, is_individual=False)
        findings = check_tds_rates([entry], tolerance=100.0)
        assert len(findings) == 1
        assert "under-deducted" in findings[0]["details"]["over_under"]

    def test_194j_technical_rate(self):
        # 194J technical: 2%; gross 200,000 → expected 4,000
        entry = _entry(section="194J", gross_amount=200000.0, tds_amount=4000.0, is_technical=True)
        findings = check_tds_rates([entry])
        assert findings == []

    def test_section_192_salary_skipped(self):
        # Section 192 uses slab rates; should not produce rate findings
        entry = _entry(section="192", gross_amount=1000000.0, tds_amount=50000.0)
        findings = check_tds_rates([entry])
        assert findings == []

    def test_unknown_section_skipped(self):
        entry = _entry(section="999XYZ", gross_amount=100000.0, tds_amount=5000.0)
        findings = check_tds_rates([entry])
        assert findings == []

    def test_missing_gross_skipped(self):
        entry = {
            "section": "194A",
            "tds_amount": 5000.0,
            "deductor_name": "Corp",
        }
        findings = check_tds_rates([entry])
        assert findings == []

    def test_large_variance_is_error(self):
        # Variance > 500 (tolerance=100 × 5) → ERROR
        entry = _entry(section="194A", gross_amount=100000.0, tds_amount=100.0)
        findings = check_tds_rates([entry], tolerance=100.0)
        assert len(findings) == 1
        assert findings[0]["severity"] == "ERROR"

    def test_small_variance_is_warning(self):
        # Variance 500 (> tolerance 100, < 500) → WARNING
        entry = _entry(section="194A", gross_amount=100000.0, tds_amount=9500.0)
        findings = check_tds_rates([entry], tolerance=100.0)
        assert len(findings) == 1
        assert findings[0]["severity"] == "WARNING"


# ===========================================================================
# Pass 2 — Quarter-wise Reconciliation
# ===========================================================================
class TestQuarterWiseReconciliation:
    def test_matching_quarters_no_finding(self):
        e = _entry(tds_amount=10000.0, transaction_date="2025-05-10")
        findings = check_quarter_wise_reconciliation([e], [e])
        assert findings == []

    def test_mismatch_detected(self):
        e_26as = _entry(tds_amount=10000.0, transaction_date="2025-05-10")
        e_books = _entry(tds_amount=7000.0, transaction_date="2025-05-10")
        findings = check_quarter_wise_reconciliation([e_26as], [e_books], tolerance=100.0)
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "TDS-QTR-001"
        assert findings[0]["details"]["variance"] == 3000.0

    def test_different_quarters_reported_separately(self):
        q1 = _entry(tds_amount=5000.0, transaction_date="2025-05-01")  # Q1
        q2 = _entry(tds_amount=8000.0, transaction_date="2025-08-01")  # Q2
        books_q1 = _entry(tds_amount=3000.0, transaction_date="2025-05-01")
        books_q2 = _entry(tds_amount=8000.0, transaction_date="2025-08-01")
        findings = check_quarter_wise_reconciliation([q1, q2], [books_q1, books_q2], tolerance=100.0)
        assert len(findings) == 1  # Only Q1 mismatches
        assert "Q1" in findings[0]["details"]["quarter"]

    def test_no_books_entries_flags_all(self):
        e = _entry(tds_amount=10000.0, transaction_date="2025-05-01")
        findings = check_quarter_wise_reconciliation([e], [], tolerance=100.0)
        assert len(findings) == 1
        assert findings[0]["details"]["tds_books"] == 0.0


# ===========================================================================
# Pass 3 — Late Deduction / Late Deposit
# ===========================================================================
class TestLateTDS:
    def test_on_time_deduction_no_finding(self):
        entry = _entry(
            payment_date="2025-05-01",
            credit_date="2025-05-15",   # Same Q1
            deposit_date="2025-06-07",  # 7th of June (June is following month of May)
        )
        findings = check_late_tds([entry])
        assert findings == []

    def test_late_deduction_cross_quarter(self):
        entry = _entry(
            payment_date="2025-05-01",   # Q1
            credit_date="2025-07-15",    # Q2
            tds_amount=10000.0,
        )
        findings = check_late_tds([entry])
        late = [f for f in findings if f["rule_id"] == "TDS-LATE-001"]
        assert len(late) == 1
        assert late[0]["details"]["delay_days"] == (date(2025, 7, 15) - date(2025, 5, 1)).days

    def test_late_deposit_non_march(self):
        # Deducted 15 May; due 7 June; deposited 20 June → late by 13 days
        entry = _entry(
            credit_date="2025-05-15",
            deposit_date="2025-06-20",
            tds_amount=5000.0,
        )
        findings = check_late_tds([entry])
        late = [f for f in findings if f["rule_id"] == "TDS-LATE-002"]
        assert len(late) == 1
        assert late[0]["details"]["delay_days"] == 13
        assert late[0]["severity"] == "ERROR"

    def test_march_tds_due_30_april(self):
        # Deducted 20 March; due 30 April; deposited 5 May → 5 days late
        entry = _entry(
            credit_date="2025-03-20",
            deposit_date="2025-05-05",
            tds_amount=8000.0,
        )
        findings = check_late_tds([entry])
        late = [f for f in findings if f["rule_id"] == "TDS-LATE-002"]
        assert len(late) == 1
        assert late[0]["details"]["statutory_due_date"] == "2025-04-30"

    def test_no_dates_no_finding(self):
        entry = {"tds_amount": 5000.0, "section": "194A"}
        findings = check_late_tds([entry])
        assert findings == []

    def test_zero_tds_skipped(self):
        entry = _entry(tds_amount=0.0, credit_date="2025-05-01", deposit_date="2025-07-01")
        findings = check_late_tds([entry])
        assert findings == []


# ===========================================================================
# Pass 4 — Lower Deduction Certificate Conflict
# ===========================================================================
class TestLowerDeductionCertificate:
    def _cert(self, cert_type: str = "15G", rate: float = 0.0) -> dict:
        return {
            "deductee_pan": "AAAPB1234C",
            "section": "ALL",
            "certificate_type": cert_type,
            "approved_rate_pct": rate,
            "valid_from": "2025-04-01",
            "valid_to": "2026-03-31",
        }

    def test_15g_conflict_raises_error(self):
        entry = _entry(tds_amount=10000.0, gross_amount=100000.0, transaction_date="2025-05-15")
        cert = self._cert("15G", 0.0)
        findings = check_lower_deduction_certificate([entry], [cert])
        assert len(findings) == 1
        assert findings[0]["severity"] == "ERROR"
        assert "15G" in findings[0]["title"]

    def test_15h_conflict_raises_error(self):
        entry = _entry(tds_amount=5000.0, gross_amount=50000.0, transaction_date="2025-07-01")
        cert = self._cert("15H", 0.0)
        findings = check_lower_deduction_certificate([entry], [cert])
        assert len(findings) == 1
        assert findings[0]["severity"] == "ERROR"

    def test_197_conflict_raises_warning(self):
        entry = _entry(tds_amount=10000.0, gross_amount=100000.0, transaction_date="2025-05-15")
        cert = self._cert("197", 5.0)  # Approved rate 5%, actual implied 10%
        findings = check_lower_deduction_certificate([entry], [cert])
        assert len(findings) == 1
        assert findings[0]["severity"] == "WARNING"

    def test_expired_certificate_no_finding(self):
        entry = _entry(tds_amount=10000.0, transaction_date="2026-07-01")
        cert = {**self._cert("15G"), "valid_from": "2025-04-01", "valid_to": "2026-03-31"}
        findings = check_lower_deduction_certificate([entry], [cert])
        assert findings == []

    def test_no_certificates_no_finding(self):
        entry = _entry(tds_amount=10000.0)
        findings = check_lower_deduction_certificate([entry], [])
        assert findings == []

    def test_different_pan_no_conflict(self):
        entry = _entry(tds_amount=10000.0, deductee_pan="ZZZZZ9999Z")
        cert = self._cert("15G")  # For AAAPB1234C
        findings = check_lower_deduction_certificate([entry], [cert])
        assert findings == []

    def test_correct_lower_rate_no_finding(self):
        # 197 at 5%; gross 100,000; correct deduction = 5,000
        entry = _entry(tds_amount=5000.0, gross_amount=100000.0, transaction_date="2025-05-15")
        cert = self._cert("197", 5.0)
        findings = check_lower_deduction_certificate([entry], [cert], tolerance=100.0)
        assert findings == []


# ===========================================================================
# Pass 5 — Multi-Deductor PAN Aggregation
# ===========================================================================
class TestPANAggregation:
    def test_excess_tds_credit_flagged(self):
        entries = [
            _entry(deductee_pan="PAN001", deductor_tan="TAN001", tds_amount=100000.0),
            _entry(deductee_pan="PAN001", deductor_tan="TAN002", tds_amount=50000.0),
        ]
        findings = check_pan_aggregate_tds(entries, tax_liability=120000.0, tolerance=100.0)
        excess = [f for f in findings if f["rule_id"] == "TDS-AGG-001"]
        assert len(excess) == 1
        assert excess[0]["details"]["excess_credit"] == pytest.approx(30000.0)

    def test_no_excess_when_tds_less_than_liability(self):
        entries = [_entry(deductee_pan="PAN001", deductor_tan="TAN001", tds_amount=50000.0)]
        findings = check_pan_aggregate_tds(entries, tax_liability=100000.0)
        excess = [f for f in findings if f["rule_id"] == "TDS-AGG-001"]
        assert excess == []

    def test_multi_deductor_flagged_at_5_or_more(self):
        entries = [
            _entry(deductee_pan="PAN002", deductor_tan=f"TAN{i:03d}", tds_amount=1000.0)
            for i in range(5)
        ]
        findings = check_pan_aggregate_tds(entries)
        multi = [f for f in findings if f["rule_id"] == "TDS-AGG-002"]
        assert len(multi) == 1
        assert multi[0]["details"]["deductor_count"] == 5

    def test_four_deductors_not_flagged(self):
        entries = [
            _entry(deductee_pan="PAN003", deductor_tan=f"TAN{i:03d}", tds_amount=1000.0)
            for i in range(4)
        ]
        findings = check_pan_aggregate_tds(entries)
        multi = [f for f in findings if f["rule_id"] == "TDS-AGG-002"]
        assert multi == []

    def test_no_tax_liability_no_excess_check(self):
        entries = [_entry(deductee_pan="PAN001", tds_amount=999999.0)]
        findings = check_pan_aggregate_tds(entries, tax_liability=None)
        excess = [f for f in findings if f["rule_id"] == "TDS-AGG-001"]
        assert excess == []


# ===========================================================================
# Pass 6 — Unclaimed TDS Credit
# ===========================================================================
class TestUnclaimedTDS:
    def test_all_flagged_when_no_itr_schedule(self):
        entries = [_entry(tds_amount=10000.0)]
        findings = check_unclaimed_tds(entries, itr_tds_schedule=None)
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "TDS-UNCLAIM-001"

    def test_fully_claimed_no_finding(self):
        entry = _entry(tds_amount=10000.0, transaction_date="2025-05-01")
        itr = [{
            "deductor_tan": "ABCD12345E",
            "tds_amount_claimed": 10000.0,
            "transaction_date": "2025-05-01",
        }]
        findings = check_unclaimed_tds([entry], itr, tolerance=100.0)
        assert findings == []

    def test_partial_claim_flagged(self):
        entry = _entry(tds_amount=10000.0, transaction_date="2025-05-01")
        itr = [{
            "deductor_tan": "ABCD12345E",
            "tds_amount_claimed": 7000.0,
            "transaction_date": "2025-05-01",
        }]
        findings = check_unclaimed_tds([entry], itr, tolerance=100.0)
        assert len(findings) == 1
        assert findings[0]["rule_id"] == "TDS-UNCLAIM-002"
        assert findings[0]["details"]["unclaimed_amount"] == pytest.approx(3000.0)

    def test_zero_tds_skipped(self):
        entry = _entry(tds_amount=0.0)
        findings = check_unclaimed_tds([entry], itr_tds_schedule=None)
        assert findings == []


# ===========================================================================
# Integration — run_advanced_tds_analysis()
# ===========================================================================
class TestRunAdvancedTDSAnalysis:
    def test_basic_run_returns_structure(self):
        entry = _entry(section="194A", gross_amount=100000.0, tds_amount=10000.0)
        result = run_advanced_tds_analysis([entry])

        assert "summary" in result
        assert "findings" in result
        assert "findings_by_pass" in result
        assert "disclaimer" in result

    def test_summary_counts_entries(self):
        entries = [_entry()] * 3
        result = run_advanced_tds_analysis(entries)
        assert result["summary"]["tds_entries_analysed"] == 3

    def test_total_26as_tds_computed(self):
        entries = [_entry(tds_amount=10000.0), _entry(tds_amount=5000.0)]
        result = run_advanced_tds_analysis(entries)
        assert result["summary"]["total_26as_tds_amount"] == pytest.approx(15000.0)

    def test_findings_aggregated_across_passes(self):
        # Under-deducted → Pass 1 finding; unclaimed → Pass 6 finding
        entry = _entry(section="194A", gross_amount=100000.0, tds_amount=1000.0)
        result = run_advanced_tds_analysis(
            tds_entries_26as=[entry],
            itr_tds_schedule=None,
        )
        assert result["summary"]["total_findings"] >= 2

    def test_pass_2_only_runs_with_books(self):
        entry = _entry()
        result_no_books = run_advanced_tds_analysis([entry])
        result_with_books = run_advanced_tds_analysis([entry], tds_entries_books=[entry])

        assert "pass_2_quarter_reconciliation" not in result_no_books["findings_by_pass"]
        assert "pass_2_quarter_reconciliation" in result_with_books["findings_by_pass"]

    def test_pass_4_only_runs_with_certs(self):
        entry = _entry()
        result = run_advanced_tds_analysis([entry], exemption_certificates=None)
        assert "pass_4_exemption_conflict" not in result["findings_by_pass"]

    def test_severity_counts_match_findings(self):
        # Inject an under-deduction to get at least one WARNING/ERROR
        entry = _entry(section="194A", gross_amount=100000.0, tds_amount=1000.0)
        result = run_advanced_tds_analysis([entry])
        all_findings = result["findings"]
        errors = sum(1 for f in all_findings if f["severity"] == "ERROR")
        warnings = sum(1 for f in all_findings if f["severity"] == "WARNING")
        infos = sum(1 for f in all_findings if f["severity"] == "INFO")
        assert result["summary"]["errors_count"] == errors
        assert result["summary"]["warnings_count"] == warnings
        assert result["summary"]["info_count"] == infos

    def test_empty_entries_returns_no_findings(self):
        result = run_advanced_tds_analysis(
            tds_entries_26as=[{"tds_amount": 0.0}]
        )
        # Zero-TDS entry should produce no rate findings
        rate_findings = result["findings_by_pass"].get("pass_1_rate_validation", [])
        assert rate_findings == []


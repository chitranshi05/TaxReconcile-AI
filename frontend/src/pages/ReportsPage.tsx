import { useState, useEffect } from 'react'
import { PageHero } from '../components/PageHero'
import { loadDocuments, getTaxRules, validateDocumentTaxCompliance } from '../services/documents'
import type {
  DocumentListItem,
  DocumentTaxValidationResponse,
  TaxRulesResponse,
} from '../types/api'

interface ReportsPageProps {
  onNavigate: (page: string) => void
  hero?: {
    line1: string
    line2: string
    kicker: string
    lede: string
    cue: string
  }
}

export function ReportsPage({ hero }: ReportsPageProps) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([])
  const [selectedDocId, setSelectedDocId] = useState<string>('')
  const [selectedFY, setSelectedFY] = useState<string>('2025-26')
  const [isSeniorCitizen, setIsSeniorCitizen] = useState(false)
  const [taxRules, setTaxRules] = useState<TaxRulesResponse | null>(null)
  const [auditResult, setAuditResult] = useState<DocumentTaxValidationResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const list = loadDocuments()
    setDocuments(list)
    const processed = list.filter((d) => d.status === 'PROCESSED')
    if (processed.length > 0 && processed[0]) {
      setSelectedDocId(processed[0].document_id)
    }

    getTaxRules()
      .then((res) => {
        setTaxRules(res)
        if (res.supported_financial_years && res.supported_financial_years.length > 0 && res.supported_financial_years[0]) {
          setSelectedFY(res.supported_financial_years[0])
        }
      })
      .catch(() => {
        // use default
      })
  }, [])

  const handleRunAudit = async () => {
    if (!selectedDocId) {
      setError('Please select a processed statement to audit.')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const res = await validateDocumentTaxCompliance(selectedDocId, {
        financial_year: selectedFY,
        is_senior_citizen: isSeniorCitizen,
      })
      setAuditResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tax compliance audit failed.')
    } finally {
      setIsLoading(false)
    }
  }

  const handlePrint = () => {
    window.print()
  }

  const currentRules = taxRules?.rules_by_fy?.[selectedFY] || {}
  const processedDocs = documents.filter((d) => d.status === 'PROCESSED')

  return (
    <>
      <PageHero
        kicker={hero?.kicker ?? 'Summaries, audit trails, tax-ready exports.'}
        line1={hero?.line1 ?? 'The show'}
        line2={hero?.line2 ?? 'on paper.'}
        lede={hero?.lede ?? 'Generate and export reconciliation summaries, audit trails and tax-ready reports.'}
        cue={hero?.cue ?? 'CUE 06 · Reports'}
      />

      {/* Compliance Target & Controls */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="section-header">
          <div>
            <span className="mono cue-label">COMPLIANCE ENGINE</span>
            <h2 className="section-title">Indian Tax Compliance Audit (IT Act & GST)</h2>
          </div>
          {auditResult && (
            <button
              type="button"
              className="action-btn action-btn-accent mono"
              onClick={handlePrint}
            >
              Print / Export Report 🖨️
            </button>
          )}
        </div>

        {error && (
          <div className="inspect-banner error mono" role="alert" style={{ marginBottom: 16 }}>
            {error}
          </div>
        )}

        <div className="reconciliation-setup-grid">
          <div className="form-group">
            <label className="mono cue-label" style={{ display: 'block', marginBottom: 8 }}>
              TARGET STATEMENT DOCUMENT
            </label>
            <select
              className="table-search mono"
              style={{ width: '100%', cursor: 'pointer' }}
              value={selectedDocId}
              onChange={(e) => setSelectedDocId(e.target.value)}
            >
              <option value="">Select statement to audit…</option>
              {processedDocs.map((doc) => (
                <option key={doc.document_id} value={doc.document_id}>
                  {doc.filename} ({doc.transaction_count || 0} txns)
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="mono cue-label" style={{ display: 'block', marginBottom: 8 }}>
              ASSESSMENT / FINANCIAL YEAR
            </label>
            <select
              className="table-search mono"
              style={{ width: '100%', cursor: 'pointer' }}
              value={selectedFY}
              onChange={(e) => setSelectedFY(e.target.value)}
            >
              {(taxRules?.supported_financial_years || ['2025-26', '2024-25', '2023-24']).map((fy) => (
                <option key={fy} value={fy}>
                  FY {fy}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <label className="mono cue-label" style={{ display: 'block', marginBottom: 8 }}>
              TAXPAYER CATEGORY
            </label>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, cursor: 'pointer', userSelect: 'none' }}>
              <input
                type="checkbox"
                checked={isSeniorCitizen}
                onChange={(e) => setIsSeniorCitizen(e.target.checked)}
                style={{ width: 16, height: 16 }}
              />
              <span className="mono" style={{ fontSize: 13 }}>Senior Citizen (60+ years)</span>
            </label>
          </div>

          <div className="form-group" style={{ display: 'flex', alignItems: 'flex-end' }}>
            <button
              type="button"
              className="btn btn-primary mono"
              style={{ width: '100%' }}
              disabled={isLoading || !selectedDocId}
              onClick={handleRunAudit}
            >
              {isLoading ? 'Auditing records…' : 'Run Statutory Compliance Audit →'}
            </button>
          </div>
        </div>
      </div>

      {/* Statutory Limits Reference Strip */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="mono cue-label">SEC 80C</span>
          </div>
          <div className="stat-value mono t-num">₹1,50,000</div>
          <div className="stat-label">Chapter VI-A Cap</div>
          <div className="stat-sub">EPF, PPF, ELSS, Insurance</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="mono cue-label">SEC 80D</span>
          </div>
          <div className="stat-value mono t-num">
            {isSeniorCitizen ? '₹50,000' : '₹25,000'}
          </div>
          <div className="stat-label">Health Insurance Exemption</div>
          <div className="stat-sub">{isSeniorCitizen ? 'Senior Citizen slab' : 'Standard individual slab'}</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="mono cue-label">SEC 269ST</span>
          </div>
          <div className="stat-value mono t-num" style={{ color: 'var(--accent-red)' }}>
            ₹2,00,000
          </div>
          <div className="stat-label">Single-Day Cash Limit</div>
          <div className="stat-sub">Strict statutory prohibition</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="mono cue-label">FY {selectedFY}</span>
          </div>
          <div className="stat-value mono t-num" style={{ color: 'var(--parsec)' }}>
            Active
          </div>
          <div className="stat-label">Audit Engine Status</div>
          <div className="stat-sub">{Object.keys(currentRules).length || 4} Rules calibrated</div>
        </div>
      </div>

      {/* Audit Findings */}
      {auditResult && (
        <div className="card">
          <div className="section-header">
            <div>
              <span className="mono cue-label">AUDIT VERDICT</span>
              <h2 className="section-title">
                Tax Compliance Findings ({auditResult.findings?.length || 0})
              </h2>
            </div>
            <span
              className={`status-tag mono ${
                auditResult.summary?.status === 'COMPLIANT'
                  ? 'is-processed'
                  : auditResult.summary?.status === 'BREACH'
                  ? 'is-failed'
                  : 'is-pending'
              }`}
            >
              {auditResult.summary?.status || 'REVIEW'}
            </span>
          </div>

          {auditResult.summary && (
            <div className="inspect-stats stats-grid" style={{ marginBottom: 20 }}>
              <div className="stat-card">
                <div className="stat-value mono t-num">{auditResult.transaction_count}</div>
                <div className="stat-label">Audited Transactions</div>
              </div>
              <div className="stat-card">
                <div className="stat-value mono t-num" style={{ color: auditResult.summary.breaches_count ? 'var(--accent-red)' : 'var(--parsec)' }}>
                  {auditResult.summary.breaches_count}
                </div>
                <div className="stat-label">Statutory Breaches</div>
              </div>
              <div className="stat-card">
                <div className="stat-value mono t-num" style={{ color: auditResult.summary.warnings_count ? 'var(--accent-yellow)' : 'var(--muted)' }}>
                  {auditResult.summary.warnings_count}
                </div>
                <div className="stat-label">Warnings & Inconsistencies</div>
              </div>
            </div>
          )}

          {auditResult.findings && auditResult.findings.length > 0 ? (
            <div className="table-responsive">
              <table className="data-table mono" aria-label="Tax audit findings">
                <thead>
                  <tr>
                    <th>Rule / Section</th>
                    <th>Issue Description</th>
                    <th className="t-num" style={{ textAlign: 'right' }}>Amount (₹)</th>
                    <th className="t-num" style={{ textAlign: 'right' }}>Statutory Cap (₹)</th>
                    <th style={{ textAlign: 'right' }}>Severity</th>
                  </tr>
                </thead>
                <tbody>
                  {auditResult.findings.map((f, idx) => (
                    <tr key={idx}>
                      <td>
                        <span className="file-badge mono">{f.section || f.rule_id}</span>
                        <span className="filename-text" style={{ display: 'inline-block', marginLeft: 8 }}>
                          {f.title}
                        </span>
                      </td>
                      <td className="cell-truncate" style={{ maxWidth: 360 }} title={f.description}>
                        {f.description}
                      </td>
                      <td className="t-num" style={{ textAlign: 'right', fontWeight: 600 }}>
                        {f.amount !== undefined ? `₹${f.amount.toLocaleString('en-IN')}` : '—'}
                      </td>
                      <td className="t-num" style={{ textAlign: 'right', color: 'var(--muted)' }}>
                        {f.threshold !== undefined ? `₹${f.threshold.toLocaleString('en-IN')}` : '—'}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <span
                          className={`status-tag mono ${
                            f.severity === 'BREACH'
                              ? 'is-failed'
                              : f.severity === 'WARNING'
                              ? 'is-pending'
                              : 'is-processed'
                          }`}
                        >
                          {f.severity}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="placeholder-state mono">
              <div className="placeholder-text" style={{ color: 'var(--parsec)' }}>
                Full Compliance Confirmed
              </div>
              <div className="placeholder-sub">
                No statutory tax breaches or 269ST cash violations were detected in this document for FY {selectedFY}.
              </div>
            </div>
          )}

          {auditResult.disclaimer && (
            <p className="validation-note mono" style={{ marginTop: 20 }}>
              {auditResult.disclaimer}
            </p>
          )}
        </div>
      )}
    </>
  )
}

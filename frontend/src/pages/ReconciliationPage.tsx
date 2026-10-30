import { useState, useEffect } from 'react'
import { PageHero } from '../components/PageHero'
import { loadDocuments, runReconciliation, listReconciliations } from '../services/documents'
import type { DocumentListItem, ReconciliationResult } from '../types/api'

interface ReconciliationPageProps {
  onNavigate: (page: string) => void
  hero?: {
    line1: string
    line2: string
    kicker: string
    lede: string
    cue: string
  }
}

export function ReconciliationPage({
  onNavigate,
  hero,
}: ReconciliationPageProps) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([])
  const [bankDocId, setBankDocId] = useState<string>('')
  const [ledgerDocId, setLedgerDocId] = useState<string>('')
  const [dateTolerance, setDateTolerance] = useState<number>(1)
  const [amountTolerance, setAmountTolerance] = useState<number>(0.0)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ReconciliationResult | null>(null)
  const [history, setHistory] = useState<ReconciliationResult[]>([])
  const [activeTab, setActiveTab] = useState<'MATCHES' | 'BANK_ONLY' | 'LEDGER_ONLY'>('MATCHES')

  // Load available documents and past reconciliations
  useEffect(() => {
    const list = loadDocuments()
    setDocuments(list)
    const processed = list.filter((d) => d.status === 'PROCESSED')
    if (processed.length >= 2 && processed[0] && processed[1]) {
      setBankDocId(processed[0].document_id)
      setLedgerDocId(processed[1].document_id)
    } else if (processed.length === 1 && processed[0]) {
      setBankDocId(processed[0].document_id)
    }

    listReconciliations()
      .then((res) => {
        setHistory(res.reconciliations || [])
        if (res.reconciliations && res.reconciliations.length > 0 && res.reconciliations[0]) {
          setResult(res.reconciliations[0])
        }
      })
      .catch(() => {
        // history empty or network
      })
  }, [])

  const handleRunReconciliation = async () => {
    if (!bankDocId || !ledgerDocId) {
      setError('Please select both a Bank document and a Ledger document.')
      return
    }
    if (bankDocId === ledgerDocId) {
      setError('Bank and Ledger documents must be two distinct statements.')
      return
    }

    setIsRunning(true)
    setError(null)

    try {
      const res = await runReconciliation({
        bank_document_id: bankDocId,
        ledger_document_id: ledgerDocId,
        date_tolerance_days: dateTolerance,
        amount_tolerance: amountTolerance,
      })
      setResult(res)
      // prepend to history
      setHistory((prev) => [res, ...prev.filter((r) => r.reconciliation_id !== res.reconciliation_id)])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reconciliation execution failed.')
    } finally {
      setIsRunning(false)
    }
  }

  const processedDocs = documents.filter((d) => d.status === 'PROCESSED')

  return (
    <>
      <PageHero
        kicker={hero?.kicker ?? 'Match across banks, books and returns.'}
        line1={hero?.line1 ?? 'Two sources.'}
        line2={hero?.line2 ?? 'One clock.'}
        lede={hero?.lede ?? 'Automatically match transactions across sources and surface discrepancies for review.'}
        cue={hero?.cue ?? 'CUE 04 · Match'}
      />

      {/* Reconciliation Engine Configuration Card */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="section-header">
          <div>
            <span className="mono cue-label">ENGINE CONFIGURATION</span>
            <h2 className="section-title">Run Reconciliation</h2>
          </div>
          <span className="mono t-num table-counter">
            {processedDocs.length} PROCESSED STATEMENTS
          </span>
        </div>

        {error && (
          <div className="inspect-banner error mono" role="alert" style={{ marginBottom: 16 }}>
            {error}
          </div>
        )}

        <div className="reconciliation-setup-grid">
          {/* Source 1: Bank */}
          <div className="form-group">
            <label className="mono cue-label" style={{ display: 'block', marginBottom: 8 }}>
              SOURCE A · BANK STATEMENT
            </label>
            <select
              className="table-search mono"
              style={{ width: '100%', cursor: 'pointer' }}
              value={bankDocId}
              onChange={(e) => setBankDocId(e.target.value)}
            >
              <option value="">Select Bank Statement…</option>
              {processedDocs.map((doc) => (
                <option key={doc.document_id} value={doc.document_id}>
                  {doc.filename} ({doc.transaction_count || 0} txns)
                </option>
              ))}
            </select>
          </div>

          {/* Source 2: Ledger */}
          <div className="form-group">
            <label className="mono cue-label" style={{ display: 'block', marginBottom: 8 }}>
              SOURCE B · INTERNAL LEDGER / BOOKS
            </label>
            <select
              className="table-search mono"
              style={{ width: '100%', cursor: 'pointer' }}
              value={ledgerDocId}
              onChange={(e) => setLedgerDocId(e.target.value)}
            >
              <option value="">Select Company Ledger…</option>
              {processedDocs.map((doc) => (
                <option key={doc.document_id} value={doc.document_id}>
                  {doc.filename} ({doc.transaction_count || 0} txns)
                </option>
              ))}
            </select>
          </div>

          {/* Tolerances */}
          <div className="form-group">
            <label className="mono cue-label" style={{ display: 'block', marginBottom: 8 }}>
              DATE TOLERANCE (± DAYS)
            </label>
            <input
              type="number"
              min="0"
              max="30"
              className="table-search mono"
              style={{ width: '100%' }}
              value={dateTolerance}
              onChange={(e) => setDateTolerance(Number(e.target.value) || 0)}
            />
          </div>

          <div className="form-group">
            <label className="mono cue-label" style={{ display: 'block', marginBottom: 8 }}>
              AMOUNT TOLERANCE (₹)
            </label>
            <input
              type="number"
              min="0"
              step="0.01"
              className="table-search mono"
              style={{ width: '100%' }}
              value={amountTolerance}
              onChange={(e) => setAmountTolerance(Number(e.target.value) || 0)}
            />
          </div>
        </div>

        <div style={{ marginTop: 20, display: 'flex', gap: 12, alignItems: 'center' }}>
          <button
            type="button"
            className="btn btn-primary mono"
            disabled={isRunning || processedDocs.length < 2}
            onClick={handleRunReconciliation}
          >
            {isRunning ? 'Reconciling statements…' : 'Run Deterministic Match →'}
          </button>
          {processedDocs.length < 2 && (
            <span className="mono" style={{ color: 'var(--muted)', fontSize: 13 }}>
              You need at least 2 processed statements to perform reconciliation.
            </span>
          )}
        </div>
      </div>

      {/* History Drawer / Past Runs */}
      {history.length > 1 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="section-header">
            <div>
              <span className="mono cue-label">PRIOR RUNS</span>
              <h2 className="section-title">Reconciliation History</h2>
            </div>
            <span className="mono t-num">{history.length} SAVED RUNS</span>
          </div>

          <div className="history-pill-list">
            {history.map((h) => {
              const isActive = result?.reconciliation_id === h.reconciliation_id
              return (
                <button
                  key={h.reconciliation_id}
                  type="button"
                  className={`filter-pill mono${isActive ? ' is-active' : ''}`}
                  onClick={() => setResult(h)}
                >
                  {h.bank_filename || 'Bank'} vs {h.ledger_filename || 'Ledger'} · {h.summary?.match_percentage ?? 0}% Match
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Results View */}
      {result && result.summary && (
        <>
          {/* Summary Stat Cards */}
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-card-header">
                <span className="mono cue-label">01</span>
              </div>
              <div className="stat-value mono t-num" style={{ color: 'var(--parsec)' }}>
                {result.summary.match_percentage}%
              </div>
              <div className="stat-label">Match Percentage</div>
              <div className="stat-sub">
                {result.summary.matched_count} of {Math.max(result.summary.bank_total_transactions, result.summary.ledger_total_transactions)} matched
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-card-header">
                <span className="mono cue-label">02</span>
              </div>
              <div className="stat-value mono t-num">{result.summary.matched_count}</div>
              <div className="stat-label">Matched Pairs</div>
              <div className="stat-sub">Cleared transactions</div>
            </div>

            <div className="stat-card">
              <div className="stat-card-header">
                <span className="mono cue-label">03</span>
              </div>
              <div className="stat-value mono t-num" style={{ color: result.summary.bank_only_count ? 'var(--accent-yellow)' : 'var(--muted)' }}>
                {result.summary.bank_only_count}
              </div>
              <div className="stat-label">Bank Only (Unreconciled)</div>
              <div className="stat-sub">Missing in company books</div>
            </div>

            <div className="stat-card">
              <div className="stat-card-header">
                <span className="mono cue-label">04</span>
              </div>
              <div className="stat-value mono t-num" style={{ color: result.summary.ledger_only_count ? 'var(--accent-red)' : 'var(--muted)' }}>
                {result.summary.ledger_only_count}
              </div>
              <div className="stat-label">Ledger Only (Unreconciled)</div>
              <div className="stat-sub">Uncleared deposits/payments</div>
            </div>
          </div>

          {/* Detailed Discrepancy & Matches Table */}
          <div className="card">
            <div className="section-header">
              <div>
                <span className="mono cue-label">RECONCILIATION AUDIT TRAIL</span>
                <h2 className="section-title">
                  {activeTab === 'MATCHES'
                    ? `Matched Pairs (${result.matches?.length || 0})`
                    : activeTab === 'BANK_ONLY'
                    ? `Bank Only Unreconciled (${result.bank_only?.length || 0})`
                    : `Ledger Only Unreconciled (${result.ledger_only?.length || 0})`}
                </h2>
              </div>

              <div className="table-filter-pills">
                <button
                  type="button"
                  className={`filter-pill mono${activeTab === 'MATCHES' ? ' is-active' : ''}`}
                  onClick={() => setActiveTab('MATCHES')}
                >
                  Matched ({result.matches?.length || 0})
                </button>
                <button
                  type="button"
                  className={`filter-pill mono${activeTab === 'BANK_ONLY' ? ' is-active' : ''}`}
                  onClick={() => setActiveTab('BANK_ONLY')}
                >
                  Bank Only ({result.bank_only?.length || 0})
                </button>
                <button
                  type="button"
                  className={`filter-pill mono${activeTab === 'LEDGER_ONLY' ? ' is-active' : ''}`}
                  onClick={() => setActiveTab('LEDGER_ONLY')}
                >
                  Ledger Only ({result.ledger_only?.length || 0})
                </button>
              </div>
            </div>

            {/* TAB: MATCHED PAIRS */}
            {activeTab === 'MATCHES' && (
              <div className="table-responsive">
                {result.matches?.length === 0 ? (
                  <div className="placeholder-state mono">
                    <div className="placeholder-text">No matches found between these statements.</div>
                  </div>
                ) : (
                  <table className="data-table mono" aria-label="Matched pairs">
                    <thead>
                      <tr>
                        <th>Bank Statement Tx</th>
                        <th>Ledger Entry</th>
                        <th className="t-num" style={{ textAlign: 'right' }}>Amount (₹)</th>
                        <th>Match Type</th>
                        <th className="t-num" style={{ textAlign: 'right' }}>Delta</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.matches?.map((pair, idx) => (
                        <tr key={idx}>
                          <td>
                            <div className="filename-text">{pair.bank_transaction?.description || 'Bank Tx'}</div>
                            <div className="stat-sub mono t-num">
                              {pair.bank_transaction?.transaction_date?.slice(0, 10)}
                            </div>
                          </td>
                          <td>
                            <div className="filename-text">{pair.ledger_transaction?.description || 'Ledger Tx'}</div>
                            <div className="stat-sub mono t-num">
                              {pair.ledger_transaction?.transaction_date?.slice(0, 10)}
                            </div>
                          </td>
                          <td className="t-num" style={{ textAlign: 'right', fontWeight: 600 }}>
                            ₹{(pair.bank_transaction?.amount ?? pair.bank_transaction?.debit ?? pair.bank_transaction?.credit ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </td>
                          <td>
                            <span className="status-tag mono is-processed">
                              {pair.match_type || 'EXACT'}
                            </span>
                          </td>
                          <td className="t-num" style={{ textAlign: 'right', color: pair.date_diff_days ? 'var(--accent-yellow)' : 'var(--muted)' }}>
                            {pair.date_diff_days ? `±${pair.date_diff_days}d` : '0d'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {/* TAB: BANK ONLY */}
            {activeTab === 'BANK_ONLY' && (
              <div className="table-responsive">
                {result.bank_only?.length === 0 ? (
                  <div className="placeholder-state mono">
                    <div className="placeholder-text">All bank transactions were reconciled cleanly.</div>
                  </div>
                ) : (
                  <table className="data-table mono" aria-label="Bank only unreconciled">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Description</th>
                        <th className="t-num" style={{ textAlign: 'right' }}>Debit (₹)</th>
                        <th className="t-num" style={{ textAlign: 'right' }}>Credit (₹)</th>
                        <th>Flag</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.bank_only?.map((tx, idx) => (
                        <tr key={idx}>
                          <td className="t-num">{tx.transaction_date?.slice(0, 10)}</td>
                          <td className="cell-truncate" title={tx.description || ''}>{tx.description || '—'}</td>
                          <td className="t-num" style={{ textAlign: 'right', color: 'var(--accent-red)' }}>
                            {tx.debit ? tx.debit.toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '—'}
                          </td>
                          <td className="t-num" style={{ textAlign: 'right', color: 'var(--parsec)' }}>
                            {tx.credit ? tx.credit.toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '—'}
                          </td>
                          <td>
                            <span className="status-tag mono is-failed">MISSING IN BOOKS</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {/* TAB: LEDGER ONLY */}
            {activeTab === 'LEDGER_ONLY' && (
              <div className="table-responsive">
                {result.ledger_only?.length === 0 ? (
                  <div className="placeholder-state mono">
                    <div className="placeholder-text">All ledger transactions were cleared in bank.</div>
                  </div>
                ) : (
                  <table className="data-table mono" aria-label="Ledger only unreconciled">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Description</th>
                        <th className="t-num" style={{ textAlign: 'right' }}>Debit (₹)</th>
                        <th className="t-num" style={{ textAlign: 'right' }}>Credit (₹)</th>
                        <th>Flag</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.ledger_only?.map((tx, idx) => (
                        <tr key={idx}>
                          <td className="t-num">{tx.transaction_date?.slice(0, 10)}</td>
                          <td className="cell-truncate" title={tx.description || ''}>{tx.description || '—'}</td>
                          <td className="t-num" style={{ textAlign: 'right', color: 'var(--accent-red)' }}>
                            {tx.debit ? tx.debit.toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '—'}
                          </td>
                          <td className="t-num" style={{ textAlign: 'right', color: 'var(--parsec)' }}>
                            {tx.credit ? tx.credit.toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '—'}
                          </td>
                          <td>
                            <span className="status-tag mono is-pending">UNCLEARED IN BANK</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        </>
      )}

      {!result && (
        <div className="card">
          <div className="placeholder-state">
            <span className="coming-soon-kicker mono">READY</span>
            <div className="placeholder-text">Select your bank & ledger statements above</div>
            <div className="placeholder-sub">
              Our reconciliation engine pairs debits to credits with customizable date & amount tolerances.
            </div>
            {processedDocs.length === 0 && (
              <button
                type="button"
                className="action-btn action-btn-accent mono"
                style={{ marginTop: 14 }}
                onClick={() => onNavigate('documents')}
              >
                Ingest Statements Now →
              </button>
            )}
          </div>
        </div>
      )}
    </>
  )
}

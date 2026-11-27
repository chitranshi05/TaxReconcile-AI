import { useState, useEffect } from 'react'
import type { DocumentMetadata } from '../types/api'
import { listDocuments } from '../services/documents'
import {
  runReconciliation,
  listReconciliations,
  downloadReconciliationReport,
  type ReconciliationRun,
  type ReconciliationSummary,
} from '../services/reconciliation'
import { DownloadIcon, ReconcileIcon } from '../components/Icons'

export function ReconciliationPage() {
  const [documents, setDocuments] = useState<DocumentMetadata[]>([])
  const [bankDocId, setBankDocId] = useState<string>('')
  const [ledgerDocId, setLedgerDocId] = useState<string>('')
  const [isRunning, setIsRunning] = useState(false)
  const [activeResult, setActiveResult] = useState<any | null>(null)
  const [historicalRuns, setHistoricalRuns] = useState<ReconciliationRun[]>([])
  const [activeTab, setActiveTab] = useState<'MATCHES' | 'BANK_ONLY' | 'LEDGER_ONLY'>('MATCHES')
  const [downloadingFormat, setDownloadingFormat] = useState<string | null>(null)

  function loadData() {
    listDocuments()
      .then((docs) => {
        const proc = docs.filter((d) => d.status === 'PROCESSED')
        setDocuments(proc)
        if (proc.length >= 2 && proc[0] && proc[1]) {
          if (!bankDocId) setBankDocId(proc[0].id)
          if (!ledgerDocId) setLedgerDocId(proc[1].id)
        } else if (proc.length === 1 && !bankDocId && proc[0]) {
          setBankDocId(proc[0].id)
        }
      })
      .catch(() => {})

    listReconciliations()
      .then((res) => {
        setHistoricalRuns(res.reconciliations || [])
      })
      .catch(() => {})
  }

  useEffect(() => {
    loadData()
  }, [])

  async function handleExecute() {
    if (!bankDocId || !ledgerDocId) {
      alert('Please select both a Bank statement and an Accounting Ledger statement.')
      return
    }
    if (bankDocId === ledgerDocId) {
      alert('Bank statement and Ledger statement must be two distinct documents.')
      return
    }

    setIsRunning(true)
    try {
      const res = await runReconciliation(bankDocId, ledgerDocId)
      setActiveResult(res)
      loadData()
    } catch (err: any) {
      alert(err.message || 'Reconciliation failed.')
    } finally {
      setIsRunning(false)
    }
  }

  async function handleDownload(recId: string, format: 'xlsx' | 'pdf') {
    setDownloadingFormat(format)
    try {
      await downloadReconciliationReport(recId, format)
    } catch (err: any) {
      alert(err.message || 'Download failed.')
    } finally {
      setDownloadingFormat(null)
    }
  }

  const summary: ReconciliationSummary | null = activeResult?.summary || null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="ledger-header">
        <div className="ledger-header-text">
          <h1>Reconciliation Engine</h1>
          <p>Multi-source automated cross-matching between external bank statements and internal general ledgers.</p>
        </div>
      </div>

      {/* Two-Statement Selector Panel */}
      <div className="paper-panel">
        <div className="panel-header">
          <div className="panel-title-group">
            <h2 className="panel-title">Statement Pairing</h2>
            <span className="panel-subtitle">Select distinct bank and accounting ledger documents</span>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '20px', alignItems: 'flex-end' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">1. Primary Bank Statement Source</label>
            <select className="form-select" value={bankDocId} onChange={(e) => setBankDocId(e.target.value)}>
              <option value="">Select bank statement…</option>
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename} ({d.file_type})
                </option>
              ))}
            </select>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">2. Internal Accounting Books / Ledger</label>
            <select className="form-select" value={ledgerDocId} onChange={(e) => setLedgerDocId(e.target.value)}>
              <option value="">Select books/ledger…</option>
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename} ({d.file_type})
                </option>
              ))}
            </select>
          </div>

          <div>
            <button
              className="btn btn-primary"
              onClick={handleExecute}
              disabled={isRunning || !bankDocId || !ledgerDocId}
              style={{ minHeight: '38px' }}
            >
              <ReconcileIcon size={14} className={isRunning ? 'spin' : ''} />
              {isRunning ? 'Reconciling Ledger…' : 'Execute Reconciliation'}
            </button>
          </div>
        </div>
      </div>

      {/* Summary KPI grid if result is present */}
      {summary && (
        <>
          <div className="kpi-grid">
            <div className="kpi-item">
              <span className="kpi-label">Reconciliation Rate</span>
              <span className="kpi-value" style={{ color: 'var(--brand-green)' }}>
                {summary.reconciliation_rate.toFixed(1)}%
              </span>
              <span className="kpi-sub">{summary.matched_count} verified matching pairs</span>
            </div>

            <div className="kpi-item">
              <span className="kpi-label">Bank-Only Unmatched</span>
              <span className="kpi-value" style={{ color: summary.bank_only_count > 0 ? 'var(--semantic-warning)' : 'var(--text-primary)' }}>
                {summary.bank_only_count}
              </span>
              <span className="kpi-sub">Appears in bank but missing in books</span>
            </div>

            <div className="kpi-item">
              <span className="kpi-label">Ledger-Only Unmatched</span>
              <span className="kpi-value" style={{ color: summary.ledger_only_count > 0 ? 'var(--semantic-warning)' : 'var(--text-primary)' }}>
                {summary.ledger_only_count}
              </span>
              <span className="kpi-sub">Appears in books but uncleared in bank</span>
            </div>

            <div className="kpi-item">
              <span className="kpi-label">Net Discrepancy</span>
              <span
                className="kpi-value"
                style={{
                  color: summary.net_discrepancy !== 0 ? 'var(--semantic-error)' : 'var(--semantic-success)',
                }}
              >
                ₹{Math.abs(summary.net_discrepancy).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </span>
              <span className="kpi-sub">
                {summary.net_discrepancy === 0 ? 'Zero variance (Balanced)' : 'Unreconciled balance differential'}
              </span>
            </div>
          </div>

          {/* Report Download Toolbar */}
          <div className="paper-panel" style={{ padding: '16px 20px', backgroundColor: 'var(--bg-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: '14px' }}>Reconciliation Run ID: {activeResult.reconciliation_id}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Matched: {activeResult.bank_filename} ↔ {activeResult.ledger_filename}
                </div>
              </div>

              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleDownload(activeResult.reconciliation_id, 'xlsx')}
                  disabled={downloadingFormat === 'xlsx'}
                >
                  <DownloadIcon size={13} />
                  {downloadingFormat === 'xlsx' ? 'Generating…' : 'Export Excel (.xlsx)'}
                </button>

                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => handleDownload(activeResult.reconciliation_id, 'pdf')}
                  disabled={downloadingFormat === 'pdf'}
                >
                  <DownloadIcon size={13} />
                  {downloadingFormat === 'pdf' ? 'Compiling…' : 'Export PDF Report (.pdf)'}
                </button>
              </div>
            </div>
          </div>

          {/* Breakdown Tabs */}
          <div className="paper-panel">
            <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-hairline)', paddingBottom: '12px', marginBottom: '16px' }}>
              {(['MATCHES', 'BANK_ONLY', 'LEDGER_ONLY'] as const).map((t) => (
                <button
                  key={t}
                  className={`btn btn-sm ${activeTab === t ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setActiveTab(t)}
                >
                  {t === 'MATCHES'
                    ? `Matched Pairs (${summary.matched_count})`
                    : t === 'BANK_ONLY'
                    ? `Bank Only (${summary.bank_only_count})`
                    : `Ledger Only (${summary.ledger_only_count})`}
                </button>
              ))}
            </div>

            <div className="table-container">
              <table className="ledger-table">
                {activeTab === 'MATCHES' ? (
                  <>
                    <thead>
                      <tr>
                        <th>Bank Date</th>
                        <th>Bank Narration</th>
                        <th className="num-col">Bank Amount</th>
                        <th>Ledger Date</th>
                        <th>Ledger Particulars</th>
                        <th className="num-col">Ledger Amount</th>
                        <th>Match Type</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(activeResult.matches || []).length === 0 ? (
                        <tr>
                          <td colSpan={7} style={{ textAlign: 'center', padding: '24px' }}>
                            No matched transactions found.
                          </td>
                        </tr>
                      ) : (
                        activeResult.matches.map((m: any, i: number) => (
                          <tr key={i}>
                            <td className="mono-cell">{m.bank_transaction?.transaction_date?.slice(0, 10) || '—'}</td>
                            <td>{m.bank_transaction?.description || '—'}</td>
                            <td className="num-col">
                              ₹{(m.bank_transaction?.amount ?? m.bank_transaction?.deposit ?? m.bank_transaction?.withdrawal ?? 0).toLocaleString()}
                            </td>
                            <td className="mono-cell">{m.ledger_transaction?.transaction_date?.slice(0, 10) || '—'}</td>
                            <td>{m.ledger_transaction?.description || '—'}</td>
                            <td className="num-col">
                              ₹{(m.ledger_transaction?.amount ?? m.ledger_transaction?.debit ?? m.ledger_transaction?.credit ?? 0).toLocaleString()}
                            </td>
                            <td>
                              <span className="status-badge processed">{m.match_type || 'EXACT'}</span>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </>
                ) : activeTab === 'BANK_ONLY' ? (
                  <>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Narration</th>
                        <th className="num-col">Withdrawal</th>
                        <th className="num-col">Deposit</th>
                        <th>Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(activeResult.bank_only || []).length === 0 ? (
                        <tr>
                          <td colSpan={5} style={{ textAlign: 'center', padding: '24px' }}>
                            Zero bank-only discrepancies.
                          </td>
                        </tr>
                      ) : (
                        activeResult.bank_only.map((b: any, i: number) => (
                          <tr key={i}>
                            <td className="mono-cell">{b.transaction_date?.slice(0, 10) || '—'}</td>
                            <td>{b.description || '—'}</td>
                            <td className="debit-amount">{b.withdrawal ? `₹${b.withdrawal.toLocaleString()}` : '—'}</td>
                            <td className="credit-amount">{b.deposit ? `₹${b.deposit.toLocaleString()}` : '—'}</td>
                            <td>
                              <span className="status-badge warning">Missing in Books</span>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </>
                ) : (
                  <>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Particulars</th>
                        <th className="num-col">Debit</th>
                        <th className="num-col">Credit</th>
                        <th>Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(activeResult.ledger_only || []).length === 0 ? (
                        <tr>
                          <td colSpan={5} style={{ textAlign: 'center', padding: '24px' }}>
                            Zero ledger-only discrepancies.
                          </td>
                        </tr>
                      ) : (
                        activeResult.ledger_only.map((l: any, i: number) => (
                          <tr key={i}>
                            <td className="mono-cell">{l.transaction_date?.slice(0, 10) || '—'}</td>
                            <td>{l.description || '—'}</td>
                            <td className="debit-amount">{l.debit ? `₹${l.debit.toLocaleString()}` : '—'}</td>
                            <td className="credit-amount">{l.credit ? `₹${l.credit.toLocaleString()}` : '—'}</td>
                            <td>
                              <span className="status-badge warning">Uncleared in Bank</span>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </>
                )}
              </table>
            </div>
          </div>
        </>
      )}

      {/* Historical Reconciliation Runs */}
      {historicalRuns.length > 0 && (
        <div className="paper-panel">
          <div className="panel-header">
            <div className="panel-title-group">
              <h2 className="panel-title">Prior Reconciliation Archives</h2>
              <span className="panel-subtitle">Archival runs recorded with download links</span>
            </div>
          </div>

          <div className="table-container">
            <table className="ledger-table">
              <thead>
                <tr>
                  <th>Run ID</th>
                  <th>Execution Timestamp</th>
                  <th>Matched Pairs</th>
                  <th className="num-col">Match Rate</th>
                  <th className="num-col">Net Discrepancy</th>
                  <th style={{ textAlign: 'right' }}>Download Reports</th>
                </tr>
              </thead>
              <tbody>
                {historicalRuns.map((run) => (
                  <tr key={run.reconciliation_id}>
                    <td className="mono-cell">{run.reconciliation_id.slice(-8)}…</td>
                    <td className="mono-cell">
                      {run.created_at ? new Date(run.created_at).toLocaleString() : '—'}
                    </td>
                    <td>
                      <span className="status-badge processed">{run.summary?.matched_count || 0} pairs</span>
                    </td>
                    <td className="num-col">{run.summary?.reconciliation_rate?.toFixed(1) || '0.0'}%</td>
                    <td
                      className="num-col"
                      style={{
                        color: run.summary?.net_discrepancy !== 0 ? 'var(--semantic-error)' : 'inherit',
                      }}
                    >
                      ₹{Math.abs(run.summary?.net_discrepancy || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '6px' }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleDownload(run.reconciliation_id, 'xlsx')}
                        >
                          XLSX
                        </button>
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => handleDownload(run.reconciliation_id, 'pdf')}
                        >
                          PDF
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

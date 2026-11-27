import { useState, useEffect } from 'react'
import { listReconciliations, downloadReconciliationReport, type ReconciliationRun } from '../services/reconciliation'
import { DownloadIcon } from '../components/Icons'

export function ReportsPage() {
  const [runs, setRuns] = useState<ReconciliationRun[]>([])
  const [loading, setLoading] = useState(true)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  function load() {
    setLoading(true)
    listReconciliations()
      .then((res) => {
        setRuns(res.reconciliations || [])
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  async function handleDownload(id: string, format: 'xlsx' | 'pdf') {
    setDownloadingId(`${id}-${format}`)
    try {
      await downloadReconciliationReport(id, format)
    } catch (err: any) {
      alert(err.message || 'Download failed.')
    } finally {
      setDownloadingId(null)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="ledger-header">
        <div className="ledger-header-text">
          <h1>Archival Reports & Audit Statements</h1>
          <p>Downloadable reconciliation statements formatted for institutional auditing and statutory reporting.</p>
        </div>
        <div className="ledger-header-actions">
          <button className="btn btn-secondary btn-sm" onClick={load}>
            Refresh Reports
          </button>
        </div>
      </div>

      <div className="paper-panel">
        <div className="panel-header">
          <div className="panel-title-group">
            <h2 className="panel-title">Available Audit Artifacts</h2>
            <span className="panel-subtitle">{runs.length} generated statements ready for export</span>
          </div>
        </div>

        <div className="table-container">
          <table className="ledger-table">
            <thead>
              <tr>
                <th>Statement Identifier</th>
                <th>Generation Date</th>
                <th>Sources Reconciled</th>
                <th className="num-col">Match Velocity</th>
                <th className="num-col">Discrepancy (₹)</th>
                <th style={{ textAlign: 'right' }}>Export Formats</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '32px' }}>
                    Loading archival statements…
                  </td>
                </tr>
              ) : runs.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '36px' }}>
                    <div className="empty-state">
                      <div className="empty-state-title">No statements generated yet</div>
                      <div className="empty-state-text">
                        Run a reconciliation between bank and ledger statements to generate exportable audit reports.
                      </div>
                    </div>
                  </td>
                </tr>
              ) : (
                runs.map((r) => (
                  <tr key={r.reconciliation_id}>
                    <td>
                      <div style={{ fontWeight: 600 }}>Statement #{r.reconciliation_id.slice(-8)}</div>
                      <div className="mono-cell" style={{ fontSize: '10.5px' }}>
                        ID: {r.reconciliation_id}
                      </div>
                    </td>
                    <td className="mono-cell">
                      {r.created_at ? new Date(r.created_at).toLocaleString() : '—'}
                    </td>
                    <td>
                      <div>Bank: {r.bank_filename || '—'}</div>
                      <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                        Books: {r.ledger_filename || '—'}
                      </div>
                    </td>
                    <td className="num-col">
                      <span className="status-badge processed">
                        {r.summary?.reconciliation_rate?.toFixed(1) || '0.0'}%
                      </span>
                    </td>
                    <td
                      className="num-col"
                      style={{
                        color: r.summary?.net_discrepancy !== 0 ? 'var(--semantic-error)' : 'inherit',
                      }}
                    >
                      ₹{Math.abs(r.summary?.net_discrepancy || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '6px' }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleDownload(r.reconciliation_id, 'xlsx')}
                          disabled={downloadingId === `${r.reconciliation_id}-xlsx`}
                        >
                          <DownloadIcon size={12} />
                          {downloadingId === `${r.reconciliation_id}-xlsx` ? '…' : 'Excel (.xlsx)'}
                        </button>
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => handleDownload(r.reconciliation_id, 'pdf')}
                          disabled={downloadingId === `${r.reconciliation_id}-pdf`}
                        >
                          <DownloadIcon size={12} />
                          {downloadingId === `${r.reconciliation_id}-pdf` ? '…' : 'PDF Report'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

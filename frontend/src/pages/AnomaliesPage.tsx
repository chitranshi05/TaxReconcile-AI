import { useState, useEffect } from 'react'
import { PageHero } from '../components/PageHero'
import { loadDocuments, getDocumentAnomalies, getDocumentDuplicates } from '../services/documents'
import type {
  DocumentListItem,
  DocumentAnomaliesResponse,
  DocumentDuplicatesResponse,
  AnomalyItem,
} from '../types/api'

interface AnomaliesPageProps {
  initialDocumentId?: string
  onNavigate?: (page: string) => void
  hero?: {
    line1: string
    line2: string
    kicker: string
    lede: string
    cue: string
  }
}

export function AnomaliesPage({
  initialDocumentId,
  onNavigate,
  hero,
}: AnomaliesPageProps) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([])
  const [selectedDocId, setSelectedDocId] = useState<string>('')
  const [anomaliesData, setAnomaliesData] = useState<DocumentAnomaliesResponse | null>(null)
  const [duplicatesData, setDuplicatesData] = useState<DocumentDuplicatesResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'ANOMALIES' | 'DUPLICATES'>('ANOMALIES')

  useEffect(() => {
    const list = loadDocuments()
    setDocuments(list)
    const processed = list.filter((d) => d.status === 'PROCESSED')

    if (initialDocumentId && list.some((d) => d.document_id === initialDocumentId)) {
      setSelectedDocId(initialDocumentId)
    } else if (processed.length > 0 && processed[0]) {
      setSelectedDocId(processed[0].document_id)
    }
  }, [initialDocumentId])

  useEffect(() => {
    if (!selectedDocId) {
      setAnomaliesData(null)
      setDuplicatesData(null)
      return
    }

    setIsLoading(true)
    setError(null)

    Promise.allSettled([
      getDocumentAnomalies(selectedDocId),
      getDocumentDuplicates(selectedDocId),
    ]).then(([anomResult, dupResult]) => {
      if (anomResult.status === 'fulfilled') {
        setAnomaliesData(anomResult.value)
      } else {
        setAnomaliesData(null)
      }

      if (dupResult.status === 'fulfilled') {
        setDuplicatesData(dupResult.value)
      } else {
        setDuplicatesData(null)
      }

      if (anomResult.status === 'rejected' && dupResult.status === 'rejected') {
        setError('Unable to analyze anomalies for this document. Verify the document is processed.')
      }

      setIsLoading(false)
    })
  }, [selectedDocId])

  const totalAnomalies = anomaliesData?.anomalous_transactions_count ?? 0
  const totalDuplicates = duplicatesData?.duplicate_count ?? 0
  const anomalyRate = anomaliesData?.anomaly_rate ?? 0
  const duplicateGroups = duplicatesData?.duplicate_groups_count ?? 0

  return (
    <>
      <PageHero
        kicker={hero?.kicker ?? 'Irregulars, duplicates, statistical outliers.'}
        line1={hero?.line1 ?? 'Flags in'}
        line2={hero?.line2 ?? 'the mix.'}
        lede={hero?.lede ?? 'AI-powered detection of irregular transactions, duplicate entries and statistical outliers.'}
        cue={hero?.cue ?? 'CUE 05 · Flags'}
      />

      {/* Document Selector */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="section-header">
          <div>
            <span className="mono cue-label">AUDIT TARGET</span>
            <h2 className="section-title">Select Document for Anomaly Detection</h2>
          </div>
          <span className="mono t-num">
            {documents.filter((d) => d.status === 'PROCESSED').length} PROCESSED
          </span>
        </div>

        <div className="table-controls" style={{ marginTop: 8 }}>
          <select
            className="table-search mono"
            style={{ maxWidth: 440, cursor: 'pointer' }}
            value={selectedDocId}
            onChange={(e) => setSelectedDocId(e.target.value)}
          >
            {documents.length === 0 ? (
              <option value="">No documents in workspace</option>
            ) : (
              documents.map((doc) => (
                <option key={doc.document_id} value={doc.document_id}>
                  {doc.filename} ({doc.status} · {doc.file_type})
                </option>
              ))
            )}
          </select>
        </div>
      </div>

      {error && (
        <div className="inspect-banner error mono" role="alert" style={{ marginBottom: 24 }}>
          {error}
        </div>
      )}

      {/* KPI Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="mono cue-label">01</span>
          </div>
          <div
            className="stat-value mono t-num"
            style={{ color: anomalyRate > 0 ? 'var(--signal-live)' : 'var(--parsec)' }}
          >
            {anomalyRate}%
          </div>
          <div className="stat-label">Anomaly Exposure Rate</div>
          <div className="stat-sub">Share of flagged transactions</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="mono cue-label">02</span>
          </div>
          <div
            className="stat-value mono t-num"
            style={{ color: totalAnomalies > 0 ? 'var(--accent-red)' : 'var(--muted)' }}
          >
            {totalAnomalies}
          </div>
          <div className="stat-label">Statistical Outliers (IQR)</div>
          <div className="stat-sub">Unusual amounts / bursts</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="mono cue-label">03</span>
          </div>
          <div
            className="stat-value mono t-num"
            style={{ color: totalDuplicates > 0 ? 'var(--accent-yellow)' : 'var(--muted)' }}
          >
            {totalDuplicates}
          </div>
          <div className="stat-label">Duplicate Candidates</div>
          <div className="stat-sub">Exact date & amount clones</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="mono cue-label">04</span>
          </div>
          <div className="stat-value mono t-num">{duplicateGroups}</div>
          <div className="stat-label">Duplicate Clusters</div>
          <div className="stat-sub">Groups requiring review</div>
        </div>
      </div>

      {/* Tabs & Table */}
      <div className="card">
        <div className="section-header">
          <div>
            <span className="mono cue-label">AUDIT FINDINGS</span>
            <h2 className="section-title">
              {activeTab === 'ANOMALIES'
                ? `Flagged Anomalies (${totalAnomalies})`
                : `Duplicate Groups (${duplicateGroups})`}
            </h2>
          </div>

          <div className="table-filter-pills">
            <button
              type="button"
              className={`filter-pill mono${activeTab === 'ANOMALIES' ? ' is-active' : ''}`}
              onClick={() => setActiveTab('ANOMALIES')}
            >
              Anomalies ({totalAnomalies})
            </button>
            <button
              type="button"
              className={`filter-pill mono${activeTab === 'DUPLICATES' ? ' is-active' : ''}`}
              onClick={() => setActiveTab('DUPLICATES')}
            >
              Duplicates ({totalDuplicates})
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="placeholder-state mono">
            <div className="placeholder-text">Analyzing transactions for statistical anomalies…</div>
          </div>
        ) : !selectedDocId ? (
          <div className="placeholder-state">
            <div className="placeholder-text">No document selected</div>
            <div className="placeholder-sub">Choose a processed statement from the menu above.</div>
            {onNavigate && (
              <button
                type="button"
                className="action-btn action-btn-accent mono"
                style={{ marginTop: 12, width: 'fit-content' }}
                onClick={() => onNavigate('documents')}
              >
                Go to Documents →
              </button>
            )}
          </div>
        ) : activeTab === 'ANOMALIES' ? (
          anomaliesData?.anomalies && anomaliesData.anomalies.length > 0 ? (
            <div className="table-responsive">
              <table className="data-table mono" aria-label="Anomalies table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Description</th>
                    <th className="t-num" style={{ textAlign: 'right' }}>Amount (₹)</th>
                    <th>Reason / Code</th>
                    <th style={{ textAlign: 'right' }}>Severity</th>
                  </tr>
                </thead>
                <tbody>
                  {anomaliesData.anomalies.map((item: AnomalyItem, idx: number) => {
                    const tx = item.transaction || {}
                    const amt = tx.amount ?? (tx.debit ?? tx.credit ?? 0)

                    return (
                      <tr key={idx}>
                        <td className="t-num">{tx.transaction_date?.slice(0, 10) || '—'}</td>
                        <td className="cell-truncate" style={{ maxWidth: 320 }} title={tx.description || ''}>
                          {tx.description || '—'}
                        </td>
                        <td className="t-num" style={{ textAlign: 'right', fontWeight: 600 }}>
                          ₹{Number(amt).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </td>
                        <td>
                          {item.reasons && item.reasons.length > 0 ? (
                            <span className="stat-sub">{item.reasons.join(', ')}</span>
                          ) : item.flags && item.flags.length > 0 ? (
                            <span className="stat-sub">{item.flags.join(', ')}</span>
                          ) : (
                            <span className="stat-sub">Statistical outlier</span>
                          )}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <span
                            className={`status-tag mono ${
                              item.severity === 'HIGH'
                                ? 'is-failed'
                                : item.severity === 'MEDIUM'
                                ? 'is-pending'
                                : 'is-uploaded'
                            }`}
                          >
                            {item.severity || 'FLAG'}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="placeholder-state mono">
              <div className="placeholder-text" style={{ color: 'var(--parsec)' }}>
                Clean Bill · No anomalies detected
              </div>
              <div className="placeholder-sub">
                No statistical outliers, sudden velocity spikes, or round-amount anomalies were found in this statement.
              </div>
            </div>
          )
        ) : (
          /* TAB: DUPLICATES */
          duplicatesData?.duplicate_groups && duplicatesData.duplicate_groups.length > 0 ? (
            <div className="duplicate-groups-list">
              {duplicatesData.duplicate_groups.map((group) => (
                <div key={group.group_id} className="duplicate-cluster-card">
                  <div className="cluster-header">
                    <div>
                      <span className="mono cue-label">CLUSTER {group.group_id}</span>
                      <h3 className="section-title" style={{ fontSize: '1rem', marginTop: 4 }}>
                        {group.count} Identical Transactions Detected
                      </h3>
                    </div>
                    <span className="status-tag mono is-pending">POTENTIAL DUPLICATE</span>
                  </div>

                  <div className="table-responsive" style={{ marginTop: 12 }}>
                    <table className="data-table mono" aria-label="Duplicate cluster items">
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Description</th>
                          <th className="t-num" style={{ textAlign: 'right' }}>Amount (₹)</th>
                          <th className="t-num" style={{ textAlign: 'right' }}>Debit (₹)</th>
                          <th className="t-num" style={{ textAlign: 'right' }}>Credit (₹)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {group.transactions?.map((tx, tIdx) => (
                          <tr key={tIdx}>
                            <td className="t-num">{tx.transaction_date?.slice(0, 10)}</td>
                            <td className="cell-truncate">{tx.description || '—'}</td>
                            <td className="t-num" style={{ textAlign: 'right' }}>
                              {tx.amount !== undefined && tx.amount !== null ? `₹${tx.amount.toLocaleString('en-IN')}` : '—'}
                            </td>
                            <td className="t-num" style={{ textAlign: 'right', color: 'var(--accent-red)' }}>
                              {tx.debit ? `₹${tx.debit.toLocaleString('en-IN')}` : '—'}
                            </td>
                            <td className="t-num" style={{ textAlign: 'right', color: 'var(--parsec)' }}>
                              {tx.credit ? `₹${tx.credit.toLocaleString('en-IN')}` : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="placeholder-state mono">
              <div className="placeholder-text" style={{ color: 'var(--parsec)' }}>
                No duplicate candidate transactions detected
              </div>
              <div className="placeholder-sub">
                Every transaction in this statement appears distinct by date, description, and amount.
              </div>
            </div>
          )
        )}
      </div>
    </>
  )
}

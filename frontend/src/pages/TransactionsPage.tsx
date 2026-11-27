import { useState, useEffect, useMemo } from 'react'
import type { DocumentMetadata } from '../types/api'
import { listDocuments, getDocumentTransactions, type StoredTransaction } from '../services/documents'
import { SearchIcon } from '../components/Icons'

interface TransactionsPageProps {
  initialDocumentId?: string | null
}

export function TransactionsPage({ initialDocumentId }: TransactionsPageProps) {
  const [documents, setDocuments] = useState<DocumentMetadata[]>([])
  const [selectedDocId, setSelectedDocId] = useState<string>(initialDocumentId || '')
  const [transactions, setTransactions] = useState<StoredTransaction[]>([])
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<'ALL' | 'DEBIT' | 'CREDIT'>('ALL')

  useEffect(() => {
    listDocuments()
      .then((docs) => {
        const processed = docs.filter((d) => d.status === 'PROCESSED')
        setDocuments(processed)
        if (!selectedDocId && processed.length > 0 && processed[0]) {
          setSelectedDocId(processed[0].id)
        }
      })
      .catch(() => {})
  }, [selectedDocId])

  useEffect(() => {
    if (!selectedDocId) {
      setTransactions([])
      return
    }
    setLoading(true)
    getDocumentTransactions(selectedDocId)
      .then((res) => {
        setTransactions(res.transactions || [])
      })
      .catch(() => {
        setTransactions([])
      })
      .finally(() => setLoading(false))
  }, [selectedDocId])

  const filtered = useMemo(() => {
    return transactions.filter((tx) => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const desc = (tx.description || '').toLowerCase()
        const amt = String(tx.amount || tx.debit || tx.credit || '')
        if (!desc.includes(q) && !amt.includes(q)) return false
      }
      if (filterType === 'DEBIT' && !(tx.debit && tx.debit > 0)) return false
      if (filterType === 'CREDIT' && !(tx.credit && tx.credit > 0)) return false
      return true
    })
  }, [transactions, searchQuery, filterType])

  const totals = useMemo(() => {
    let totalDebit = 0
    let totalCredit = 0
    transactions.forEach((tx) => {
      if (tx.debit) totalDebit += tx.debit
      if (tx.credit) totalCredit += tx.credit
    })
    return { totalDebit, totalCredit }
  }, [transactions])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="ledger-header">
        <div className="ledger-header-text">
          <h1>Financial General Ledger</h1>
          <p>Institutional journal records extracted and normalized with strict tabular monetary precision.</p>
        </div>
      </div>

      {/* Control bar: Document Selector & Search */}
      <div className="paper-panel" style={{ padding: '16px 20px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <label className="form-label" style={{ marginBottom: 0 }}>
              Statement Source:
            </label>
            <select
              className="form-select"
              value={selectedDocId}
              onChange={(e) => setSelectedDocId(e.target.value)}
              style={{ minWidth: '260px' }}
            >
              {documents.length === 0 ? (
                <option value="">No processed statements available</option>
              ) : (
                documents.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.filename} ({d.file_type})
                  </option>
                ))
              )}
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                className="form-input"
                placeholder="Search narration or amount…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ paddingLeft: '32px', width: '240px' }}
              />
              <span style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}>
                <SearchIcon size={14} />
              </span>
            </div>

            <div style={{ display: 'inline-flex', gap: '4px' }}>
              {(['ALL', 'DEBIT', 'CREDIT'] as const).map((t) => (
                <button
                  key={t}
                  className={`btn btn-sm ${filterType === t ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setFilterType(t)}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Quick Summary of Current Document */}
      <div className="kpi-grid">
        <div className="kpi-item">
          <span className="kpi-label">Ledger Row Count</span>
          <span className="kpi-value">{transactions.length}</span>
          <span className="kpi-sub">{filtered.length} matching criteria</span>
        </div>
        <div className="kpi-item">
          <span className="kpi-label">Aggregate Debits (Withdrawals)</span>
          <span className="kpi-value" style={{ color: 'var(--semantic-error)' }}>
            ₹{totals.totalDebit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </span>
          <span className="kpi-sub">Total outflow recorded</span>
        </div>
        <div className="kpi-item">
          <span className="kpi-label">Aggregate Credits (Deposits)</span>
          <span className="kpi-value" style={{ color: 'var(--semantic-success)' }}>
            ₹{totals.totalCredit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </span>
          <span className="kpi-sub">Total inflow recorded</span>
        </div>
      </div>

      {/* The Financial Ledger Table */}
      <div className="paper-panel">
        <div className="table-container">
          <table className="ledger-table">
            <thead>
              <tr>
                <th style={{ width: '40px' }}>#</th>
                <th style={{ width: '110px' }}>Value Date</th>
                <th>Narration & Particulars</th>
                <th className="num-col" style={{ width: '130px' }}>Debit (₹)</th>
                <th className="num-col" style={{ width: '130px' }}>Credit (₹)</th>
                <th className="num-col" style={{ width: '140px' }}>Running Balance</th>
                <th style={{ width: '110px', textAlign: 'right' }}>Transaction ID</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '36px' }}>
                    <span className="mono-cell">Streaming ledger records from database…</span>
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '36px' }}>
                    <div className="empty-state">
                      <div className="empty-state-title">No transactions recorded</div>
                      <div className="empty-state-text">
                        {selectedDocId
                          ? 'No transactions matched the search or filter query.'
                          : 'Please process a document in the Documents Manager to view its transactions here.'}
                      </div>
                    </div>
                  </td>
                </tr>
              ) : (
                filtered.map((tx, idx) => {
                  const dateStr = tx.transaction_date
                    ? new Date(tx.transaction_date).toLocaleDateString('en-GB', {
                        day: '2-digit',
                        month: 'short',
                        year: 'numeric',
                      })
                    : '—'

                  return (
                    <tr key={tx.transaction_id || idx}>
                      <td className="mono-cell">{tx.source_row ?? idx + 1}</td>
                      <td className="mono-cell">{dateStr}</td>
                      <td>
                        <div style={{ fontWeight: 500 }}>{tx.description || '—'}</div>
                      </td>
                      <td className="debit-amount">
                        {tx.debit !== null && tx.debit > 0
                          ? tx.debit.toLocaleString('en-IN', { minimumFractionDigits: 2 })
                          : '—'}
                      </td>
                      <td className="credit-amount">
                        {tx.credit !== null && tx.credit > 0
                          ? tx.credit.toLocaleString('en-IN', { minimumFractionDigits: 2 })
                          : '—'}
                      </td>
                      <td className="balance-amount">
                        {tx.balance !== null && tx.balance !== undefined
                          ? `₹${tx.balance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                          : '—'}
                      </td>
                      <td className="mono-cell" style={{ textAlign: 'right', fontSize: '10.5px' }}>
                        {(tx.transaction_id || '').slice(0, 8)}…
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

import { useState, useEffect, useMemo } from 'react'
import { PageHero } from '../components/PageHero'
import { loadDocuments, getDocumentTransactions } from '../services/documents'
import type { DocumentListItem, TransactionRecord } from '../types/api'

interface TransactionsPageProps {
  initialDocumentId?: string
  onNavigate: (page: string) => void
  hero?: {
    line1: string
    line2: string
    kicker: string
    lede: string
    cue: string
  }
}

export function TransactionsPage({
  initialDocumentId,
  onNavigate,
  hero,
}: TransactionsPageProps) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([])
  const [selectedDocId, setSelectedDocId] = useState<string>('')
  const [transactions, setTransactions] = useState<TransactionRecord[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [filterType, setFilterType] = useState<'ALL' | 'DEBIT' | 'CREDIT'>('ALL')
  const [sortOrder, setSortOrder] = useState<'DATE_DESC' | 'DATE_ASC' | 'AMOUNT_DESC'>('DATE_DESC')

  // Load processed documents
  useEffect(() => {
    const list = loadDocuments()
    setDocuments(list)
    const processedList = list.filter((d) => d.status === 'PROCESSED')

    if (initialDocumentId && list.some((d) => d.document_id === initialDocumentId)) {
      setSelectedDocId(initialDocumentId)
    } else if (processedList.length > 0 && processedList[0]) {
      setSelectedDocId(processedList[0].document_id)
    }
  }, [initialDocumentId])

  // Fetch transactions when selected document changes
  useEffect(() => {
    if (!selectedDocId) {
      setTransactions([])
      return
    }

    setIsLoading(true)
    setError(null)

    getDocumentTransactions(selectedDocId)
      .then((res) => {
        setTransactions(res.transactions || [])
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Unable to load transactions.')
        setTransactions([])
      })
      .finally(() => {
        setIsLoading(false)
      })
  }, [selectedDocId])

  // Filter & sort transactions
  const filteredTransactions = useMemo(() => {
    let result = transactions.filter((tx) => {
      const q = search.toLowerCase()
      const descMatches = (tx.description || '').toLowerCase().includes(q)
      const dateMatches = (tx.transaction_date || '').toLowerCase().includes(q)
      const amountMatches = tx.amount !== undefined && tx.amount !== null && String(tx.amount).includes(q)
      const matchesSearch = descMatches || dateMatches || amountMatches

      if (!matchesSearch) return false

      if (filterType === 'DEBIT') {
        return (tx.debit !== null && tx.debit !== undefined && tx.debit > 0)
      }
      if (filterType === 'CREDIT') {
        return (tx.credit !== null && tx.credit !== undefined && tx.credit > 0)
      }
      return true
    })

    result = [...result].sort((a, b) => {
      if (sortOrder === 'DATE_DESC') {
        return new Date(b.transaction_date).getTime() - new Date(a.transaction_date).getTime()
      }
      if (sortOrder === 'DATE_ASC') {
        return new Date(a.transaction_date).getTime() - new Date(b.transaction_date).getTime()
      }
      if (sortOrder === 'AMOUNT_DESC') {
        const amtA = Math.abs(a.amount ?? (a.debit ?? a.credit ?? 0))
        const amtB = Math.abs(b.amount ?? (b.debit ?? b.credit ?? 0))
        return amtB - amtA
      }
      return 0
    })

    return result
  }, [transactions, search, filterType, sortOrder])

  // Aggregate metrics
  const totalDebits = useMemo(() => {
    return transactions.reduce((sum, tx) => sum + (tx.debit || 0), 0)
  }, [transactions])

  const totalCredits = useMemo(() => {
    return transactions.reduce((sum, tx) => sum + (tx.credit || 0), 0)
  }, [transactions])

  const netBalance = totalCredits - totalDebits

  // Export to CSV helper
  const handleExportCSV = () => {
    if (filteredTransactions.length === 0) return

    const headers = ['Transaction Date', 'Description', 'Amount', 'Debit', 'Credit', 'Balance', 'Source Row']
    const rows = filteredTransactions.map((tx) => [
      `"${tx.transaction_date || ''}"`,
      `"${(tx.description || '').replace(/"/g, '""')}"`,
      tx.amount ?? '',
      tx.debit ?? '',
      tx.credit ?? '',
      tx.balance ?? '',
      tx.source_row ?? '',
    ])

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `ledger_export_${selectedDocId || 'transactions'}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const selectedDoc = documents.find((d) => d.document_id === selectedDocId)

  return (
    <>
      <PageHero
        kicker={hero?.kicker ?? 'Valid rows extracted from processed documents.'}
        line1={hero?.line1 ?? 'Every beat'}
        line2={hero?.line2 ?? 'from the file.'}
        lede={hero?.lede ?? 'Browse, filter and export every transaction pulled from your files. Powered by GET /api/documents/{id}/transactions.'}
        cue={hero?.cue ?? 'CUE 03 · Ledger'}
      />

      {/* Document Selector & Controls */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="section-header">
          <div>
            <span className="mono cue-label">SOURCE SELECTION</span>
            <h2 className="section-title">Active Statement Document</h2>
          </div>
          {filteredTransactions.length > 0 && (
            <button
              type="button"
              className="action-btn action-btn-accent mono"
              onClick={handleExportCSV}
              title="Download CSV file of displayed transactions"
            >
              Export CSV ↓
            </button>
          )}
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

          {selectedDoc && selectedDoc.status !== 'PROCESSED' && (
            <div className="inspect-banner mono" style={{ margin: 0, padding: '8px 14px' }}>
              Document is not yet processed. Ingest transactions from the Documents page.
            </div>
          )}
        </div>
      </div>

      {/* Ledger Stats Bar */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="mono cue-label">01</span>
          </div>
          <div className="stat-value mono t-num">{transactions.length.toLocaleString()}</div>
          <div className="stat-label">Total Transactions</div>
          <div className="stat-sub">Parsed records</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="mono cue-label">02</span>
          </div>
          <div className="stat-value mono t-num" style={{ color: 'var(--accent-red)' }}>
            ₹{totalDebits.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
          </div>
          <div className="stat-label">Total Outflow (Debit)</div>
          <div className="stat-sub">Sum of debited entries</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="mono cue-label">03</span>
          </div>
          <div className="stat-value mono t-num" style={{ color: 'var(--parsec)' }}>
            ₹{totalCredits.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
          </div>
          <div className="stat-label">Total Inflow (Credit)</div>
          <div className="stat-sub">Sum of credited entries</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="mono cue-label">04</span>
          </div>
          <div
            className="stat-value mono t-num"
            style={{ color: netBalance >= 0 ? 'var(--parallax)' : 'var(--accent-yellow)' }}
          >
            ₹{netBalance.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
          </div>
          <div className="stat-label">Net Movement</div>
          <div className="stat-sub">{netBalance >= 0 ? 'Surplus / Positive' : 'Deficit / Outflow'}</div>
        </div>
      </div>

      {/* Main Ledger Table Card */}
      <div className="card">
        <div className="section-header">
          <div>
            <span className="mono cue-label">TRANSACTION LEDGER</span>
            <h2 className="section-title">Extracted Records</h2>
          </div>
          <span className="mono t-num table-counter">
            {filteredTransactions.length} of {transactions.length} RECORDS
          </span>
        </div>

        {error && (
          <div className="inspect-banner error mono" role="alert">
            {error}
          </div>
        )}

        {/* Filter Toolbar */}
        <div className="table-controls">
          <input
            type="search"
            className="table-search mono"
            placeholder="Search description, reference, amount, date…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          <div className="table-filter-pills">
            {(['ALL', 'DEBIT', 'CREDIT'] as const).map((ft) => (
              <button
                key={ft}
                type="button"
                className={`filter-pill mono${filterType === ft ? ' is-active' : ''}`}
                onClick={() => setFilterType(ft)}
              >
                {ft}
              </button>
            ))}

            <select
              className="filter-pill mono"
              style={{ cursor: 'pointer', background: 'var(--panel-2)' }}
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as typeof sortOrder)}
            >
              <option value="DATE_DESC">Date: Newest First</option>
              <option value="DATE_ASC">Date: Oldest First</option>
              <option value="AMOUNT_DESC">Amount: Highest First</option>
            </select>
          </div>
        </div>

        {isLoading ? (
          <div className="placeholder-state mono">
            <div className="placeholder-text">Reading ledger records…</div>
          </div>
        ) : !selectedDocId ? (
          <div className="placeholder-state">
            <div className="placeholder-text">No document selected</div>
            <div className="placeholder-sub">
              Upload a statement and process it to view its transactions.
            </div>
            <button
              type="button"
              className="action-btn action-btn-accent mono"
              style={{ marginTop: 12 }}
              onClick={() => onNavigate('documents')}
            >
              Go to Documents →
            </button>
          </div>
        ) : filteredTransactions.length === 0 ? (
          <div className="placeholder-state">
            <div className="placeholder-text">No matching transactions found</div>
            <div className="placeholder-sub">
              {transactions.length === 0
                ? 'This document has no extracted transactions yet. Make sure it is a CSV and click Process on the Documents screen.'
                : 'Try adjusting your search filters above.'}
            </div>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="data-table mono" aria-label="Transactions ledger">
              <thead>
                <tr>
                  <th style={{ width: 60 }}>Row</th>
                  <th>Date</th>
                  <th>Description</th>
                  <th className="t-num" style={{ textAlign: 'right' }}>Debit (₹)</th>
                  <th className="t-num" style={{ textAlign: 'right' }}>Credit (₹)</th>
                  <th className="t-num" style={{ textAlign: 'right' }}>Amount (₹)</th>
                  <th className="t-num" style={{ textAlign: 'right' }}>Balance (₹)</th>
                </tr>
              </thead>
              <tbody>
                {filteredTransactions.map((tx, idx) => {
                  const hasDebit = tx.debit !== null && tx.debit !== undefined && tx.debit > 0
                  const hasCredit = tx.credit !== null && tx.credit !== undefined && tx.credit > 0

                  return (
                    <tr key={idx}>
                      <td className="t-num" style={{ color: 'var(--muted)' }}>
                        {tx.source_row ?? idx + 1}
                      </td>
                      <td className="t-num" style={{ whiteSpace: 'nowrap' }}>
                        {tx.transaction_date ? tx.transaction_date.slice(0, 10) : '—'}
                      </td>
                      <td className="cell-truncate" style={{ maxWidth: 360 }} title={tx.description || ''}>
                        {tx.description || '—'}
                      </td>
                      <td className="t-num" style={{ textAlign: 'right', color: hasDebit ? 'var(--accent-red)' : 'var(--muted)' }}>
                        {hasDebit ? tx.debit!.toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '—'}
                      </td>
                      <td className="t-num" style={{ textAlign: 'right', color: hasCredit ? 'var(--parsec)' : 'var(--muted)' }}>
                        {hasCredit ? tx.credit!.toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '—'}
                      </td>
                      <td className="t-num" style={{ textAlign: 'right' }}>
                        {tx.amount !== null && tx.amount !== undefined
                          ? tx.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })
                          : '—'}
                      </td>
                      <td className="t-num" style={{ textAlign: 'right', color: 'var(--muted)' }}>
                        {tx.balance !== null && tx.balance !== undefined
                          ? tx.balance.toLocaleString('en-IN', { minimumFractionDigits: 2 })
                          : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}

import { useState } from 'react'
import type { DocumentMetadata } from '../types/api'
import { EyeIcon, TrashIcon, RefreshCwIcon } from './Icons'

interface DocumentsTableProps {
  documents: DocumentMetadata[]
  isLoading?: boolean
  onProcess?: (docId: string) => Promise<void>
  onDelete?: (docId: string) => Promise<void>
  onInspect?: (docId: string) => void
  onViewTransactions?: (docId: string) => void
}

export function DocumentsTable({
  documents,
  isLoading = false,
  onProcess,
  onDelete,
  onInspect,
  onViewTransactions,
}: DocumentsTableProps) {
  const [processingId, setProcessingId] = useState<string | null>(null)

  async function handleProcess(docId: string) {
    if (!onProcess) return
    setProcessingId(docId)
    try {
      await onProcess(docId)
    } finally {
      setProcessingId(null)
    }
  }

  function getStatusClass(status: string) {
    const s = status.toLowerCase()
    if (s === 'processed') return 'processed'
    if (s === 'failed') return 'failed'
    if (s === 'pending') return 'pending'
    return 'uploaded'
  }

  return (
    <div className="paper-panel">
      <div className="panel-header">
        <div className="panel-title-group">
          <h2 className="panel-title">Statement Registry</h2>
          <span className="panel-subtitle">
            {documents.length} financial statement{documents.length === 1 ? '' : 's'} cataloged
          </span>
        </div>
      </div>

      <div className="table-container">
        <table className="ledger-table">
          <thead>
            <tr>
              <th style={{ width: '40px' }}>#</th>
              <th>Document Filename</th>
              <th>Format</th>
              <th>Category</th>
              <th>Ingestion Time</th>
              <th>Status</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '32px' }}>
                  <span className="mono-cell">Querying document repository…</span>
                </td>
              </tr>
            ) : documents.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '36px' }}>
                  <div className="empty-state">
                    <div className="empty-state-title">No statements in registry</div>
                    <div className="empty-state-text">
                      Upload bank statements or accounting ledgers above to begin ingestion and normalization.
                    </div>
                  </div>
                </td>
              </tr>
            ) : (
              documents.map((doc, idx) => {
                const isProcessing = processingId === doc.id
                return (
                  <tr key={doc.id}>
                    <td className="mono-cell">{idx + 1}</td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{doc.filename}</div>
                      <div className="mono-cell" style={{ fontSize: '10.5px' }}>
                        ID: {doc.id}
                      </div>
                    </td>
                    <td>
                      <span className="format-pill">{doc.file_type}</span>
                    </td>
                    <td>
                      <span className="mono-cell">{doc.document_type || 'STATEMENT'}</span>
                    </td>
                    <td className="mono-cell">
                      {doc.uploaded_at
                        ? new Date(doc.uploaded_at).toLocaleDateString('en-GB', {
                            day: '2-digit',
                            month: 'short',
                            year: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })
                        : '—'}
                    </td>
                    <td>
                      <span className={`status-badge ${getStatusClass(doc.status)}`}>
                        {doc.status}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '6px' }}>
                        {doc.status !== 'PROCESSED' && onProcess && (
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleProcess(doc.id)}
                            disabled={isProcessing}
                            title="Extract transactions into MongoDB"
                          >
                            <RefreshCwIcon size={12} className={isProcessing ? 'spin' : ''} />
                            {isProcessing ? 'Processing…' : 'Process'}
                          </button>
                        )}

                        {doc.status === 'PROCESSED' && onViewTransactions && (
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => onViewTransactions(doc.id)}
                            title="View Extracted Transactions"
                          >
                            View Ledger
                          </button>
                        )}

                        {onInspect && (
                          <button
                            className="btn-icon"
                            onClick={() => onInspect(doc.id)}
                            title="Inspect Columns & Sample Rows"
                          >
                            <EyeIcon size={13} />
                          </button>
                        )}

                        {onDelete && (
                          <button
                            className="btn-icon"
                            onClick={() => onDelete(doc.id)}
                            title="Delete Statement and Stored Records"
                            style={{ color: 'var(--semantic-error)' }}
                          >
                            <TrashIcon size={13} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

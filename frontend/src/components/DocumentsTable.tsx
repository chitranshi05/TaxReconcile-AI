import { useState } from 'react'
import { processDocument, inspectDocument, deleteStoredDocument } from '../services/documents'
import type { DocumentInspectResponse, DocumentListItem, DocumentStatus } from '../types/api'
import { DocumentInspectModal } from './DocumentInspectModal'

export type { DocumentStatus }
export type DocumentRow = DocumentListItem

interface DocumentsTableProps {
  documents?: DocumentListItem[]
  onInspect?: (id: string) => void
  onProcess?: (id: string) => void
  onRefresh?: () => void
  onNavigatePage?: (page: string, documentId?: string) => void
}

function StatusBadge({ status }: { status: DocumentStatus }) {
  const map: Record<DocumentStatus, string> = {
    UPLOADED: 'is-uploaded',
    PROCESSED: 'is-processed',
    FAILED: 'is-failed',
    PENDING: 'is-pending',
  }
  return (
    <span className={`status-tag mono ${map[status] || 'is-uploaded'}`}>
      <span className="dot" />
      {status}
    </span>
  )
}

function SkeletonRow() {
  return (
    <tr>
      <td><div className="skeleton" style={{ height: 14, width: '70%' }} /></td>
      <td><div className="skeleton" style={{ height: 14, width: 44 }} /></td>
      <td><div className="skeleton" style={{ height: 18, width: 80 }} /></td>
      <td><div className="skeleton" style={{ height: 14, width: 40 }} /></td>
      <td><div className="skeleton" style={{ height: 14, width: 60 }} /></td>
      <td />
    </tr>
  )
}

export function DocumentsTable({
  documents,
  onProcess,
  onRefresh,
  onNavigatePage,
}: DocumentsTableProps) {
  const [processingId, setProcessingId] = useState<string | null>(null)
  const [inspectingId, setInspectingId] = useState<string | null>(null)
  const [inspectModalData, setInspectModalData] = useState<DocumentInspectResponse | null>(null)
  const [actionMessage, setActionMessage] = useState<{ text: string; isError?: boolean } | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'ALL' | DocumentStatus>('ALL')

  const filteredDocs = (documents || []).filter((doc) => {
    const matchesQuery = doc.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.file_type.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesStatus = statusFilter === 'ALL' || doc.status === statusFilter
    return matchesQuery && matchesStatus
  })

  const isEmpty = !documents || documents.length === 0

  const handleProcessClick = async (docId: string) => {
    setProcessingId(docId)
    setActionMessage(null)
    try {
      const result = await processDocument(docId)
      setActionMessage({
        text: `Processed successfully: ${result.saved_transactions} transactions extracted (${result.invalid_rows} invalid).`,
      })
      onProcess?.(docId)
      onRefresh?.()
    } catch (err) {
      setActionMessage({
        text: err instanceof Error ? err.message : 'Processing failed.',
        isError: true,
      })
    } finally {
      setProcessingId(null)
    }
  }

  const handleInspectClick = async (docId: string) => {
    setInspectingId(docId)
    setActionMessage(null)
    try {
      const result = await inspectDocument(docId)
      setInspectModalData(result)
    } catch (err) {
      setActionMessage({
        text: err instanceof Error ? err.message : 'Inspection failed.',
        isError: true,
      })
    } finally {
      setInspectingId(null)
    }
  }

  const handleDelete = (docId: string) => {
    deleteStoredDocument(docId)
    onRefresh?.()
  }

  return (
    <div className="card" id="documents-table-card">
      <div className="section-header">
        <div>
          <span className="mono cue-label">CUE 02 · ARCHIVE</span>
          <h2 className="section-title">Documents</h2>
        </div>
        {documents && documents.length > 0 && (
          <span className="mono t-num table-counter">
            {filteredDocs.length} / {documents.length} FILES
          </span>
        )}
      </div>

      {actionMessage && (
        <div
          role="status"
          className={`inspect-banner mono ${actionMessage.isError ? 'error' : 'success'}`}
        >
          {actionMessage.text}
        </div>
      )}

      {/* Filter / Search Bar */}
      {!isEmpty && (
        <div className="table-controls">
          <input
            type="search"
            className="table-search mono"
            placeholder="Filter files by name or type…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <div className="table-filter-pills">
            {(['ALL', 'UPLOADED', 'PROCESSED', 'FAILED'] as const).map((st) => (
              <button
                key={st}
                type="button"
                className={`filter-pill mono${statusFilter === st ? ' is-active' : ''}`}
                onClick={() => setStatusFilter(st)}
              >
                {st}
              </button>
            ))}
          </div>
        </div>
      )}

      {isEmpty ? (
        <div className="placeholder-state">
          <span className="coming-soon-kicker mono">STANDBY</span>
          <div className="placeholder-text">No documents yet</div>
          <div className="placeholder-sub">
            Upload a CSV, XLSX, PDF or JSON file above to begin tax ingestion and reconciliation.
          </div>
        </div>
      ) : filteredDocs.length === 0 ? (
        <div className="placeholder-state">
          <div className="placeholder-text">No matching documents</div>
          <div className="placeholder-sub">Try adjusting your search query or status filter.</div>
        </div>
      ) : (
        <div className="table-responsive">
          <table className="data-table" aria-label="Documents list">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Format</th>
                <th>Status</th>
                <th className="t-num">Transactions</th>
                <th>Timestamp</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents === undefined
                ? Array.from({ length: 4 }).map((_, i) => <SkeletonRow key={i} />)
                : filteredDocs.map((doc) => {
                    const isProcessing = processingId === doc.document_id
                    const isInspecting = inspectingId === doc.document_id

                    return (
                      <tr key={doc.document_id} id={`doc-row-${doc.document_id}`}>
                        <td className="primary">
                          <span className="file-badge mono">{doc.file_type}</span>
                          <span className="filename-text" title={doc.filename}>{doc.filename}</span>
                        </td>
                        <td className="mono">{doc.file_type}</td>
                        <td>
                          <StatusBadge status={doc.status} />
                        </td>
                        <td className="mono t-num">
                          {doc.transaction_count !== undefined
                            ? doc.transaction_count.toLocaleString()
                            : '—'}
                        </td>
                        <td className="mono t-num">
                          {doc.uploaded_at
                            ? new Date(doc.uploaded_at).toLocaleDateString()
                            : '—'}
                        </td>
                        <td>
                          <div className="row-actions" style={{ justifyContent: 'flex-end' }}>
                            <button
                              type="button"
                              className="action-btn mono"
                              disabled={isInspecting || isProcessing}
                              onClick={() => handleInspectClick(doc.document_id)}
                              title="Inspect columns and schema"
                            >
                              {isInspecting ? 'Inspecting…' : 'Inspect'}
                            </button>
                            {doc.status !== 'PROCESSED' && doc.file_type === 'CSV' && (
                              <button
                                type="button"
                                className="action-btn action-btn-accent mono"
                                disabled={isProcessing || isInspecting}
                                onClick={() => handleProcessClick(doc.document_id)}
                                title="Process CSV and extract transactions"
                              >
                                {isProcessing ? 'Processing…' : 'Process'}
                              </button>
                            )}
                            {doc.status === 'PROCESSED' && onNavigatePage && (
                              <>
                                <button
                                  type="button"
                                  className="action-btn mono"
                                  onClick={() => onNavigatePage('transactions', doc.document_id)}
                                  title="Browse transactions"
                                >
                                  Ledger
                                </button>
                                <button
                                  type="button"
                                  className="action-btn mono"
                                  onClick={() => onNavigatePage('anomalies', doc.document_id)}
                                  title="Check anomalies"
                                >
                                  Flags
                                </button>
                              </>
                            )}
                            <button
                              type="button"
                              className="action-btn action-btn-danger mono"
                              onClick={() => handleDelete(doc.document_id)}
                              title="Remove from workspace"
                            >
                              ✕
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
            </tbody>
          </table>
        </div>
      )}

      {inspectModalData && (
        <DocumentInspectModal
          data={inspectModalData}
          onClose={() => setInspectModalData(null)}
          onProcessed={() => {
            onRefresh?.()
          }}
        />
      )}
    </div>
  )
}

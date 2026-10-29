// DocumentsTable — lists uploaded documents with status badges and processing actions

import { useState } from 'react'
import { processDocument, inspectDocument } from '../services/documents'
import type { DocumentListItem, DocumentStatus } from '../types/api'

export type { DocumentStatus }

export type DocumentRow = DocumentListItem

interface DocumentsTableProps {
  documents?: DocumentListItem[]
  onInspect?: (id: string) => void
  onProcess?: (id: string) => void
  onRefresh?: () => void
}

const FILE_ICONS: Record<string, string> = {
  CSV: '📊',
  XLSX: '📗',
  XLS: '📗',
  PDF: '📕',
  JSON: '📦',
}

function StatusBadge({ status }: { status: DocumentStatus }) {
  const map: Record<DocumentStatus, string> = {
    UPLOADED: 'uploaded',
    PROCESSED: 'processed',
    FAILED: 'failed',
    PENDING: 'pending',
  }
  return (
    <span className={`badge ${map[status] || 'uploaded'}`}>
      <span className="badge-dot" />
      {status}
    </span>
  )
}

function SkeletonRow() {
  return (
    <tr>
      <td><div className="skeleton" style={{ height: 14, width: '70%', borderRadius: 4 }} /></td>
      <td><div className="skeleton" style={{ height: 14, width: 50, borderRadius: 4 }} /></td>
      <td><div className="skeleton" style={{ height: 18, width: 80, borderRadius: 10 }} /></td>
      <td><div className="skeleton" style={{ height: 14, width: 40, borderRadius: 4 }} /></td>
      <td><div className="skeleton" style={{ height: 14, width: 60, borderRadius: 4 }} /></td>
      <td />
    </tr>
  )
}

export function DocumentsTable({
  documents,
  onInspect,
  onProcess,
  onRefresh,
}: DocumentsTableProps) {
  const [processingId, setProcessingId] = useState<string | null>(null)
  const [inspectingId, setInspectingId] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<{ text: string; isError?: boolean } | null>(null)

  const isEmpty = !documents || documents.length === 0

  const handleProcessClick = async (docId: string) => {
    setProcessingId(docId)
    setActionMessage(null)
    try {
      const result = await processDocument(docId)
      setActionMessage({
        text: `Processed successfully: ${result.saved_transactions} transactions saved (${result.invalid_rows} invalid).`,
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
      const totalColumns = result.sheets.reduce((acc, s) => acc + s.columns.length, 0)
      setActionMessage({
        text: `Inspection complete for "${result.filename}": detected ${totalColumns} columns across ${result.sheets.length} sheet(s).`,
      })
      onInspect?.(docId)
    } catch (err) {
      setActionMessage({
        text: err instanceof Error ? err.message : 'Inspection failed.',
        isError: true,
      })
    } finally {
      setInspectingId(null)
    }
  }

  return (
    <div className="card" id="documents-table-card">
      <div className="section-header">
        <h2 className="section-title">
          <span className="section-title-icon">📄</span>
          Documents
        </h2>
        {documents && documents.length > 0 && (
          <span className="section-action" style={{ cursor: 'default' }}>
            {documents.length} file{documents.length === 1 ? '' : 's'} tracked
          </span>
        )}
      </div>

      {actionMessage && (
        <div
          role="status"
          style={{
            margin: '0 0 16px 0',
            padding: '10px 14px',
            borderRadius: 'var(--radius-sm)',
            fontSize: '13px',
            background: actionMessage.isError
              ? 'var(--accent-red-dim)'
              : 'var(--accent-green-dim)',
            color: actionMessage.isError
              ? 'var(--accent-red)'
              : 'var(--accent-green)',
            border: `1px solid ${actionMessage.isError ? 'var(--accent-red)' : 'var(--accent-green)'}`,
          }}
        >
          {actionMessage.text}
        </div>
      )}

      {isEmpty ? (
        <div className="placeholder-state">
          <div className="placeholder-icon">📁</div>
          <div className="placeholder-text">No documents yet</div>
          <div className="placeholder-sub">
            Upload a CSV, XLSX, PDF or JSON file above to begin tax ingestion and reconciliation.
          </div>
        </div>
      ) : (
        <table className="data-table" aria-label="Documents list">
          <thead>
            <tr>
              <th>Filename</th>
              <th>Type</th>
              <th>Status</th>
              <th>Transactions</th>
              <th>Uploaded</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {documents === undefined
              ? Array.from({ length: 4 }).map((_, i) => <SkeletonRow key={i} />)
              : documents.map((doc) => {
                const isProcessing = processingId === doc.document_id
                const isInspecting = inspectingId === doc.document_id

                return (
                  <tr key={doc.document_id} id={`doc-row-${doc.document_id}`}>
                    <td className="primary">
                      <span className="table-file-icon">
                        {FILE_ICONS[doc.file_type] ?? '📄'}
                      </span>
                      {doc.filename}
                    </td>
                    <td>{doc.file_type}</td>
                    <td>
                      <StatusBadge status={doc.status} />
                    </td>
                    <td>
                      {doc.transaction_count !== undefined
                        ? doc.transaction_count.toLocaleString()
                        : '—'}
                    </td>
                    <td>
                      {doc.uploaded_at
                        ? new Date(doc.uploaded_at).toLocaleDateString()
                        : '—'}
                    </td>
                    <td>
                      <div className="row-actions">
                        <button
                          type="button"
                          className="action-btn"
                          disabled={isInspecting || isProcessing}
                          onClick={() => handleInspectClick(doc.document_id)}
                          title="Inspect columns and schema"
                        >
                          {isInspecting ? 'Inspecting…' : 'Inspect'}
                        </button>
                        {doc.status !== 'PROCESSED' && doc.file_type === 'CSV' && (
                          <button
                            type="button"
                            className="action-btn"
                            disabled={isProcessing || isInspecting}
                            onClick={() => handleProcessClick(doc.document_id)}
                            style={{
                              color: 'var(--brand-end)',
                              borderColor: 'var(--border-brand)',
                            }}
                            title="Process CSV and extract transactions"
                          >
                            {isProcessing ? 'Processing…' : 'Process'}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
          </tbody>
        </table>
      )}
    </div>
  )
}

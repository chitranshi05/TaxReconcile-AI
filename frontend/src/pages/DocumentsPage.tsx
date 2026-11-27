import { useState, useEffect } from 'react'
import type { DocumentMetadata } from '../types/api'
import { listDocuments, processDocument, deleteDocument, inspectDocument } from '../services/documents'
import { DocumentsTable } from '../components/DocumentsTable'
import { UploadPanel } from '../components/UploadPanel'

interface DocumentsPageProps {
  onNavigate: (page: string) => void
  onSelectDocumentForTransactions?: (docId: string) => void
}

export function DocumentsPage({ onNavigate, onSelectDocumentForTransactions }: DocumentsPageProps) {
  const [documents, setDocuments] = useState<DocumentMetadata[]>([])
  const [loading, setLoading] = useState(true)
  const [inspectData, setInspectData] = useState<any | null>(null)
  const [statusMessage, setStatusMessage] = useState<string>('')

  async function refresh() {
    setLoading(true)
    try {
      const docs = await listDocuments()
      setDocuments(docs)
    } catch {
      // Backend may be offline or unauthenticated
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  async function handleProcess(docId: string) {
    try {
      const res = await processDocument(docId)
      setStatusMessage(`Extracted ${res.saved_transactions} transactions from document.`)
      await refresh()
    } catch (err: any) {
      alert(err.message || 'Processing failed')
    }
  }

  async function handleDelete(docId: string) {
    if (!window.confirm('Delete this statement and its extracted transactions?')) return
    try {
      await deleteDocument(docId)
      await refresh()
    } catch (err: any) {
      alert(err.message || 'Deletion failed')
    }
  }

  async function handleInspect(docId: string) {
    try {
      const data = await inspectDocument(docId)
      setInspectData(data)
    } catch (err: any) {
      alert(err.message || 'Inspection failed')
    }
  }

  function handleViewTransactions(docId: string) {
    onSelectDocumentForTransactions?.(docId)
    onNavigate('transactions')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="ledger-header">
        <div className="ledger-header-text">
          <h1>Statement Intake & Repository</h1>
          <p>Ingest, inspect column mappings, and process institutional financial files into the general ledger.</p>
        </div>
        <div className="ledger-header-actions">
          <button className="btn btn-secondary btn-sm" onClick={refresh}>
            Refresh Registry
          </button>
        </div>
      </div>

      {statusMessage && (
        <div
          style={{
            padding: '10px 14px',
            backgroundColor: 'var(--semantic-success-bg)',
            border: '1px solid var(--semantic-success-border)',
            color: 'var(--semantic-success)',
            borderRadius: 'var(--radius-sm)',
            fontSize: '12px',
          }}
        >
          {statusMessage}
        </div>
      )}

      {/* Upload Zone */}
      <UploadPanel onUploaded={() => refresh()} />

      {/* Documents Registry */}
      <DocumentsTable
        documents={documents}
        isLoading={loading}
        onProcess={handleProcess}
        onDelete={handleDelete}
        onInspect={handleInspect}
        onViewTransactions={handleViewTransactions}
      />

      {/* Column Inspection Modal / Drawer */}
      {inspectData && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(28, 27, 24, 0.45)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '24px',
          }}
          onClick={() => setInspectData(null)}
        >
          <div
            className="paper-panel"
            style={{ maxWidth: '780px', width: '100%', maxHeight: '85vh', overflowY: 'auto' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="panel-header">
              <div>
                <h3 className="panel-title">Statement Column Mapping & Sample Rows</h3>
                <span className="panel-subtitle">File: {inspectData.filename} ({inspectData.file_type})</span>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setInspectData(null)}>
                Close
              </button>
            </div>

            {inspectData.sheets?.map((sh: any) => (
              <div key={sh.sheet_name} style={{ marginBottom: '20px' }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 600, marginBottom: '8px' }}>
                  Sheet: {sh.sheet_name} ({sh.rows} rows detected)
                </div>

                <div style={{ marginBottom: '12px' }}>
                  <span className="kpi-label">Detected Column Mappings:</span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '4px' }}>
                    {Object.entries(sh.column_mapping || {}).map(([canon, orig]) => (
                      <span key={canon} className="format-pill">
                        <strong>{canon}:</strong> {String(orig)}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="table-container">
                  <table className="ledger-table">
                    <thead>
                      <tr>
                        {sh.columns?.map((c: string) => (
                          <th key={c}>{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sh.sample?.slice(0, 5).map((row: any, i: number) => (
                        <tr key={i}>
                          {sh.columns?.map((c: string) => (
                            <td key={c} className="mono-cell">
                              {String(row[c] ?? '—')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

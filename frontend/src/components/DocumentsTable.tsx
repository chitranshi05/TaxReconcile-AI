// DocumentsTable — lists uploaded documents with status badges
// Data will be fetched from GET /api/documents (endpoint TBD by backend team)
// Currently shows placeholder skeleton rows

export type DocumentStatus = 'UPLOADED' | 'PROCESSED' | 'FAILED' | 'PENDING'

export interface DocumentRow {
  document_id: string
  filename: string
  file_type: string
  status: DocumentStatus
  transaction_count?: number
  invalid_row_count?: number
  uploaded_at?: string
}

interface DocumentsTableProps {
  documents?: DocumentRow[]
  onInspect?: (id: string) => void
  onProcess?: (id: string) => void
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
    <span className={`badge ${map[status]}`}>
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

export function DocumentsTable({ documents, onInspect, onProcess }: DocumentsTableProps) {
  const isEmpty = !documents || documents.length === 0

  return (
    <div className="card" id="documents-table-card">
      <div className="section-header">
        <h2 className="section-title">
          <span className="section-title-icon">📄</span>
          Documents
        </h2>
        <button className="section-action" id="view-all-docs-btn">
          View all →
        </button>
      </div>

      {isEmpty ? (
        <div className="placeholder-state">
          <div className="placeholder-icon">📁</div>
          <div className="placeholder-text">No documents yet</div>
          <div className="placeholder-sub">
            Upload a CSV, XLSX, PDF or JSON file to get started with reconciliation.
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
              <th />
            </tr>
          </thead>
          <tbody>
            {documents === undefined
              ? Array.from({ length: 4 }).map((_, i) => <SkeletonRow key={i} />)
              : documents.map((doc) => (
                  <tr key={doc.document_id} id={`doc-row-${doc.document_id}`}>
                    <td className="primary">
                      <span className="table-file-icon">
                        {FILE_ICONS[doc.file_type] ?? '📄'}
                      </span>
                      {doc.filename}
                    </td>
                    <td>{doc.file_type}</td>
                    <td><StatusBadge status={doc.status} /></td>
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
                        {onInspect && (
                          <button
                            className="action-btn"
                            onClick={() => onInspect(doc.document_id)}
                          >
                            Inspect
                          </button>
                        )}
                        {onProcess && doc.status === 'UPLOADED' && doc.file_type === 'CSV' && (
                          <button
                            className="action-btn"
                            onClick={() => onProcess(doc.document_id)}
                          >
                            Process
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

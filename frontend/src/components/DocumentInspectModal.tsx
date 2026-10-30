import { useState } from 'react'
import type { DocumentInspectResponse, ProcessDocumentResponse } from '../types/api'
import { processDocument } from '../services/documents'

interface DocumentInspectModalProps {
  data: DocumentInspectResponse
  onClose: () => void
  onProcessed?: (result: ProcessDocumentResponse) => void
}

export function DocumentInspectModal({
  data,
  onClose,
  onProcessed,
}: DocumentInspectModalProps) {
  const [activeSheetIndex, setActiveSheetIndex] = useState(0)
  const [isProcessing, setIsProcessing] = useState(false)
  const [processError, setProcessError] = useState<string | null>(null)
  const [processSuccess, setProcessSuccess] = useState<string | null>(null)

  const sheet = data.sheets[activeSheetIndex] || data.sheets[0]

  const handleProcessNow = async () => {
    setIsProcessing(true)
    setProcessError(null)
    setProcessSuccess(null)
    try {
      const res = await processDocument(data.document_id)
      setProcessSuccess(`Extracted ${res.saved_transactions} transactions (${res.invalid_rows} invalid rows).`)
      onProcessed?.(res)
    } catch (err) {
      setProcessError(err instanceof Error ? err.message : 'Processing failed.')
    } finally {
      setIsProcessing(false)
    }
  }

  return (
    <div className="inspect-overlay" role="dialog" aria-modal="true" aria-label="Document inspection">
      <div className="inspect-backdrop" onClick={onClose} />
      <div className="inspect-drawer">
        <div className="inspect-head">
          <div>
            <span className="mono cue-label">CUE INSPECT · SCHEMA & MAPPING</span>
            <h2 className="inspect-title">{data.filename}</h2>
            <p className="inspect-sub mono">
              ID: {data.document_id} · TYPE: {data.file_type} · SHEETS: {data.sheets.length}
            </p>
          </div>
          <button type="button" className="menu-close mono" onClick={onClose}>
            Close
          </button>
        </div>

        {processError && (
          <div className="inspect-banner error mono" role="alert">
            {processError}
          </div>
        )}

        {processSuccess && (
          <div className="inspect-banner success mono" role="status">
            {processSuccess}
          </div>
        )}

        {data.sheets.length > 1 && (
          <div className="sheet-tabs" role="tablist">
            {data.sheets.map((s, idx) => (
              <button
                key={s.sheet_name || idx}
                type="button"
                className={`sheet-tab mono${activeSheetIndex === idx ? ' is-active' : ''}`}
                onClick={() => setActiveSheetIndex(idx)}
              >
                {s.sheet_name || `Sheet ${idx + 1}`}
              </button>
            ))}
          </div>
        )}

        <div className="inspect-body">
          {/* Column Mapping Section */}
          <section className="inspect-section">
            <div className="section-head-sm">
              <span className="mono cue-label">01 · COLUMN DETECTION</span>
              <span className="mono t-num">
                {Object.keys(sheet?.column_mapping || {}).length} Mapped / {sheet?.columns.length || 0} Total
              </span>
            </div>

            <div className="mapping-grid">
              {sheet?.column_mapping && Object.keys(sheet.column_mapping).length > 0 ? (
                Object.entries(sheet.column_mapping).map(([canonical, sourceCol]) => (
                  <div key={canonical} className="mapping-card">
                    <span className="mapping-canonical mono">{canonical.toUpperCase()}</span>
                    <span className="mapping-arrow">→</span>
                    <span className="mapping-source mono">{sourceCol || '—'}</span>
                  </div>
                ))
              ) : (
                <div className="empty-inline mono">No automatic column mappings resolved.</div>
              )}
            </div>

            <div className="columns-chip-row">
              <span className="mono chip-label">Detected columns:</span>
              {sheet?.columns.map((c) => (
                <span key={c} className="column-chip mono">
                  {c}
                </span>
              ))}
            </div>
          </section>

          {/* Validation Metrics */}
          {sheet?.validation && (
            <section className="inspect-section">
              <div className="section-head-sm">
                <span className="mono cue-label">02 · SAMPLE VALIDATION AUDIT</span>
                <span className={`status-pill mono ${sheet.validation.valid ? 'is-live' : 'is-dark'}`}>
                  {sheet.validation.valid ? 'VALID SAMPLE' : 'ISSUES DETECTED'}
                </span>
              </div>

              <div className="stats-grid inspect-stats">
                <div className="stat-card">
                  <div className="stat-value mono t-num">{sheet.validation.total_rows}</div>
                  <div className="stat-label">Sample Rows</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value mono t-num" style={{ color: 'var(--parsec)' }}>
                    {sheet.validation.valid_rows}
                  </div>
                  <div className="stat-label">Valid Rows</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value mono t-num" style={{ color: sheet.validation.invalid_rows ? 'var(--accent-red)' : 'var(--muted)' }}>
                    {sheet.validation.invalid_rows}
                  </div>
                  <div className="stat-label">Invalid Rows</div>
                </div>
              </div>

              {sheet.validation_note && (
                <p className="validation-note mono">{sheet.validation_note}</p>
              )}

              {sheet.validation.errors && sheet.validation.errors.length > 0 && (
                <div className="validation-errors-list">
                  <span className="mono error-head">Validation Errors ({sheet.validation.errors.length}):</span>
                  {sheet.validation.errors.slice(0, 5).map((err, i) => (
                    <div key={i} className="validation-error-item mono">
                      {err.row !== undefined && err.row !== null && <span>[Row {err.row}] </span>}
                      {err.field && <span>[{err.field}] </span>}
                      <span>{err.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* Sample Rows Table */}
          {sheet?.sample && sheet.sample.length > 0 && (
            <section className="inspect-section">
              <div className="section-head-sm">
                <span className="mono cue-label">03 · SAMPLE DATA PREVIEW</span>
                <span className="mono t-num">{sheet.sample.length} Rows</span>
              </div>

              <div className="table-responsive">
                <table className="data-table mono" aria-label="Sample rows">
                  <thead>
                    <tr>
                      <th style={{ width: 48 }}>#</th>
                      {sheet.columns.map((col) => (
                        <th key={col}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sheet.sample.map((row, rIdx) => (
                      <tr key={rIdx}>
                        <td className="t-num" style={{ color: 'var(--muted)' }}>
                          {rIdx + 1}
                        </td>
                        {sheet.columns.map((col) => (
                          <td key={col} className="cell-truncate">
                            {row[col] !== undefined && row[col] !== null ? String(row[col]) : '—'}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </div>

        <div className="inspect-footer">
          <button
            type="button"
            className="btn btn-secondary mono"
            onClick={onClose}
          >
            Close Inspector
          </button>
          {data.file_type === 'CSV' && (
            <button
              type="button"
              className="btn btn-primary mono"
              disabled={isProcessing}
              onClick={handleProcessNow}
            >
              {isProcessing ? 'Processing…' : 'Process File Now →'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

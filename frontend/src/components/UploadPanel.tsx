// UploadPanel — drag-and-drop file upload zone
// Wires to POST /api/documents/upload via the documents service

import { useState, useRef, type DragEvent } from 'react'
import { uploadDocument } from '../services/documents'

const ACCEPTED_TYPES = ['CSV', 'XLSX', 'XLS', 'PDF', 'JSON']

interface UploadPanelProps {
  /** Called after a successful upload with the returned document_id */
  onUploaded?: (documentId: string, filename: string) => void
}

type UploadState = 'idle' | 'dragging' | 'uploading' | 'success' | 'error'

export function UploadPanel({ onUploaded }: UploadPanelProps) {
  const [uploadState, setUploadState] = useState<UploadState>('idle')
  const [message, setMessage] = useState<string>('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setUploadState('dragging')
  }

  function handleDragLeave() {
    setUploadState('idle')
  }

  async function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (file) await submitFile(file)
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) await submitFile(file)
  }

  async function submitFile(file: File) {
    setUploadState('uploading')
    setMessage('')

    try {
      const result = await uploadDocument(file)
      setUploadState('success')
      setMessage(`"${result.filename}" uploaded — ID: ${result.document_id}`)
      onUploaded?.(result.document_id, result.filename)

      // Reset after 3 s
      setTimeout(() => {
        setUploadState('idle')
        setMessage('')
      }, 3000)
    } catch (err: unknown) {
      setUploadState('error')
      setMessage(
        err instanceof Error ? err.message : 'Upload failed. Please try again.',
      )
      setTimeout(() => setUploadState('idle'), 4000)
    }

    // Clear file input so the same file can be re-uploaded
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const isDragging = uploadState === 'dragging'
  const isUploading = uploadState === 'uploading'

  return (
    <div className="card" id="upload-panel">
      <div className="section-header">
        <h2 className="section-title">
          <span className="section-title-icon">📤</span>
          Upload Document
        </h2>
      </div>

      {/* Drop zone */}
      <div
        className={`upload-zone${isDragging ? ' drag-over' : ''}`}
        id="upload-dropzone"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="Drop file here or click to browse"
        onKeyDown={(e) =>
          e.key === 'Enter' && !isUploading && fileInputRef.current?.click()
        }
      >
        <input
          ref={fileInputRef}
          type="file"
          id="file-input"
          accept=".csv,.xlsx,.xls,.pdf,.json"
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />

        {isUploading ? (
          <>
            <div className="upload-icon">⏳</div>
            <div className="upload-title">Uploading…</div>
            <div className="upload-sub">Please wait while your file is being uploaded</div>
          </>
        ) : uploadState === 'success' ? (
          <>
            <div className="upload-icon">✅</div>
            <div className="upload-title">Upload Successful</div>
            <div className="upload-sub" style={{ color: 'var(--accent-green)' }}>{message}</div>
          </>
        ) : uploadState === 'error' ? (
          <>
            <div className="upload-icon">❌</div>
            <div className="upload-title">Upload Failed</div>
            <div className="upload-sub" style={{ color: 'var(--accent-red)' }}>{message}</div>
          </>
        ) : (
          <>
            <div className="upload-icon">📂</div>
            <div className="upload-title">Drop your file here</div>
            <div className="upload-sub">
              or click to browse — supports the following formats
            </div>
            <div className="upload-types">
              {ACCEPTED_TYPES.map((t) => (
                <span key={t} className="type-badge">{t}</span>
              ))}
            </div>
            <button className="upload-btn" type="button" onClick={(e) => e.stopPropagation()}>
              Browse Files
            </button>
          </>
        )}
      </div>
    </div>
  )
}

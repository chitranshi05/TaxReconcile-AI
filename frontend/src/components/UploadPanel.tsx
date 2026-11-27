import React, { useState, useRef, type DragEvent } from 'react'
import { UploadIcon } from './Icons'
import { uploadDocument } from '../services/documents'

const ACCEPTED_TYPES = ['CSV', 'XLSX', 'XLS', 'PDF', 'JSON']

interface UploadPanelProps {
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
      setMessage(`"${result.filename}" uploaded successfully. ID: ${result.document_id.slice(-8)}`)
      onUploaded?.(result.document_id, result.filename)

      setTimeout(() => {
        setUploadState('idle')
        setMessage('')
      }, 3500)
    } catch (err: unknown) {
      setUploadState('error')
      setMessage(err instanceof Error ? err.message : 'Upload failed. Please try again.')
      setTimeout(() => setUploadState('idle'), 4500)
    }

    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const isDragging = uploadState === 'dragging'
  const isUploading = uploadState === 'uploading'

  return (
    <div className="paper-panel">
      <div className="panel-header">
        <div className="panel-title-group">
          <h2 className="panel-title">Statement Intake</h2>
          <span className="panel-subtitle">Ingest bank accounts, books & ledger files</span>
        </div>
      </div>

      <div
        className={`dropzone-container${isDragging ? ' drag-over' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xls,.pdf,.json"
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />

        <div className="dropzone-icon">
          <UploadIcon size={32} />
        </div>

        {isUploading ? (
          <>
            <div className="dropzone-title">Encrypting & Uploading Statement…</div>
            <div className="dropzone-sub">Streamed to isolated disk storage with cryptographic hash</div>
          </>
        ) : uploadState === 'success' ? (
          <>
            <div className="dropzone-title" style={{ color: 'var(--semantic-success)' }}>
              Intake Verified
            </div>
            <div className="dropzone-sub" style={{ color: 'var(--semantic-success)' }}>{message}</div>
          </>
        ) : uploadState === 'error' ? (
          <>
            <div className="dropzone-title" style={{ color: 'var(--semantic-error)' }}>
              Upload Rejected
            </div>
            <div className="dropzone-sub" style={{ color: 'var(--semantic-error)' }}>{message}</div>
          </>
        ) : (
          <>
            <div className="dropzone-title">Select Financial Statement</div>
            <div className="dropzone-sub">Drop CSV, Excel, or JSON files here or browse local disk</div>
            <div className="dropzone-formats">
              {ACCEPTED_TYPES.map((t) => (
                <span key={t} className="format-pill">{t}</span>
              ))}
            </div>
            <div style={{ marginTop: '16px' }}>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={(e) => {
                  e.stopPropagation()
                  fileInputRef.current?.click()
                }}
              >
                Browse Files
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

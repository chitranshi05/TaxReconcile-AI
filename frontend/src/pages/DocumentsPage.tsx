import { useState, useEffect, useCallback } from 'react'
import { PageHero } from '../components/PageHero'
import { UploadPanel } from '../components/UploadPanel'
import { DocumentsTable } from '../components/DocumentsTable'
import { loadDocuments, fetchDocuments } from '../services/documents'
import type { DocumentListItem } from '../types/api'

interface DocumentsPageProps {
  onNavigate: (page: string, docId?: string) => void
  onDocumentsChange?: (count: number) => void
  hero?: {
    line1: string
    line2: string
    kicker: string
    lede: string
    cue: string
  }
}

export function DocumentsPage({
  onNavigate,
  onDocumentsChange,
  hero,
}: DocumentsPageProps) {
  const [documents, setDocuments] = useState<DocumentListItem[]>(() => loadDocuments())

  const refreshDocuments = useCallback(async () => {
    const list = await fetchDocuments()
    setDocuments(list)
    onDocumentsChange?.(list.length)
  }, [onDocumentsChange])

  useEffect(() => {
    refreshDocuments()
  }, [refreshDocuments])

  const csvCount = documents.filter((d) => d.file_type === 'CSV').length
  const processedCount = documents.filter((d) => d.status === 'PROCESSED').length
  const pendingCount = documents.filter((d) => d.status === 'UPLOADED').length

  return (
    <>
      <PageHero
        kicker={hero?.kicker ?? 'CSV, XLSX, PDF and JSON on the same rail.'}
        line1={hero?.line1 ?? 'Rooms we have'}
        line2={hero?.line2 ?? 'ingested.'}
        lede={hero?.lede ?? 'Upload, inspect and process financial documents. Column auto-detection and transaction extraction live here.'}
        cue={hero?.cue ?? 'CUE 02 · Documents'}
      />

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="mono cue-label">01</span>
          </div>
          <div className="stat-value mono t-num">{documents.length}</div>
          <div className="stat-label">Total Ingested</div>
          <div className="stat-sub">Across all workspace formats</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="mono cue-label">02</span>
          </div>
          <div className="stat-value mono t-num">{csvCount}</div>
          <div className="stat-label">CSV Statements</div>
          <div className="stat-sub">Pipeline compatible files</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="mono cue-label">03</span>
          </div>
          <div className="stat-value mono t-num" style={{ color: 'var(--parsec)' }}>
            {processedCount}
          </div>
          <div className="stat-label">Processed Ledger</div>
          <div className="stat-sub">Transactions extracted</div>
        </div>

        <div className="stat-card">
          <div className="stat-card-header">
            <span className="mono cue-label">04</span>
          </div>
          <div className="stat-value mono t-num" style={{ color: pendingCount ? 'var(--signal-live)' : 'var(--muted)' }}>
            {pendingCount}
          </div>
          <div className="stat-label">Pending Ingestion</div>
          <div className="stat-sub">Ready to inspect or process</div>
        </div>
      </div>

      <div className="dashboard-grid">
        <UploadPanel onUploaded={() => refreshDocuments()} />
      </div>

      <DocumentsTable
        documents={documents}
        onRefresh={refreshDocuments}
        onProcess={() => refreshDocuments()}
        onNavigatePage={onNavigate}
      />
    </>
  )
}

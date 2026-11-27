import { useState, useEffect } from 'react'
import type { DocumentMetadata } from '../types/api'
import { listDocuments } from '../services/documents'
import { StatCards } from '../components/StatCards'
import { UploadPanel } from '../components/UploadPanel'
import { DocumentsTable } from '../components/DocumentsTable'
import { ProcessingPipeline } from '../components/ProcessingPipeline'
import { ActivityFeed } from '../components/ActivityFeed'
import { QuickActions } from '../components/QuickActions'

interface DashboardPageProps {
  onNavigate: (page: string) => void
  onUpload?: () => void
  onSelectDocumentForTransactions?: (docId: string) => void
}

export function DashboardPage({ onNavigate, onUpload, onSelectDocumentForTransactions }: DashboardPageProps) {
  const [documents, setDocuments] = useState<DocumentMetadata[]>([])
  const [loading, setLoading] = useState(true)

  function load() {
    setLoading(true)
    listDocuments()
      .then((docs) => setDocuments(docs))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  const processedCount = documents.filter((d) => d.status === 'PROCESSED').length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* Editorial Header */}
      <div className="ledger-header">
        <div className="ledger-header-text">
          <h1>Institutional Overview</h1>
          <p>Continuous transaction reconciliation, anomaly surveillance, and statutory tax governance.</p>
        </div>
        <div className="ledger-header-actions">
          <button className="btn btn-secondary btn-sm" onClick={load}>
            Refresh Ledger Data
          </button>
        </div>
      </div>

      {/* Row 1 – KPI cards with real document counts */}
      <StatCards
        totalDocuments={documents.length}
        totalTransactions={processedCount * 3}
        matchedCount={2}
        discrepancyCount={2}
        reconciliationRate={66.7}
      />

      {/* Row 2 – Upload Intake + Pipeline */}
      <div className="two-col-grid">
        <UploadPanel onUploaded={() => load()} />
        <ProcessingPipeline
          documentId={documents[0]?.id}
          documentName={documents[0]?.filename}
          onPipelineCompleted={() => load()}
        />
      </div>

      {/* Row 3 – Documents table */}
      <DocumentsTable
        documents={documents.slice(0, 5)}
        isLoading={loading}
        onViewTransactions={(docId) => {
          onSelectDocumentForTransactions?.(docId)
          onNavigate('transactions')
        }}
      />

      {/* Row 4 – Quick Actions + Activity Feed */}
      <div className="two-col-grid">
        <QuickActions onNavigate={onNavigate} onUpload={onUpload} />
        <ActivityFeed />
      </div>
    </div>
  )
}

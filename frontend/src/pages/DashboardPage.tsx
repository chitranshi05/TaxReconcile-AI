// DashboardPage — main overview screen wired with live documents & statistics

import { useState, useEffect, useCallback } from 'react'
import { StatCards } from '../components/StatCards'
import { UploadPanel } from '../components/UploadPanel'
import { DocumentsTable } from '../components/DocumentsTable'
import { ProcessingPipeline } from '../components/ProcessingPipeline'
import { ActivityFeed } from '../components/ActivityFeed'
import { QuickActions } from '../components/QuickActions'
import { loadDocuments } from '../services/documents'
import type { DocumentListItem } from '../types/api'

interface DashboardPageProps {
  onNavigate: (page: string) => void
  onUpload?: () => void
  onDocumentsChange?: (count: number) => void
}

export function DashboardPage({
  onNavigate,
  onUpload,
  onDocumentsChange,
}: DashboardPageProps) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([])

  const refreshDocuments = useCallback(() => {
    const list = loadDocuments()
    setDocuments(list)
    onDocumentsChange?.(list.length)
  }, [onDocumentsChange])

  useEffect(() => {
    refreshDocuments()
  }, [refreshDocuments])

  // Derive metrics from current document collection
  const documentsCount = documents.length
  const transactionsCount = documents.reduce(
    (sum, doc) => sum + (doc.transaction_count || 0),
    0,
  )
  const invalidRowsCount = documents.reduce(
    (sum, doc) => sum + (doc.invalid_row_count || 0),
    0,
  )

  // Pipeline step calculation based on recent document state
  let currentStep: number | undefined = undefined
  const latestDoc = documents[0]
  if (latestDoc) {
    if (latestDoc.status === 'PROCESSED') {
      currentStep = 3 // Review Transactions
    } else if (latestDoc.status === 'UPLOADED') {
      currentStep = 1 // Inspect / Ready to process
    } else {
      currentStep = 2 // Processing
    }
  }

  const handleDocumentUploaded = () => {
    refreshDocuments()
  }

  return (
    <>
      {/* Row 1 – KPI cards with real metrics */}
      <StatCards
        documentsCount={documentsCount}
        transactionsCount={transactionsCount}
        invalidRowsCount={invalidRowsCount}
      />

      {/* Row 2 – Upload + Pipeline */}
      <div className="two-col">
        <UploadPanel onUploaded={handleDocumentUploaded} />
        <ProcessingPipeline currentStep={currentStep} />
      </div>

      {/* Row 3 – Documents table (full width) */}
      <DocumentsTable
        documents={documents}
        onRefresh={refreshDocuments}
        onProcess={() => refreshDocuments()}
      />

      {/* Row 4 – Quick Actions + Activity Feed */}
      <div className="two-col">
        <QuickActions onNavigate={onNavigate} onUpload={onUpload} />
        <ActivityFeed documents={documents} />
      </div>
    </>
  )
}

import { useState, useEffect, useCallback } from 'react'
import { StatCards } from '../components/StatCards'
import { UploadPanel } from '../components/UploadPanel'
import { DocumentsTable } from '../components/DocumentsTable'
import { ProcessingPipeline } from '../components/ProcessingPipeline'
import { ActivityFeed } from '../components/ActivityFeed'
import { QuickActions } from '../components/QuickActions'
import { PageHero } from '../components/PageHero'
import { loadDocuments, fetchDocuments } from '../services/documents'
import type { DocumentListItem } from '../types/api'

interface DashboardPageProps {
  onNavigate: (page: string, docId?: string) => void
  onUpload?: () => void
  onDocumentsChange?: (count: number) => void
  hero?: {
    line1: string
    line2: string
    kicker: string
    lede: string
    cue: string
  }
}

export function DashboardPage({
  onNavigate,
  onUpload,
  onDocumentsChange,
  hero,
}: DashboardPageProps) {
  const [documents, setDocuments] = useState<DocumentListItem[]>(() => loadDocuments())

  const refreshDocuments = useCallback(async () => {
    const list = await fetchDocuments()
    setDocuments(list)
    onDocumentsChange?.(list.length)
  }, [onDocumentsChange])

  useEffect(() => {
    refreshDocuments()
  }, [refreshDocuments])

  const documentsCount = documents.length
  const transactionsCount = documents.reduce(
    (sum, doc) => sum + (doc.transaction_count || 0),
    0,
  )
  const invalidRowsCount = documents.reduce(
    (sum, doc) => sum + (doc.invalid_row_count || 0),
    0,
  )

  let currentStep: number | undefined = undefined
  const latestDoc = documents[0]
  if (latestDoc) {
    if (latestDoc.status === 'PROCESSED') {
      currentStep = 3
    } else if (latestDoc.status === 'UPLOADED') {
      currentStep = 1
    } else {
      currentStep = 2
    }
  }

  const handleDocumentUploaded = () => {
    refreshDocuments()
  }

  return (
    <>
      <PageHero
        kicker={hero?.kicker ?? 'Statements in, transactions out. The room stays in sync.'}
        line1={hero?.line1 ?? 'The ledger runs'}
        line2={hero?.line2 ?? 'on our clock.'}
        lede={hero?.lede ?? 'We ingest files, map columns, extract the ledger and flag what does not belong — one clock for the whole workspace.'}
        cue={hero?.cue ?? 'CUE 01 · Selected work'}
      />

      <StatCards
        documentsCount={documentsCount}
        transactionsCount={transactionsCount}
        invalidRowsCount={invalidRowsCount}
      />

      <div className="two-col">
        <UploadPanel onUploaded={handleDocumentUploaded} />
        <ProcessingPipeline currentStep={currentStep} />
      </div>

      <DocumentsTable
        documents={documents}
        onRefresh={refreshDocuments}
        onProcess={() => refreshDocuments()}
        onNavigatePage={onNavigate}
      />

      <div className="two-col">
        <QuickActions onNavigate={onNavigate} onUpload={onUpload} />
        <ActivityFeed documents={documents} />
      </div>
    </>
  )
}

// DashboardPage — main overview screen

import { StatCards } from '../components/StatCards'
import { UploadPanel } from '../components/UploadPanel'
import { DocumentsTable } from '../components/DocumentsTable'
import { ProcessingPipeline } from '../components/ProcessingPipeline'
import { ActivityFeed } from '../components/ActivityFeed'
import { QuickActions } from '../components/QuickActions'

interface DashboardPageProps {
  onNavigate: (page: string) => void
  onUpload?: () => void
}

export function DashboardPage({ onNavigate, onUpload }: DashboardPageProps) {
  return (
    <>
      {/* Row 1 – KPI cards */}
      <StatCards />

      {/* Row 2 – Upload + Pipeline */}
      <div className="two-col">
        <UploadPanel />
        <ProcessingPipeline />
      </div>

      {/* Row 3 – Documents table (full width) */}
      <DocumentsTable documents={[]} />

      {/* Row 4 – Quick Actions + Activity Feed */}
      <div className="two-col">
        <QuickActions onNavigate={onNavigate} onUpload={onUpload} />
        <ActivityFeed />
      </div>
    </>
  )
}

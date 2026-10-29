import { useEffect, useState } from 'react'
import './App.css'

import { Sidebar } from './components/Sidebar'
import { TopBar } from './components/TopBar'
import { DashboardPage } from './pages/DashboardPage'
import { PlaceholderPage } from './pages/PlaceholderPage'

import { getHealth } from './services/backend'
import type { HealthResponse } from './types/api'

// ─── Page config ──────────────────────────────────────────────────
type PageId =
  | 'dashboard'
  | 'documents'
  | 'transactions'
  | 'reconciliation'
  | 'anomalies'
  | 'reports'
  | 'settings'

const PAGE_META: Record<PageId, { title: string; subtitle: string }> = {
  dashboard: {
    title: 'Dashboard',
    subtitle: 'Overview of your tax reconciliation workspace',
  },
  documents: {
    title: 'Documents',
    subtitle: 'Manage uploaded files — inspect, process, and track status',
  },
  transactions: {
    title: 'Transactions',
    subtitle: 'Browse and filter extracted transaction records',
  },
  reconciliation: {
    title: 'Reconciliation',
    subtitle: 'Match and reconcile transactions across sources',
  },
  anomalies: {
    title: 'Anomaly Detection',
    subtitle: 'AI-flagged anomalies and irregularities',
  },
  reports: {
    title: 'Reports',
    subtitle: 'Export reconciliation reports and audit trails',
  },
  settings: {
    title: 'Settings',
    subtitle: 'Account, API configuration, and preferences',
  },
}

// ─── App ──────────────────────────────────────────────────────────
function App() {
  const [activePage, setActivePage] = useState<PageId>('dashboard')
  const [health, setHealth] = useState<HealthResponse['status'] | 'loading'>('loading')

  // Poll backend health on mount
  useEffect(() => {
    getHealth()
      .then((res) => setHealth(res.status))
      .catch(() => setHealth('unhealthy'))
  }, [])

  const { title, subtitle } = PAGE_META[activePage]

  function renderPage() {
    switch (activePage) {
      case 'dashboard':
        return (
          <DashboardPage
            onNavigate={(p) => setActivePage(p as PageId)}
            onUpload={() => setActivePage('documents')}
          />
        )
      case 'documents':
        return (
          <PlaceholderPage
            icon="📄"
            title="Documents Manager"
            description="Upload, inspect, and process your financial documents. CSV processing with column auto-detection and transaction extraction will be available here."
          />
        )
      case 'transactions':
        return (
          <PlaceholderPage
            icon="💳"
            title="Transactions"
            description="Browse, filter, and export every transaction extracted from your processed documents. Powered by GET /api/documents/{id}/transactions."
          />
        )
      case 'reconciliation':
        return (
          <PlaceholderPage
            icon="🔄"
            title="Reconciliation Engine"
            description="Automatically match transactions across multiple sources and flag discrepancies for review."
          />
        )
      case 'anomalies':
        return (
          <PlaceholderPage
            icon="⚠️"
            title="Anomaly Detection"
            description="AI-powered detection of irregular transactions, duplicate entries, and statistical outliers."
          />
        )
      case 'reports':
        return (
          <PlaceholderPage
            icon="📊"
            title="Reports"
            description="Generate and export reconciliation summaries, audit trails, and tax-ready reports."
          />
        )
      case 'settings':
        return (
          <PlaceholderPage
            icon="⚙️"
            title="Settings"
            description="Configure your account, manage API credentials, and set notification preferences."
          />
        )
    }
  }

  return (
    <div className="app-shell">
      <Sidebar activePage={activePage} onNavigate={(p) => setActivePage(p as PageId)} />

      <TopBar
        title={title}
        subtitle={subtitle}
        health={health}
        onUpload={() => setActivePage('documents')}
      />

      <main className="main-content" id="main-content" role="main">
        {renderPage()}
      </main>
    </div>
  )
}

export default App

import { useEffect, useState } from 'react'
import './App.css'

import { Sidebar } from './components/Sidebar'
import { TopBar } from './components/TopBar'
import { Grain } from './components/Grain'
import { Cursor } from './components/Cursor'
import { DashboardPage } from './pages/DashboardPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { TransactionsPage } from './pages/TransactionsPage'
import { ReconciliationPage } from './pages/ReconciliationPage'
import { AnomaliesPage } from './pages/AnomaliesPage'
import { ReportsPage } from './pages/ReportsPage'
import { SettingsPage } from './pages/SettingsPage'
import { LoginPage } from './pages/LoginPage'

import { getHealth } from './services/backend'
import { getMe, logout, isAuthenticated } from './services/auth'
import { loadDocuments } from './services/documents'
import type { HealthResponse, UserResponse } from './types/api'

type PageId =
  | 'dashboard'
  | 'documents'
  | 'transactions'
  | 'reconciliation'
  | 'anomalies'
  | 'reports'
  | 'settings'

const PAGE_META: Record<
  PageId,
  { title: string; subtitle: string; line1: string; line2: string; kicker: string; lede: string; cue: string }
> = {
  dashboard: {
    title: 'Dashboard',
    subtitle: 'Overview of your tax reconciliation workspace',
    line1: 'The ledger runs',
    line2: 'on our clock.',
    kicker: 'Statements in, transactions out. The room stays in sync.',
    lede: 'We ingest files, map columns, extract the ledger and flag what does not belong — one clock for the whole workspace.',
    cue: 'CUE 01 · Selected work',
  },
  documents: {
    title: 'Documents',
    subtitle: 'Manage uploaded files — inspect, process, and track status',
    line1: 'Rooms we have',
    line2: 'ingested.',
    kicker: 'CSV, XLSX, PDF and JSON on the same rail.',
    lede: 'Upload, inspect and process financial documents. Column auto-detection and transaction extraction live here.',
    cue: 'CUE 02 · Documents',
  },
  transactions: {
    title: 'Transactions',
    subtitle: 'Browse and filter extracted transaction records',
    line1: 'Every beat',
    line2: 'from the file.',
    kicker: 'Valid rows extracted from processed documents.',
    lede: 'Browse, filter and export every transaction pulled from your files. Powered by GET /api/documents/{id}/transactions.',
    cue: 'CUE 03 · Ledger',
  },
  reconciliation: {
    title: 'Reconciliation',
    subtitle: 'Match and reconcile transactions across sources',
    line1: 'Two sources.',
    line2: 'One clock.',
    kicker: 'Match across banks, books and returns.',
    lede: 'Automatically match transactions across sources and surface discrepancies for review.',
    cue: 'CUE 04 · Match',
  },
  anomalies: {
    title: 'Anomaly Detection',
    subtitle: 'AI-flagged anomalies and irregularities',
    line1: 'Flags in',
    line2: 'the mix.',
    kicker: 'Irregulars, duplicates, statistical outliers.',
    lede: 'AI-powered detection of irregular transactions, duplicate entries and statistical outliers.',
    cue: 'CUE 05 · Flags',
  },
  reports: {
    title: 'Reports',
    subtitle: 'Export reconciliation reports and audit trails',
    line1: 'The show',
    line2: 'on paper.',
    kicker: 'Summaries, audit trails, tax-ready exports.',
    lede: 'Generate and export reconciliation summaries, audit trails and tax-ready reports.',
    cue: 'CUE 06 · Reports',
  },
  settings: {
    title: 'Settings',
    subtitle: 'Account, API configuration, and preferences',
    line1: 'The room',
    line2: 'and the desk.',
    kicker: 'Account, credentials, notifications.',
    lede: 'Configure your account, manage API credentials and set notification preferences.',
    cue: 'CUE 07 · Settings',
  },
}

function App() {
  const [user, setUser] = useState<UserResponse | null>(null)
  const [isAuthLoading, setIsAuthLoading] = useState(true)
  const [activePage, setActivePage] = useState<PageId>('dashboard')
  const [activeDocumentId, setActiveDocumentId] = useState<string | undefined>(undefined)
  const [health, setHealth] = useState<HealthResponse['status'] | 'loading'>('loading')
  const [documentsCount, setDocumentsCount] = useState<number>(() => loadDocuments().length)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    if (!isAuthenticated()) {
      setIsAuthLoading(false)
      return
    }

    getMe()
      .then((userData) => {
        setUser(userData)
      })
      .catch(() => {
        logout()
        setUser(null)
      })
      .finally(() => {
        setIsAuthLoading(false)
      })
  }, [])

  useEffect(() => {
    getHealth()
      .then((res) => setHealth(res.status))
      .catch(() => setHealth('unhealthy'))
  }, [])

  const handleAuthSuccess = (authenticatedUser: UserResponse) => {
    setUser(authenticatedUser)
  }

  const handleLogout = () => {
    logout()
    setUser(null)
    setMenuOpen(false)
  }

  const handleNavigate = (page: string, docId?: string) => {
    if (docId) {
      setActiveDocumentId(docId)
    }
    setActivePage(page as PageId)
    setMenuOpen(false)
  }

  if (isAuthLoading) {
    return (
      <>
        <Grain />
        <div className="auth-loading-screen">
          <div className="auth-loading-content">
            <p className="mono">CONNECTING TO ROOM…</p>
          </div>
        </div>
      </>
    )
  }

  if (!user) {
    return (
      <>
        <Grain />
        <Cursor />
        <LoginPage onSuccess={handleAuthSuccess} />
      </>
    )
  }

  const meta = PAGE_META[activePage]

  function renderPage() {
    switch (activePage) {
      case 'dashboard':
        return (
          <DashboardPage
            onNavigate={handleNavigate}
            onUpload={() => setActivePage('documents')}
            onDocumentsChange={(count) => setDocumentsCount(count)}
            hero={meta}
          />
        )
      case 'documents':
        return (
          <DocumentsPage
            onNavigate={handleNavigate}
            onDocumentsChange={(count) => setDocumentsCount(count)}
            hero={meta}
          />
        )
      case 'transactions':
        return (
          <TransactionsPage
            initialDocumentId={activeDocumentId}
            onNavigate={handleNavigate}
            hero={meta}
          />
        )
      case 'reconciliation':
        return (
          <ReconciliationPage
            onNavigate={handleNavigate}
            hero={meta}
          />
        )
      case 'anomalies':
        return (
          <AnomaliesPage
            initialDocumentId={activeDocumentId}
            onNavigate={handleNavigate}
            hero={meta}
          />
        )
      case 'reports':
        return (
          <ReportsPage
            onNavigate={handleNavigate}
            hero={meta}
          />
        )
      case 'settings':
        return (
          <SettingsPage
            user={user}
            health={health}
            onLogout={handleLogout}
            hero={meta}
          />
        )
    }
  }

  return (
    <div className="app-shell">
      <Grain />
      <Cursor />
      <TopBar
        title={meta.title}
        subtitle={meta.subtitle}
        health={health}
        onUpload={() => setActivePage('documents')}
        activePage={activePage}
        onNavigate={handleNavigate}
        onMenu={() => setMenuOpen(true)}
        menuOpen={menuOpen}
      />
      <Sidebar
        activePage={activePage}
        onNavigate={handleNavigate}
        user={user}
        onLogout={handleLogout}
        documentsCount={documentsCount}
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
      />

      <main className="main-content" id="main-content" role="main" key={activePage}>
        {renderPage()}
      </main>
    </div>
  )
}

export default App

import { useEffect, useState } from 'react'
import './App.css'

import { Sidebar } from './components/Sidebar'
import { TopBar } from './components/TopBar'
import { AuthModal } from './components/AuthModal'

import { DashboardPage } from './pages/DashboardPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { TransactionsPage } from './pages/TransactionsPage'
import { ReconciliationPage } from './pages/ReconciliationPage'
import { AnomaliesPage } from './pages/AnomaliesPage'
import { ReportsPage } from './pages/ReportsPage'

import { getHealth } from './services/backend'
import { getCurrentUser, type AuthUser } from './services/auth'
import type { HealthResponse } from './types/api'

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
    title: 'Executive Dashboard',
    subtitle: 'Institutional overview of multi-source reconciliations',
  },
  documents: {
    title: 'Statement Intake Registry',
    subtitle: 'Catalog, inspect column mapping, and normalize financial files',
  },
  transactions: {
    title: 'Financial General Ledger',
    subtitle: 'Normalized tabular transaction journals with debit & credit precision',
  },
  reconciliation: {
    title: 'Multi-Source Reconciliation',
    subtitle: 'Cross-match external bank statements against accounting books',
  },
  anomalies: {
    title: 'Statutory Tax & Anomaly Surveillance',
    subtitle: 'IQR outlier detection and Indian Income Tax compliance validation',
  },
  reports: {
    title: 'Archival Reports & Exports',
    subtitle: 'Audited Excel (.xlsx) workbooks and formal PDF statements',
  },
  settings: {
    title: 'System & Institutional Settings',
    subtitle: 'Cryptographic credentials, MongoDB indexes, and environment configuration',
  },
}

function App() {
  const [activePage, setActivePage] = useState<PageId>('dashboard')
  const [health, setHealth] = useState<HealthResponse['status'] | 'loading'>('loading')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isAuthOpen, setIsAuthOpen] = useState(false)
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null)
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    return (localStorage.getItem('theme') as 'light' | 'dark') || 'light'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  function toggleTheme() {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'))
  }

  function checkHealth() {
    setHealth('loading')
    getHealth()
      .then((res) => setHealth(res.status))
      .catch(() => setHealth('unhealthy'))
  }

  useEffect(() => {
    checkHealth()
    getCurrentUser()
      .then((u) => setUser(u))
      .catch(() => {})
  }, [])

  const { title, subtitle } = PAGE_META[activePage]

  function renderPage() {
    switch (activePage) {
      case 'dashboard':
        return (
          <DashboardPage
            onNavigate={(p) => setActivePage(p as PageId)}
            onUpload={() => setActivePage('documents')}
            onSelectDocumentForTransactions={(id) => setSelectedDocId(id)}
          />
        )
      case 'documents':
        return (
          <DocumentsPage
            onNavigate={(p) => setActivePage(p as PageId)}
            onSelectDocumentForTransactions={(id) => setSelectedDocId(id)}
          />
        )
      case 'transactions':
        return <TransactionsPage initialDocumentId={selectedDocId} />
      case 'reconciliation':
        return <ReconciliationPage />
      case 'anomalies':
        return <AnomaliesPage />
      case 'reports':
        return <ReportsPage />
      case 'settings':
        return (
          <div className="paper-panel">
            <div className="panel-header">
              <div className="panel-title-group">
                <h2 className="panel-title">Institutional Ledger Settings</h2>
                <span className="panel-subtitle">Current session & connected architecture</span>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ padding: '14px', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-sm)' }}>
                <div className="kpi-label">Active Operator</div>
                <div style={{ fontSize: '14px', fontWeight: 600 }}>{user ? user.name : 'Unauthenticated Guest'}</div>
                <div className="mono-cell" style={{ fontSize: '12px' }}>{user ? `${user.email} (${user.role})` : 'Running in local development mode'}</div>
              </div>

              <div style={{ padding: '14px', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-sm)' }}>
                <div className="kpi-label">Daemon Endpoints</div>
                <div style={{ fontSize: '13px' }}>Backend: <code>http://localhost:8000</code></div>
                <div style={{ fontSize: '13px' }}>Database: <code>mongodb://localhost:27017</code> (Database: <code>tax_reconcile_ai</code>)</div>
                <div style={{ fontSize: '13px' }}>Statutory Rules: <code>Income Tax Act (India) — FY 2023-24, 2024-25, 2025-26</code></div>
              </div>

              <div>
                <button className="btn btn-primary" onClick={() => setIsAuthOpen(true)}>
                  {user ? 'Switch / Re-authenticate Account' : 'Sign In with Auditor Credentials'}
                </button>
              </div>
            </div>
          </div>
        )
      default:
        return null
    }
  }

  return (
    <div className="app-shell">
      <Sidebar
        activePage={activePage}
        onNavigate={(p) => setActivePage(p as PageId)}
        userName={user?.name || 'Auditor'}
        userRole={user?.role || 'LOCAL'}
      />

      <TopBar
        pageTitle={title}
        pageSubtitle={subtitle}
        health={health}
        onRefreshHealth={checkHealth}
        onOpenAuth={() => setIsAuthOpen(true)}
        isAuthenticated={!!user}
        theme={theme}
        onToggleTheme={toggleTheme}
      />

      <main className="main-content">
        <div className="content-container">{renderPage()}</div>
      </main>

      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        onSuccess={(u) => setUser(u)}
      />
    </div>
  )
}

export default App

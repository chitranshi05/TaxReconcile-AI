import { useState } from 'react'
import { PageHero } from '../components/PageHero'
import { ThemeSwitcher } from '../components/ThemeSwitcher'
import { loadDocuments } from '../services/documents'
import type { UserResponse, HealthResponse } from '../types/api'

interface SettingsPageProps {
  user: UserResponse | null
  health: HealthResponse['status'] | 'loading'
  onLogout: () => void
  hero?: {
    line1: string
    line2: string
    kicker: string
    lede: string
    cue: string
  }
}

export function SettingsPage({
  user,
  health,
  onLogout,
  hero,
}: SettingsPageProps) {
  const [clearedNotice, setClearedNotice] = useState<string | null>(null)
  const docsCount = loadDocuments().length

  const handleClearLocalData = () => {
    localStorage.removeItem('tax_reconcile_documents')
    setClearedNotice('Workspace document cache cleared. Refreshing in 1s…')
    setTimeout(() => {
      window.location.reload()
    }, 1000)
  }

  return (
    <>
      <PageHero
        kicker={hero?.kicker ?? 'Account, credentials, notifications.'}
        line1={hero?.line1 ?? 'The room'}
        line2={hero?.line2 ?? 'and the desk.'}
        lede={hero?.lede ?? 'Configure your account, manage API credentials and set notification preferences.'}
        cue={hero?.cue ?? 'CUE 07 · Settings'}
      />

      {clearedNotice && (
        <div className="inspect-banner success mono" role="status" style={{ marginBottom: 24 }}>
          {clearedNotice}
        </div>
      )}

      {/* Account Profile Card */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="section-header">
          <div>
            <span className="mono cue-label">USER PROFILE</span>
            <h2 className="section-title">Authenticated Operator</h2>
          </div>
          <span className="status-tag mono is-processed">ON AIR</span>
        </div>

        <div className="reconciliation-setup-grid">
          <div className="stat-card">
            <span className="mono cue-label">OPERATOR NAME</span>
            <div className="stat-value" style={{ fontSize: '1.25rem', marginTop: 4 }}>
              {user?.name || 'Operator'}
            </div>
            <div className="stat-sub mono">Workspace principal</div>
          </div>

          <div className="stat-card">
            <span className="mono cue-label">REGISTERED EMAIL</span>
            <div className="stat-value mono" style={{ fontSize: '1.1rem', marginTop: 4 }}>
              {user?.email || '—'}
            </div>
            <div className="stat-sub mono">Identity verification</div>
          </div>

          <div className="stat-card">
            <span className="mono cue-label">ROLE PRIVILEGE</span>
            <div className="stat-value mono" style={{ fontSize: '1.25rem', marginTop: 4, color: 'var(--parallax)' }}>
              {user?.role || 'USER'}
            </div>
            <div className="stat-sub mono">{user?.role === 'ADMIN' ? 'Full administrative access' : 'Standard workspace user'}</div>
          </div>

          <div className="stat-card">
            <span className="mono cue-label">USER ID</span>
            <div className="stat-value mono" style={{ fontSize: '0.9rem', marginTop: 8, wordBreak: 'break-all' }}>
              {user?.id || '—'}
            </div>
            <div className="stat-sub mono">Database record key</div>
          </div>
        </div>
      </div>

      {/* Platform & System Architecture Card */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="section-header">
          <div>
            <span className="mono cue-label">ENGINE & INFRASTRUCTURE</span>
            <h2 className="section-title">Runtime & Connectivity</h2>
          </div>
          <span className={`status-tag mono ${health === 'healthy' ? 'is-processed' : 'is-failed'}`}>
            {health === 'healthy' ? 'CONNECTED' : 'DISCONNECTED'}
          </span>
        </div>

        <div className="reconciliation-setup-grid">
          <div className="stat-card">
            <span className="mono cue-label">API BASE URL</span>
            <div className="stat-value mono" style={{ fontSize: '1rem', marginTop: 6 }}>
              http://127.0.0.1:8000
            </div>
            <div className="stat-sub mono">FastAPI local proxy</div>
          </div>

          <div className="stat-card">
            <span className="mono cue-label">DATABASE CLOCK</span>
            <div className="stat-value mono" style={{ fontSize: '1rem', marginTop: 6, color: health === 'healthy' ? 'var(--parsec)' : 'var(--accent-red)' }}>
              {health === 'healthy' ? 'MongoDB Online' : 'Check local mongod'}
            </div>
            <div className="stat-sub mono">Port 27017 status</div>
          </div>

          <div className="stat-card">
            <span className="mono cue-label">THEME MATRIX</span>
            <div style={{ marginTop: 8 }}>
              <ThemeSwitcher />
            </div>
          </div>

          <div className="stat-card">
            <span className="mono cue-label">WORKSPACE CACHE</span>
            <div className="stat-value mono t-num" style={{ fontSize: '1.2rem', marginTop: 4 }}>
              {docsCount} Files
            </div>
            <div className="stat-sub mono">Local document cache</div>
          </div>
        </div>
      </div>

      {/* Data Management & Session Controls */}
      <div className="card">
        <div className="section-header">
          <div>
            <span className="mono cue-label">SESSION CONTROLS</span>
            <h2 className="section-title">Workspace Actions</h2>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center' }}>
          <button
            type="button"
            className="btn btn-secondary mono"
            onClick={handleClearLocalData}
          >
            Clear Document Cache
          </button>

          <button
            type="button"
            className="btn btn-primary mono"
            style={{ background: 'var(--accent-red)' }}
            onClick={onLogout}
          >
            Sign Out of Workspace →
          </button>
        </div>
      </div>
    </>
  )
}

import { RefreshCwIcon, SunIcon, MoonIcon } from './Icons'
import type { HealthResponse } from '../types/api'

interface TopBarProps {
  pageTitle: string
  pageSubtitle?: string
  health: HealthResponse['status'] | 'loading'
  onRefreshHealth?: () => void
  onOpenAuth?: () => void
  isAuthenticated?: boolean
  theme?: 'light' | 'dark'
  onToggleTheme?: () => void
}

export function TopBar({
  pageTitle,
  pageSubtitle,
  health,
  onRefreshHealth,
  onOpenAuth,
  isAuthenticated = false,
  theme = 'light',
  onToggleTheme,
}: TopBarProps) {
  return (
    <header className="topbar">
      <div className="topbar-context">
        <h2 className="topbar-page-title">{pageTitle}</h2>
        {pageSubtitle && <span className="topbar-page-sub">— {pageSubtitle}</span>}
      </div>

      <div className="topbar-actions">
        {onToggleTheme && (
          <button
            className="topbar-btn theme-toggle-btn"
            onClick={onToggleTheme}
            title={theme === 'light' ? 'Switch to Midnight Crème Dark' : 'Switch to Warm Crème Light'}
            aria-label="Toggle theme"
          >
            {theme === 'light' ? (
              <>
                <MoonIcon size={14} />
                <span>Midnight</span>
              </>
            ) : (
              <>
                <SunIcon size={14} />
                <span>Crème</span>
              </>
            )}
          </button>
        )}

        <div className="system-status-indicator" title="Connected to local FastAPI + MongoDB daemon">
          <span className={`status-dot ${health === 'healthy' ? '' : 'unhealthy'}`} />
          <span>
            {health === 'healthy'
              ? 'API Online · 8000'
              : health === 'loading'
                ? 'Connecting…'
                : 'API Offline'}
          </span>
          {onRefreshHealth && (
            <button
              onClick={onRefreshHealth}
              className="btn-icon"
              title="Refresh connection"
              style={{ marginLeft: 4, padding: 2, border: 'none' }}
            >
              <RefreshCwIcon size={12} />
            </button>
          )}
        </div>

        <button className="topbar-btn" onClick={onOpenAuth}>
          {isAuthenticated ? 'Session Active' : 'Sign In / Register'}
        </button>
      </div>
    </header>
  )
}

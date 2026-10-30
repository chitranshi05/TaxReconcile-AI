import { BrandMark } from './BrandMark'
import { ThemeSwitcher } from './ThemeSwitcher'
import { Timecode } from './Timecode'

interface TopBarProps {
  title: string
  subtitle: string
  health: 'healthy' | 'unhealthy' | 'loading'
  onUpload?: () => void
  activePage: string
  onNavigate: (page: string) => void
  onMenu: () => void
  menuOpen?: boolean
}

const NAV = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'documents', label: 'Documents' },
  { id: 'transactions', label: 'Ledger' },
  { id: 'reconciliation', label: 'Match' },
  { id: 'anomalies', label: 'Flags' },
  { id: 'reports', label: 'Reports' },
  { id: 'settings', label: 'Settings' },
]

function HealthPill({ status }: { status: TopBarProps['health'] }) {
  const labels = {
    healthy: 'API live',
    unhealthy: 'API dark',
    loading: 'Checking',
  }
  return (
    <div
      className={`health-pill ${status}`}
      id="health-status-pill"
      aria-label={`API status: ${status}`}
    >
      <span className="health-dot" />
      {labels[status]}
    </div>
  )
}

export function TopBar({
  health,
  onUpload,
  activePage,
  onNavigate,
  onMenu,
  menuOpen = false,
}: TopBarProps) {
  return (
    <header className="header" aria-label="Page header">
      <div className="header-row wrap">
        <a
          className="brand"
          href="#main-content"
          onClick={(e) => {
            e.preventDefault()
            onNavigate('dashboard')
          }}
          aria-label="TaxReconcile, home"
        >
          <BrandMark />
          <span className="brand-word">TaxReconcile</span>
        </a>

        <Timecode />

        <nav className="nav" aria-label="Primary">
          <ul className="nav-list">
            {NAV.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={`nav-link${activePage === item.id ? ' is-current' : ''}`}
                  onClick={() => onNavigate(item.id)}
                  aria-current={activePage === item.id ? 'page' : undefined}
                >
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <div className="header-actions">
          <ThemeSwitcher />
          <HealthPill status={health} />
          {onUpload && (
            <button
              id="topbar-upload-btn"
              className="topbar-btn primary"
              onClick={onUpload}
              title="Upload a new document"
            >
              Upload
            </button>
          )}
          <button
            id="topbar-docs-btn"
            className="menu-btn mono"
            type="button"
            aria-expanded={menuOpen}
            aria-controls="site-menu"
            onClick={onMenu}
          >
            Menu
          </button>
        </div>
      </div>
    </header>
  )
}

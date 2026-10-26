// TopBar — page title, health indicator, and action buttons

interface TopBarProps {
  title: string
  subtitle: string
  health: 'healthy' | 'unhealthy' | 'loading'
  onUpload?: () => void
}

function HealthPill({ status }: { status: TopBarProps['health'] }) {
  const labels = {
    healthy: 'API Healthy',
    unhealthy: 'API Offline',
    loading: 'Checking…',
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

export function TopBar({ title, subtitle, health, onUpload }: TopBarProps) {
  return (
    <header className="topbar" aria-label="Page header">
      <div className="topbar-left">
        <h1 className="topbar-title">{title}</h1>
        <p className="topbar-subtitle">{subtitle}</p>
      </div>

      <div className="topbar-right">
        <HealthPill status={health} />

        <button
          id="topbar-docs-btn"
          className="topbar-btn"
          title="View API documentation"
        >
          📖 API Docs
        </button>

        {onUpload && (
          <button
            id="topbar-upload-btn"
            className="topbar-btn primary"
            onClick={onUpload}
            title="Upload a new document"
          >
            ＋ Upload
          </button>
        )}
      </div>
    </header>
  )
}

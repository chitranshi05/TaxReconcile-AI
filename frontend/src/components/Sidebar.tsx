// Sidebar navigation component
// Active page state is lifted to App — this is presentation only

interface NavItem {
  id: string
  label: string
  icon: string
  badge?: string | number
}

interface SidebarProps {
  activePage: string
  onNavigate: (page: string) => void
}

const NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: '⬛' },
  { id: 'documents', label: 'Documents', icon: '📄', badge: 0 },
  { id: 'transactions', label: 'Transactions', icon: '💳' },
  { id: 'reconciliation', label: 'Reconciliation', icon: '🔄' },
  { id: 'anomalies', label: 'Anomaly Detection', icon: '⚠️' },
]

const UTILITY_ITEMS: NavItem[] = [
  { id: 'reports', label: 'Reports', icon: '📊' },
  { id: 'settings', label: 'Settings', icon: '⚙️' },
]

export function Sidebar({ activePage, onNavigate }: SidebarProps) {
  return (
    <aside className="sidebar" aria-label="Main navigation">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">🧾</div>
        <div className="sidebar-logo-text">
          <span>TaxReconcile</span>
          <span>AI Platform</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="sidebar-nav">
        <span className="nav-section-label">Main</span>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            id={`nav-${item.id}`}
            className={`nav-item${activePage === item.id ? ' active' : ''}`}
            onClick={() => onNavigate(item.id)}
            aria-current={activePage === item.id ? 'page' : undefined}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
            {item.badge !== undefined && (
              <span className="nav-badge">{item.badge}</span>
            )}
          </button>
        ))}

        <span className="nav-section-label">Utility</span>
        {UTILITY_ITEMS.map((item) => (
          <button
            key={item.id}
            id={`nav-${item.id}`}
            className={`nav-item${activePage === item.id ? ' active' : ''}`}
            onClick={() => onNavigate(item.id)}
            aria-current={activePage === item.id ? 'page' : undefined}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      {/* User card */}
      <div className="sidebar-footer">
        <div className="user-card" id="user-profile-card">
          <div className="user-avatar">U</div>
          <div className="user-info">
            <span className="user-name">User</span>
            <span className="user-role">USER · Ready</span>
          </div>
        </div>
      </div>
    </aside>
  )
}

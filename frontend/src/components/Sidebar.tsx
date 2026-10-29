// Sidebar navigation component
// Shows dynamic user info from /api/auth/me with sign-out support

import type { UserResponse } from '../types/api'

interface NavItem {
  id: string
  label: string
  icon: string
  badge?: string | number
}

interface SidebarProps {
  activePage: string
  onNavigate: (page: string) => void
  user?: UserResponse | null
  onLogout?: () => void
  documentsCount?: number
}

const NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: '⬛' },
  { id: 'documents', label: 'Documents', icon: '📄' },
  { id: 'transactions', label: 'Transactions', icon: '💳' },
  { id: 'reconciliation', label: 'Reconciliation', icon: '🔄' },
  { id: 'anomalies', label: 'Anomaly Detection', icon: '⚠️' },
]

const UTILITY_ITEMS: NavItem[] = [
  { id: 'reports', label: 'Reports', icon: '📊' },
  { id: 'settings', label: 'Settings', icon: '⚙️' },
]

export function Sidebar({
  activePage,
  onNavigate,
  user,
  onLogout,
  documentsCount,
}: SidebarProps) {
  const userInitials = user?.name
    ? user.name
      .split(' ')
      .map((part) => part[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
    : 'U'

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
        {NAV_ITEMS.map((item) => {
          const badgeValue =
            item.id === 'documents' && documentsCount !== undefined
              ? documentsCount
              : item.badge

          return (
            <button
              key={item.id}
              id={`nav-${item.id}`}
              className={`nav-item${activePage === item.id ? ' active' : ''}`}
              onClick={() => onNavigate(item.id)}
              aria-current={activePage === item.id ? 'page' : undefined}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
              {badgeValue !== undefined && (
                <span className="nav-badge">{badgeValue}</span>
              )}
            </button>
          )
        })}

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

      {/* User card & Logout */}
      <div className="sidebar-footer">
        <div className="user-card" id="user-profile-card">
          <div className="user-avatar">{userInitials}</div>
          <div className="user-info">
            <span className="user-name" title={user?.name || 'User'}>
              {user?.name || 'User'}
            </span>
            <span className="user-role">
              {user?.role || 'USER'} · Active
            </span>
          </div>
        </div>
        {onLogout && (
          <button
            type="button"
            className="sidebar-logout-btn"
            onClick={onLogout}
            title="Sign out of account"
          >
            Sign out
          </button>
        )}
      </div>
    </aside>
  )
}

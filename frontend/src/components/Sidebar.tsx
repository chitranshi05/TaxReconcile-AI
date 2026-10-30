import type { UserResponse } from '../types/api'

interface NavItem {
  id: string
  index: string
  label: string
  badge?: string | number
}

interface SidebarProps {
  activePage: string
  onNavigate: (page: string) => void
  user?: UserResponse | null
  onLogout?: () => void
  documentsCount?: number
  open?: boolean
  onClose?: () => void
}

const NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', index: '01', label: 'Dashboard' },
  { id: 'documents', index: '02', label: 'Documents' },
  { id: 'transactions', index: '03', label: 'Transactions' },
  { id: 'reconciliation', index: '04', label: 'Reconciliation' },
  { id: 'anomalies', index: '05', label: 'Anomaly Detection' },
  { id: 'reports', index: '06', label: 'Reports' },
  { id: 'settings', index: '07', label: 'Settings' },
]

export function Sidebar({
  activePage,
  onNavigate,
  user,
  onLogout,
  documentsCount,
  open = false,
  onClose,
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
    <div
      className={`menu${open ? ' is-open' : ''}`}
      id="site-menu"
      hidden={!open}
    >
      <div className="menu-backdrop" onClick={onClose} />
      <aside className="sidebar" aria-label="Main navigation">
        <div className="menu-head">
          <span className="mono menu-kicker">CUE LIST</span>
          <button type="button" className="menu-close mono" onClick={onClose}>
            Close
          </button>
        </div>

        <nav className="sidebar-nav">
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
                onClick={() => {
                  onNavigate(item.id)
                  onClose?.()
                }}
                aria-current={activePage === item.id ? 'page' : undefined}
              >
                <span className="nav-index mono">{item.index}</span>
                <span className="nav-label">{item.label}</span>
                {badgeValue !== undefined && (
                  <span className="nav-badge">{badgeValue}</span>
                )}
              </button>
            )
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="user-card" id="user-profile-card">
            <div className="user-avatar">{userInitials}</div>
            <div className="user-info">
              <span className="user-name" title={user?.name || 'User'}>
                {user?.name || 'User'}
              </span>
              <span className="user-role">{user?.role || 'USER'} · On air</span>
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
    </div>
  )
}

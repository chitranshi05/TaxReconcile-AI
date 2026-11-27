import React from 'react'
import {
  LedgerIcon,
  DocumentIcon,
  TransactionIcon,
  ReconcileIcon,
  AnomalyIcon,
  ReportIcon,
  SettingsIcon,
  LockIcon,
} from './Icons'

export interface NavItem {
  id: string
  label: string
  icon: React.ComponentType<{ size?: number; className?: string }>
  badge?: string | number
}

interface SidebarProps {
  activePage: string
  onNavigate: (page: string) => void
  userName?: string
  userRole?: string
}

const PRIMARY_NAV: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LedgerIcon },
  { id: 'documents', label: 'Documents', icon: DocumentIcon },
  { id: 'transactions', label: 'Financial Ledger', icon: TransactionIcon },
  { id: 'reconciliation', label: 'Reconciliation', icon: ReconcileIcon },
  { id: 'anomalies', label: 'Tax & Anomalies', icon: AnomalyIcon },
]

const AUDIT_NAV: NavItem[] = [
  { id: 'reports', label: 'Reports & Exports', icon: ReportIcon },
  { id: 'settings', label: 'Settings & Access', icon: SettingsIcon },
]

export function Sidebar({ activePage, onNavigate, userName = 'Auditor', userRole = 'USER' }: SidebarProps) {
  return (
    <aside className="sidebar" aria-label="Main navigation">
      <div>
        <div className="sidebar-brand">
          <div className="brand-badge">Institutional Edition</div>
          <h1 className="brand-title">Private Ledger</h1>
          <div className="brand-sub">TaxReconcile·AI — Swiss Grade</div>
        </div>

        <nav className="sidebar-nav">
          <span className="nav-section-title">Core Operations</span>
          {PRIMARY_NAV.map((item) => {
            const Icon = item.icon
            const isActive = activePage === item.id
            return (
              <button
                key={item.id}
                id={`nav-${item.id}`}
                className={`nav-item${isActive ? ' active' : ''}`}
                onClick={() => onNavigate(item.id)}
                aria-current={isActive ? 'page' : undefined}
              >
                <span className="nav-icon">
                  <Icon size={16} />
                </span>
                <span>{item.label}</span>
                {item.badge !== undefined && <span className="nav-badge">{item.badge}</span>}
              </button>
            )
          })}

          <span className="nav-section-title" style={{ marginTop: '12px' }}>Audit & Governance</span>
          {AUDIT_NAV.map((item) => {
            const Icon = item.icon
            const isActive = activePage === item.id
            return (
              <button
                key={item.id}
                id={`nav-${item.id}`}
                className={`nav-item${isActive ? ' active' : ''}`}
                onClick={() => onNavigate(item.id)}
                aria-current={isActive ? 'page' : undefined}
              >
                <span className="nav-icon">
                  <Icon size={16} />
                </span>
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>
      </div>

      <div className="sidebar-footer">
        <div className="institution-tag">
          <div className="institution-info">
            <span className="institution-name">{userName}</span>
            <span className="institution-jurisdiction">{userRole} · Secure Session</span>
          </div>
          <span className="institution-lock">
            <LockIcon size={13} />
          </span>
        </div>
      </div>
    </aside>
  )
}

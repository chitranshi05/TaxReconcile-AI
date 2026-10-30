// QuickActions — shortcut buttons for common workflows

interface QuickAction {
  id: string
  icon: string
  label: string
  onClick?: () => void
}

interface QuickActionsProps {
  onNavigate?: (page: string) => void
  onUpload?: () => void
}

export function QuickActions({ onNavigate, onUpload }: QuickActionsProps) {
  const actions: QuickAction[] = [
    {
      id: 'qa-upload',
      icon: '01',
      label: 'Upload Document',
      onClick: onUpload,
    },
    {
      id: 'qa-transactions',
      icon: '02',
      label: 'View Transactions',
      onClick: () => onNavigate?.('transactions'),
    },
    {
      id: 'qa-reconcile',
      icon: '03',
      label: 'Run Reconciliation',
      onClick: () => onNavigate?.('reconciliation'),
    },
    {
      id: 'qa-anomalies',
      icon: '04',
      label: 'Check Anomalies',
      onClick: () => onNavigate?.('anomalies'),
    },
    {
      id: 'qa-reports',
      icon: '05',
      label: 'Generate Report',
      onClick: () => onNavigate?.('reports'),
    },
    {
      id: 'qa-settings',
      icon: '06',
      label: 'Settings',
      onClick: () => onNavigate?.('settings'),
    },
  ]

  return (
    <div className="card" id="quick-actions-card">
      <div className="section-header">
        <h2 className="section-title">
          <span className="section-title-icon">⚡</span>
          Quick Actions
        </h2>
      </div>
      <div className="quick-actions">
        {actions.map((action) => (
          <button
            key={action.id}
            id={action.id}
            className="quick-action-btn"
            onClick={action.onClick}
            type="button"
          >
            <span className="quick-action-icon">{action.icon}</span>
            {action.label}
          </button>
        ))}
      </div>
    </div>
  )
}

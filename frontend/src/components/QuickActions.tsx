interface QuickActionsProps {
  onNavigate: (page: string) => void
  onUpload?: () => void
}

export function QuickActions({ onNavigate, onUpload }: QuickActionsProps) {
  return (
    <div className="paper-panel">
      <div className="panel-header">
        <div className="panel-title-group">
          <h2 className="panel-title">Institutional Actions</h2>
          <span className="panel-subtitle">Primary accounting workflows</span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        <button
          className="btn btn-primary"
          onClick={() => {
            onUpload?.()
            onNavigate('documents')
          }}
          style={{ justifyContent: 'flex-start', padding: '14px 16px' }}
        >
          <div>
            <div style={{ fontWeight: 600 }}>Ingest Statement</div>
            <div style={{ fontSize: '11px', opacity: 0.8, marginTop: '2px' }}>
              Upload CSV or Excel file
            </div>
          </div>
        </button>

        <button
          className="btn btn-secondary"
          onClick={() => onNavigate('reconciliation')}
          style={{ justifyContent: 'flex-start', padding: '14px 16px' }}
        >
          <div>
            <div style={{ fontWeight: 600 }}>Execute Reconciliation</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Bank vs. Books cross-match
            </div>
          </div>
        </button>

        <button
          className="btn btn-secondary"
          onClick={() => onNavigate('transactions')}
          style={{ justifyContent: 'flex-start', padding: '14px 16px' }}
        >
          <div>
            <div style={{ fontWeight: 600 }}>Browse General Ledger</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Filter & verify transactions
            </div>
          </div>
        </button>

        <button
          className="btn btn-secondary"
          onClick={() => onNavigate('anomalies')}
          style={{ justifyContent: 'flex-start', padding: '14px 16px' }}
        >
          <div>
            <div style={{ fontWeight: 600 }}>Tax & Anomalies Audit</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
              IQR outliers & Section 269ST
            </div>
          </div>
        </button>
      </div>
    </div>
  )
}

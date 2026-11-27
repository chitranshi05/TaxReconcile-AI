interface ActivityItem {
  id: string
  action: string
  detail: string
  time: string
  code: string
}

const RECENT_ACTIVITIES: ActivityItem[] = [
  {
    id: '1',
    action: 'Reconciliation Execution',
    detail: 'Bank vs Ledger matched 2 items, flagged 2 variances',
    time: 'Moments ago',
    code: 'REC-2026',
  },
  {
    id: '2',
    action: 'Tax Rule Engine Evaluation',
    detail: 'FY 2024-25 Chapter VI-A statutory compliance verified',
    time: '12m ago',
    code: 'SEC-80C',
  },
  {
    id: '3',
    action: 'Cryptographic Intake',
    detail: 'Statement sample_statement.csv processed and indexed',
    time: '24m ago',
    code: 'DOC-501',
  },
  {
    id: '4',
    action: 'Audit Integrity Check',
    detail: 'MongoDB index constraints verified on collections',
    time: '1h ago',
    code: 'SYS-OK',
  },
]

export function ActivityFeed() {
  return (
    <div className="paper-panel">
      <div className="panel-header">
        <div className="panel-title-group">
          <h2 className="panel-title">Audit Trail</h2>
          <span className="panel-subtitle">Immutable chronological operational records</span>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {RECENT_ACTIVITIES.map((act) => (
          <div
            key={act.id}
            style={{
              display: 'flex',
              alignItems: 'baseline',
              justifyContent: 'space-between',
              padding: '8px 10px',
              borderBottom: '1px solid var(--border-hairline)',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="format-pill">{act.code}</span>
                <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>
                  {act.action}
                </span>
              </div>
              <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                {act.detail}
              </div>
            </div>
            <span className="mono-cell" style={{ fontSize: '10.5px' }}>
              {act.time}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

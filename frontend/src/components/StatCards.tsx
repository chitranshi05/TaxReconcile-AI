interface StatCardsProps {
  totalDocuments?: number
  totalTransactions?: number
  matchedCount?: number
  discrepancyCount?: number
  reconciliationRate?: number
}

export function StatCards({
  totalDocuments = 0,
  totalTransactions = 0,
  matchedCount = 0,
  discrepancyCount = 0,
  reconciliationRate = 100,
}: StatCardsProps) {
  return (
    <div className="kpi-grid">
      <div className="kpi-item">
        <span className="kpi-label">Ingested Statements</span>
        <span className="kpi-value">{totalDocuments.toLocaleString()}</span>
        <span className="kpi-sub">Archived in isolated storage</span>
      </div>

      <div className="kpi-item">
        <span className="kpi-label">Normalized Ledger Rows</span>
        <span className="kpi-value">{totalTransactions.toLocaleString()}</span>
        <span className="kpi-sub">Parsed & schema-validated</span>
      </div>

      <div className="kpi-item">
        <span className="kpi-label">Reconciled Entries</span>
        <span className="kpi-value" style={{ color: 'var(--brand-green)' }}>
          {matchedCount.toLocaleString()}
        </span>
        <span className="kpi-sub">{reconciliationRate.toFixed(1)}% match velocity</span>
      </div>

      <div className="kpi-item">
        <span className="kpi-label">Discrepancy Alerts</span>
        <span
          className="kpi-value"
          style={{ color: discrepancyCount > 0 ? 'var(--semantic-error)' : 'var(--text-primary)' }}
        >
          {discrepancyCount.toLocaleString()}
        </span>
        <span className="kpi-sub">Unmatched or amount variances</span>
      </div>
    </div>
  )
}

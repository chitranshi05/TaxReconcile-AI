// StatCards — summary metrics row at the top of the dashboard

interface StatCardProps {
  icon: string
  iconColor: 'purple' | 'green' | 'blue' | 'red'
  value: string | number
  label: string
  sub?: string
  trend?: { direction: 'up' | 'down' | 'neutral'; label: string }
  placeholder?: boolean
}

function StatCard({
  icon,
  iconColor,
  value,
  label,
  sub,
  trend,
  placeholder,
}: StatCardProps) {
  return (
    <div className="stat-card">
      <div className="stat-card-header">
        <div className={`stat-icon ${iconColor}`}>{icon}</div>
        {trend && (
          <span className={`stat-trend ${trend.direction}`}>{trend.label}</span>
        )}
      </div>
      <div>
        <div className={`stat-value${placeholder ? ' placeholder' : ''}`}>
          {placeholder ? '—' : value}
        </div>
        <div className="stat-label">{label}</div>
        {sub && <div className="stat-sub">{sub}</div>}
      </div>
    </div>
  )
}

interface StatCardsProps {
  documentsCount?: number
  transactionsCount?: number
  anomaliesCount?: number
  invalidRowsCount?: number
}

export function StatCards({
  documentsCount = 0,
  transactionsCount = 0,
  anomaliesCount = 0,
  invalidRowsCount = 0,
}: StatCardsProps) {
  const hasDocuments = documentsCount > 0

  return (
    <div className="stats-grid">
      <StatCard
        icon="01"
        iconColor="purple"
        value={documentsCount}
        label="Documents Uploaded"
        sub="Total files tracked"
        trend={
          hasDocuments
            ? { direction: 'up', label: `${documentsCount} active` }
            : { direction: 'neutral', label: 'No files yet' }
        }
        placeholder={!hasDocuments}
      />
      <StatCard
        icon="02"
        iconColor="green"
        value={transactionsCount.toLocaleString()}
        label="Transactions Processed"
        sub="Valid rows extracted"
        trend={
          transactionsCount > 0
            ? { direction: 'up', label: `${transactionsCount} records` }
            : { direction: 'neutral', label: 'Awaiting process' }
        }
        placeholder={transactionsCount === 0}
      />
      <StatCard
        icon="03"
        iconColor="blue"
        value={anomaliesCount}
        label="Anomalies Detected"
        sub="Flagged for review"
        trend={
          anomaliesCount > 0
            ? { direction: 'down', label: `${anomaliesCount} flagged` }
            : { direction: 'neutral', label: 'None flagged' }
        }
        placeholder={anomaliesCount === 0}
      />
      <StatCard
        icon="04"
        iconColor="red"
        value={invalidRowsCount}
        label="Invalid Rows"
        sub="Validation errors"
        trend={
          invalidRowsCount > 0
            ? { direction: 'down', label: `${invalidRowsCount} failed` }
            : { direction: 'neutral', label: 'Clean ingestion' }
        }
        placeholder={invalidRowsCount === 0}
      />
    </div>
  )
}

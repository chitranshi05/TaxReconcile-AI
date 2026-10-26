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

function StatCard({ icon, iconColor, value, label, sub, trend, placeholder }: StatCardProps) {
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

export function StatCards() {
  return (
    <div className="stats-grid">
      <StatCard
        icon="📄"
        iconColor="purple"
        value="—"
        label="Documents Uploaded"
        sub="All time"
        trend={{ direction: 'neutral', label: 'No data' }}
        placeholder
      />
      <StatCard
        icon="✅"
        iconColor="green"
        value="—"
        label="Transactions Processed"
        sub="Valid rows saved"
        trend={{ direction: 'neutral', label: 'No data' }}
        placeholder
      />
      <StatCard
        icon="🔍"
        iconColor="blue"
        value="—"
        label="Anomalies Detected"
        sub="Flagged for review"
        trend={{ direction: 'neutral', label: 'No data' }}
        placeholder
      />
      <StatCard
        icon="⚠️"
        iconColor="red"
        value="—"
        label="Invalid Rows"
        sub="Failed validation"
        trend={{ direction: 'neutral', label: 'No data' }}
        placeholder
      />
    </div>
  )
}

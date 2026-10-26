// ActivityFeed — recent system activity log
// Will be driven by real events once the backend exposes an activity/audit endpoint

interface ActivityEvent {
  id: string
  color: 'green' | 'blue' | 'yellow' | 'red' | 'purple'
  message: string
  meta: string
}

// Placeholder events shown until real data is available
const PLACEHOLDER_EVENTS: ActivityEvent[] = [
  {
    id: '1',
    color: 'blue',
    message: 'Dashboard loaded successfully',
    meta: 'Just now',
  },
  {
    id: '2',
    color: 'purple',
    message: 'Waiting for first document upload',
    meta: 'No activity yet',
  },
]

interface ActivityFeedProps {
  events?: ActivityEvent[]
}

export function ActivityFeed({ events }: ActivityFeedProps) {
  const items = events ?? PLACEHOLDER_EVENTS

  return (
    <div className="card" id="activity-feed-card">
      <div className="section-header">
        <h2 className="section-title">
          <span className="section-title-icon">🕐</span>
          Recent Activity
        </h2>
        <button className="section-action" id="clear-activity-btn">
          Clear
        </button>
      </div>

      <div className="activity-list" role="log" aria-live="polite" aria-label="Activity log">
        {items.map((event) => (
          <div className="activity-item" key={event.id}>
            <div className="activity-dot-wrap">
              <div className={`activity-dot ${event.color}`} />
            </div>
            <div className="activity-body">
              <div className="activity-msg">{event.message}</div>
              <div className="activity-meta">{event.meta}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

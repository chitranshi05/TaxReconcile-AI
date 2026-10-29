// ActivityFeed — recent system activity log driven by document events

import type { DocumentListItem } from '../types/api'

export interface ActivityEvent {
  id: string
  color: 'green' | 'blue' | 'yellow' | 'red' | 'purple'
  message: string
  meta: string
}

interface ActivityFeedProps {
  events?: ActivityEvent[]
  documents?: DocumentListItem[]
}

export function ActivityFeed({ events, documents }: ActivityFeedProps) {
  // If custom events are provided, use them; otherwise derive from tracked documents
  let items: ActivityEvent[] = []

  if (events && events.length > 0) {
    items = events
  } else if (documents && documents.length > 0) {
    items = documents.slice(0, 5).map((doc) => {
      const isProcessed = doc.status === 'PROCESSED'
      const isFailed = doc.status === 'FAILED'
      const color: ActivityEvent['color'] = isProcessed
        ? 'green'
        : isFailed
          ? 'red'
          : 'blue'

      const dateStr = doc.uploaded_at
        ? new Date(doc.uploaded_at).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })
        : 'Recently'

      const statusNote = isProcessed
        ? `Processed (${doc.transaction_count || 0} txns)`
        : isFailed
          ? 'Failed processing'
          : 'Uploaded & ready'

      return {
        id: doc.document_id,
        color,
        message: `${doc.filename} — ${statusNote}`,
        meta: dateStr,
      }
    })
  } else {
    items = [
      {
        id: 'init-1',
        color: 'green',
        message: 'Workspace authenticated and ready',
        meta: 'Active',
      },
      {
        id: 'init-2',
        color: 'purple',
        message: 'Awaiting first document upload',
        meta: 'Standby',
      },
    ]
  }

  return (
    <div className="card" id="activity-feed-card">
      <div className="section-header">
        <h2 className="section-title">
          <span className="section-title-icon">🕐</span>
          Recent Activity
        </h2>
      </div>

      <div
        className="activity-list"
        role="log"
        aria-live="polite"
        aria-label="Activity log"
      >
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

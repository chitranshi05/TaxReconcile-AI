import type { DocumentListItem } from '../types/api'

export interface ActivityEvent {
  id: string
  color: 'green' | 'blue' | 'yellow' | 'red' | 'purple'
  cue: string
  message: string
  meta: string
}

interface ActivityFeedProps {
  events?: ActivityEvent[]
  documents?: DocumentListItem[]
}

export function ActivityFeed({ events, documents }: ActivityFeedProps) {
  let items: ActivityEvent[] = []

  if (events && events.length > 0) {
    items = events
  } else if (documents && documents.length > 0) {
    items = documents.slice(0, 5).map((doc, idx) => {
      const isProcessed = doc.status === 'PROCESSED'
      const isFailed = doc.status === 'FAILED'
      const color: ActivityEvent['color'] = isProcessed
        ? 'green'
        : isFailed
          ? 'red'
          : 'blue'

      const cue = isProcessed ? 'TAKE' : isFailed ? 'HOLD' : 'SYNC'

      const dateStr = doc.uploaded_at
        ? new Date(doc.uploaded_at).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          })
        : 'LIVE'

      const statusNote = isProcessed
        ? `Extracted ${doc.transaction_count || 0} rows`
        : isFailed
          ? 'Processing halted'
          : 'Ingested · Awaiting process'

      return {
        id: doc.document_id || String(idx),
        color,
        cue,
        message: `${doc.filename} — ${statusNote}`,
        meta: dateStr,
      }
    })
  } else {
    items = [
      {
        id: 'init-1',
        color: 'green',
        cue: 'ON AIR',
        message: 'Workspace authenticated and ready on clock',
        meta: 'LIVE',
      },
      {
        id: 'init-2',
        color: 'purple',
        cue: 'STANDBY',
        message: 'Awaiting first document ingestion',
        meta: 'STANDBY',
      },
    ]
  }

  return (
    <div className="card" id="activity-feed-card">
      <div className="section-header">
        <div>
          <span className="mono cue-label">CUE 03 · ACTIVITY LOG</span>
          <h2 className="section-title">System Log</h2>
        </div>
        <span className="dot dot-live" title="Live stream active" />
      </div>

      <div
        className="activity-list"
        role="log"
        aria-live="polite"
        aria-label="Activity log"
      >
        {items.map((event) => (
          <div className="activity-item" key={event.id}>
            <div className="activity-cue mono">{event.cue}</div>
            <div className="activity-body">
              <div className="activity-msg">{event.message}</div>
              <div className="activity-meta mono t-num">{event.meta}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

import { useState } from 'react'
import { triggerPipeline, type PipelineResults } from '../services/pipeline'
import { ReconcileIcon, CheckIcon } from './Icons'

interface ProcessingPipelineProps {
  documentId?: string
  documentName?: string
  onPipelineCompleted?: (results: PipelineResults) => void
}

const STAGES = [
  { key: 'EXTRACTING', step: '01', title: 'Extraction', desc: 'CSV, XLSX & JSON reader' },
  { key: 'NORMALIZING', step: '02', title: 'Normalization', desc: 'Schema standardization & saving' },
  { key: 'DEDUPLICATING', step: '03', title: 'Deduplication', desc: 'Collision & signature detection' },
  { key: 'RECONCILING', step: '04', title: 'Reconciliation', desc: 'Cross-matching books vs bank' },
  { key: 'ANALYZING', step: '05', title: 'Tax & Anomalies', desc: 'IQR outliers & Indian IT Act' },
  { key: 'GENERATING_REPORT', step: '06', title: 'Audit Report', desc: 'Consolidated scoring & findings' },
]

export function ProcessingPipeline({
  documentId,
  documentName,
  onPipelineCompleted,
}: ProcessingPipelineProps) {
  const [isRunning, setIsRunning] = useState(false)
  const [activeStage, setActiveStage] = useState<string>('IDLE')
  const [progress, setProgress] = useState<number>(0)
  const [lastResults, setLastResults] = useState<PipelineResults | null>(null)
  const [errorMsg, setErrorMsg] = useState<string>('')

  async function handleRunPipeline() {
    if (!documentId) return
    setIsRunning(true)
    setErrorMsg('')
    setActiveStage('EXTRACTING')
    setProgress(20)

    try {
      const res = await triggerPipeline(documentId, null, false)
      if (res.results) {
        setLastResults(res.results)
        setActiveStage('COMPLETED')
        setProgress(100)
        onPipelineCompleted?.(res.results)
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Pipeline orchestration failed.')
      setActiveStage('FAILED')
    } finally {
      setIsRunning(false)
    }
  }

  function getStageStatus(stageKey: string) {
    if (activeStage === 'COMPLETED') return 'COMPLETED'
    if (activeStage === 'FAILED') return 'ERROR'
    if (activeStage === stageKey) return 'ACTIVE'

    const order = ['EXTRACTING', 'NORMALIZING', 'DEDUPLICATING', 'RECONCILING', 'ANALYZING', 'GENERATING_REPORT']
    const currentIndex = order.indexOf(activeStage)
    const thisIndex = order.indexOf(stageKey)

    if (currentIndex >= 0 && thisIndex < currentIndex) return 'COMPLETED'
    return 'READY'
  }

  return (
    <div className="paper-panel">
      <div className="panel-header">
        <div className="panel-title-group">
          <h2 className="panel-title">Automated Pipeline Orchestrator</h2>
          <span className="panel-subtitle">Sequential execution of extraction, matching & tax governance</span>
        </div>

        {documentId && (
          <button
            className="btn btn-primary btn-sm"
            onClick={handleRunPipeline}
            disabled={isRunning}
          >
            <ReconcileIcon size={13} className={isRunning ? 'spin' : ''} />
            {isRunning ? 'Running Pipeline…' : 'Run Full Pipeline'}
          </button>
        )}
      </div>

      {documentName && (
        <div style={{ marginBottom: '14px', fontSize: '12px', color: 'var(--text-secondary)' }}>
          Target Statement: <strong>{documentName}</strong>
        </div>
      )}

      {errorMsg && (
        <div
          style={{
            padding: '10px 14px',
            backgroundColor: 'var(--semantic-error-bg)',
            border: '1px solid var(--semantic-error-border)',
            color: 'var(--semantic-error)',
            borderRadius: 'var(--radius-sm)',
            fontSize: '12px',
            marginBottom: '14px',
          }}
        >
          {errorMsg}
        </div>
      )}

      {/* Progress Bar */}
      {isRunning && (
        <div style={{ marginBottom: '16px' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              marginBottom: '4px',
            }}
          >
            <span>Orchestrating services…</span>
            <span>{progress}%</span>
          </div>
          <div
            style={{
              height: '4px',
              width: '100%',
              backgroundColor: 'var(--bg-subtle)',
              borderRadius: '2px',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${progress}%`,
                backgroundColor: 'var(--brand-green)',
                transition: 'width 250ms ease-out',
              }}
            />
          </div>
        </div>
      )}

      {/* Sequential Pipeline Stages */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {STAGES.map((s) => {
          const status = getStageStatus(s.key)
          const isCurrent = status === 'ACTIVE'
          const isDone = status === 'COMPLETED'

          return (
            <div
              key={s.step}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '14px',
                padding: '8px 12px',
                backgroundColor: isCurrent ? 'var(--brand-green-subtle)' : 'var(--bg-subtle)',
                border: `1px solid ${isCurrent ? 'var(--brand-green-border)' : 'var(--border-hairline)'}`,
                borderRadius: 'var(--radius-sm)',
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '10.5px',
                  fontWeight: 600,
                  color: isCurrent ? 'var(--brand-green)' : 'var(--text-muted)',
                }}
              >
                {s.step}
              </span>
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    fontSize: '12.5px',
                    fontWeight: 500,
                    color: isCurrent ? 'var(--brand-green)' : 'var(--text-primary)',
                  }}
                >
                  {s.title}
                </div>
                <div style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>{s.desc}</div>
              </div>
              <span
                className={`status-badge ${isDone ? 'processed' : isCurrent ? 'pending' : 'uploaded'}`}
              >
                {status}
              </span>
            </div>
          )
        })}
      </div>

      {/* Pipeline Scores Banner upon completion */}
      {lastResults && (
        <div
          style={{
            marginTop: '16px',
            padding: '14px',
            backgroundColor: 'var(--semantic-success-bg)',
            border: '1px solid var(--semantic-success-border)',
            borderRadius: 'var(--radius-sm)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--semantic-success)', fontWeight: 600, fontSize: '13px' }}>
            <CheckIcon size={14} />
            Pipeline Completed Successfully
          </div>
          <div style={{ display: 'flex', gap: '16px', marginTop: '8px', fontSize: '12px' }}>
            <div>
              Confidence: <strong>{lastResults.scores.confidence_score}%</strong>
            </div>
            <div>
              Tax Readiness: <strong>{lastResults.scores.tax_readiness_score}%</strong>
            </div>
            <div>
              Transactions: <strong>{lastResults.metrics.valid_transactions}</strong>
            </div>
            <div>
              Findings: <strong>{lastResults.findings.length}</strong>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

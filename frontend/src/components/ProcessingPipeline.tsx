// ProcessingPipeline — shows the 4-step document processing workflow
// Steps: Upload → Inspect → Process → Transactions

interface Step {
  id: string
  name: string
  description: string
  state: 'done' | 'active' | 'waiting'
}

interface PipelineStepsProps {
  currentStep?: number // 0-indexed; undefined = no active document
}

const STEPS: Omit<Step, 'state'>[] = [
  {
    id: 'upload',
    name: '1. Upload Document',
    description: 'POST /api/documents/upload — CSV, XLSX, PDF, JSON',
  },
  {
    id: 'inspect',
    name: '2. Inspect',
    description: 'GET /api/documents/{id}/inspect — column detection & validation',
  },
  {
    id: 'process',
    name: '3. Process',
    description: 'POST /api/documents/{id}/process — extract & save transactions',
  },
  {
    id: 'review',
    name: '4. Review Transactions',
    description: 'GET /api/documents/{id}/transactions — view extracted records',
  },
]

export function ProcessingPipeline({ currentStep }: PipelineStepsProps) {
  const steps: Step[] = STEPS.map((s, i) => ({
    ...s,
    state:
      currentStep === undefined
        ? 'waiting'
        : i < currentStep
        ? 'done'
        : i === currentStep
        ? 'active'
        : 'waiting',
  }))

  return (
    <div className="card" id="pipeline-card">
      <div className="section-header">
        <h2 className="section-title">
          <span className="section-title-icon">🔄</span>
          Processing Pipeline
        </h2>
      </div>

      <div className="pipeline-steps">
        {steps.map((step) => (
          <div className="pipeline-step" key={step.id} id={`step-${step.id}`}>
            <div className={`step-number ${step.state}`}>
              {step.state === 'done' ? '✓' : step.state === 'active' ? '►' : '○'}
            </div>
            <div className="step-info">
              <div className="step-name">{step.name}</div>
              <div className="step-desc">{step.description}</div>
            </div>
            <div
              className={`step-status ${step.state === 'done' ? 'ready' : step.state === 'active' ? 'ready' : 'waiting'}`}
            >
              {step.state === 'done' ? 'Done' : step.state === 'active' ? 'Active' : 'Waiting'}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

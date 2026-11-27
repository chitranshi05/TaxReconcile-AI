import { requestJson } from './apiClient'

export interface PipelineScores {
  confidence_score: number
  reconciliation_rate: number
  tax_readiness_score: number
  anomaly_risk_score: number
}

export interface PipelineMetrics {
  total_rows: number
  valid_transactions: number
  saved_transactions: number
  duplicate_count: number
  anomalous_count: number
  tax_findings_count: number
}

export interface PipelineFinding {
  source: string
  severity: string
  category: string
  rule_name: string
  description: string
  recommendation: string
}

export interface PipelineResults {
  job_id: string
  document_id: string
  paired_document_id?: string | null
  financial_year: string
  status: string
  scores: PipelineScores
  metrics: PipelineMetrics
  reconciliation?: Record<string, unknown> | null
  reconciliation_id?: string | null
  findings: PipelineFinding[]
  completed_at: string
}

export interface PipelineStatus {
  job_id: string
  document_id: string
  stage: string
  progress: number
  message: string
  error?: string | null
  updated_at?: string | null
}

export function triggerPipeline(
  documentId: string,
  pairedDocumentId?: string | null,
  runInBackground: boolean = false,
  financialYear: string = '2024-25',
): Promise<{
  message: string
  job_id: string
  stage: string
  progress: number
  results?: PipelineResults
}> {
  return requestJson('/api/pipeline/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      document_id: documentId,
      paired_document_id: pairedDocumentId,
      run_in_background: runInBackground,
      financial_year: financialYear,
    }),
  })
}

export function getPipelineStatus(jobId: string): Promise<PipelineStatus> {
  return requestJson(`/api/pipeline/${jobId}/status`)
}

export function getPipelineResults(jobId: string): Promise<{
  job_id: string
  document_id: string
  stage: string
  progress: number
  results: PipelineResults
}> {
  return requestJson(`/api/pipeline/${jobId}/results`)
}

export function getDocumentPipeline(documentId: string): Promise<{
  job_id: string
  document_id: string
  stage: string
  progress: number
  results?: PipelineResults
}> {
  return requestJson(`/api/pipeline/document/${documentId}`)
}

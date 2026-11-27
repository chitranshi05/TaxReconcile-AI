import { requestJson } from './apiClient'

export interface ReconciliationSummary {
  total_bank_transactions: number
  total_ledger_transactions: number
  matched_count: number
  potential_match_count: number
  amount_mismatch_count: number
  bank_only_count: number
  ledger_only_count: number
  reconciliation_rate: number
  total_bank_amount: number
  total_ledger_amount: number
  matched_amount: number
  net_discrepancy: number
}

export interface ReconciliationRun {
  reconciliation_id: string
  bank_document_id: string
  ledger_document_id: string
  bank_filename: string
  ledger_filename: string
  summary: ReconciliationSummary
  created_at: string
}

export function runReconciliation(
  bankDocumentId: string,
  ledgerDocumentId: string,
): Promise<{
  reconciliation_id: string
  bank_document_id: string
  ledger_document_id: string
  bank_filename: string
  ledger_filename: string
  summary: ReconciliationSummary
  matches: Array<Record<string, unknown>>
  bank_only: Array<Record<string, unknown>>
  ledger_only: Array<Record<string, unknown>>
}> {
  return requestJson('/api/reconciliation', {
    method: 'POST',
    body: JSON.stringify({
      bank_document_id: bankDocumentId,
      ledger_document_id: ledgerDocumentId,
    }),
    headers: {
      'Content-Type': 'application/json',
    },
  })
}

export function listReconciliations(): Promise<{
  count: number
  reconciliations: ReconciliationRun[]
}> {
  return requestJson('/api/reconciliation')
}

export function getReconciliation(reconciliationId: string): Promise<Record<string, unknown>> {
  return requestJson(`/api/reconciliation/${reconciliationId}`)
}

export async function downloadReconciliationReport(
  reconciliationId: string,
  format: 'xlsx' | 'pdf',
): Promise<void> {
  const token = localStorage.getItem('token') || sessionStorage.getItem('token')
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`

  const response = await fetch(`/api/reconciliation/${reconciliationId}/report?format=${format}`, {
    headers,
  })

  if (!response.ok) {
    throw new Error(`Report download failed with status ${response.status}`)
  }

  const blob = await response.blob()
  const downloadUrl = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = `reconciliation-${reconciliationId}.${format}`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(downloadUrl)
}

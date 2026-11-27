import type { DocumentMetadata, DocumentUploadResponse } from '../types/api'
import { requestJson } from './apiClient'

export function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  return requestJson<DocumentUploadResponse>('/api/documents/upload', {
    method: 'POST',
    body: formData,
  })
}

export function listDocuments(skip = 0, limit = 50): Promise<DocumentMetadata[]> {
  return requestJson<DocumentMetadata[]>(`/api/documents/?skip=${skip}&limit=${limit}`)
}

export function getDocument(documentId: string): Promise<DocumentMetadata> {
  return requestJson<DocumentMetadata>(`/api/documents/${documentId}`)
}

export function deleteDocument(documentId: string): Promise<{ message: string; document_id: string }> {
  return requestJson<{ message: string; document_id: string }>(`/api/documents/${documentId}`, {
    method: 'DELETE',
  })
}

export function inspectDocument(documentId: string): Promise<{
  document_id: string
  filename: string
  file_type: string
  sheets: Array<{
    sheet_name: string
    rows: number
    columns: string[]
    sample: Array<Record<string, unknown>>
    column_mapping: Record<string, string>
    validation: {
      valid: boolean
      total_rows: number
      valid_rows: number
      invalid_rows: number
      errors: Array<{ row: number | null; field: string | null; message: string }>
      warnings: Array<{ row: number | null; field: string | null; message: string }>
    }
  }>
}> {
  return requestJson(`/api/documents/${documentId}/inspect`)
}

export function processDocument(documentId: string): Promise<{
  message: string
  document_id: string
  total_rows: number
  valid_rows: number
  invalid_rows: number
  saved_transactions: number
  errors: Array<{ row: number; field: string; message: string }>
}> {
  return requestJson(`/api/documents/${documentId}/process`, {
    method: 'POST',
  })
}

export interface StoredTransaction {
  transaction_id: string
  document_id: string
  owner_id: string
  transaction_date: string
  description: string
  amount: number | null
  debit: number | null
  credit: number | null
  balance: number | null
  source_row: number | null
  created_at: string
}

export function getDocumentTransactions(documentId: string): Promise<{
  document_id: string
  filename: string
  transaction_count: number
  transactions: StoredTransaction[]
}> {
  return requestJson(`/api/documents/${documentId}/transactions`)
}

export function getDocumentDuplicates(documentId: string): Promise<{
  document_id: string
  filename: string
  total_transactions: number
  duplicate_count: number
  duplicate_groups_count: number
  duplicate_groups: Array<{
    hash: string
    count: number
    sample_transaction: StoredTransaction
    transactions: StoredTransaction[]
  }>
}> {
  return requestJson(`/api/documents/${documentId}/duplicates`)
}

export function getDocumentAnomalies(documentId: string): Promise<{
  document_id: string
  filename: string
  total_transactions: number
  anomalous_transactions_count: number
  normal_transactions_count: number
  anomaly_rate: number
  flag_counts: Record<string, number>
  statistics: {
    count: number
    mean: number
    median: number
    std: number
    q1: number
    q3: number
    iqr: number
    upper_bound: number
  }
  anomalies: Array<{
    transaction: StoredTransaction
    flags: string[]
    reasons: string[]
  }>
}> {
  return requestJson(`/api/documents/${documentId}/anomalies`)
}

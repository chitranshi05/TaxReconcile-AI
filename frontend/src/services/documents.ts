import type {
  DocumentAnomaliesResponse,
  DocumentDuplicatesResponse,
  DocumentInspectResponse,
  DocumentListItem,
  DocumentTaxValidationResponse,
  DocumentTransactionsResponse,
  DocumentUploadResponse,
  ProcessDocumentResponse,
  ReconciliationListResponse,
  ReconciliationRequest,
  ReconciliationResult,
  TaxRulesResponse,
} from '../types/api'
import { requestJson } from './apiClient'

const STORAGE_DOCS_KEY = 'tax_reconcile_documents'

export function loadDocuments(): DocumentListItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_DOCS_KEY)
    return raw ? (JSON.parse(raw) as DocumentListItem[]) : []
  } catch {
    return []
  }
}

export function listDocuments(): DocumentListItem[] {
  return loadDocuments()
}

export function saveStoredDocument(doc: DocumentListItem): void {
  const docs = loadDocuments()
  const existingIndex = docs.findIndex((d) => d.document_id === doc.document_id)

  if (existingIndex >= 0) {
    docs[existingIndex] = { ...docs[existingIndex], ...doc }
  } else {
    docs.unshift(doc)
  }

  localStorage.setItem(STORAGE_DOCS_KEY, JSON.stringify(docs))
}

export function updateStoredDocument(
  documentId: string,
  updates: Partial<DocumentListItem>,
): void {
  const docs = loadDocuments()
  const updatedDocs = docs.map((doc) =>
    doc.document_id === documentId ? { ...doc, ...updates } : doc,
  )
  localStorage.setItem(STORAGE_DOCS_KEY, JSON.stringify(updatedDocs))
}

export function deleteStoredDocument(documentId: string): void {
  const docs = loadDocuments()
  const updatedDocs = docs.filter((doc) => doc.document_id !== documentId)
  localStorage.setItem(STORAGE_DOCS_KEY, JSON.stringify(updatedDocs))
}

interface BackendDocumentMetadata {
  id: string
  filename: string
  file_type: DocumentListItem['file_type']
  document_type?: string
  status: DocumentListItem['status']
  owner_id?: string
  uploaded_at?: string
  transaction_count?: number
}

/**
 * Fetch documents from the backend API (GET /api/documents/) and synchronise with localStorage.
 * Falls back to local cache if offline or unauthenticated.
 */
export async function fetchDocuments(): Promise<DocumentListItem[]> {
  try {
    const remote = await requestJson<BackendDocumentMetadata[]>('/api/documents/')
    const local = loadDocuments()
    const localMap = new Map(local.map((d) => [d.document_id, d]))

    const merged: DocumentListItem[] = remote.map((item) => {
      const existing = localMap.get(item.id)
      return {
        document_id: item.id,
        filename: item.filename,
        file_type: item.file_type,
        status: (item.status as DocumentListItem['status']) || 'UPLOADED',
        uploaded_at: item.uploaded_at || existing?.uploaded_at || new Date().toISOString(),
        transaction_count: item.transaction_count ?? existing?.transaction_count ?? 0,
        invalid_row_count: existing?.invalid_row_count,
        column_mapping: existing?.column_mapping,
        processing_errors: existing?.processing_errors,
      }
    })

    localStorage.setItem(STORAGE_DOCS_KEY, JSON.stringify(merged))
    return merged
  } catch (error) {
    console.warn('Could not fetch server documents, using local cache:', error)
    return loadDocuments()
  }
}

/**
 * Delete a document from both backend and local storage.
 */
export async function deleteDocument(documentId: string): Promise<void> {
  try {
    await requestJson(`/api/documents/${documentId}`, {
      method: 'DELETE',
    })
  } catch (err) {
    console.warn('Backend delete document failed, removing locally:', err)
  }
  deleteStoredDocument(documentId)
}

export async function uploadDocument(
  file: File,
): Promise<DocumentUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await requestJson<DocumentUploadResponse>(
    '/api/documents/upload',
    {
      method: 'POST',
      body: formData,
    },
  )

  saveStoredDocument({
    document_id: response.document_id,
    filename: response.filename,
    file_type: response.file_type,
    status: (response.status as DocumentListItem['status']) || 'UPLOADED',
    uploaded_at: new Date().toISOString(),
  })

  return response
}

export async function inspectDocument(
  documentId: string,
): Promise<DocumentInspectResponse> {
  return requestJson<DocumentInspectResponse>(
    `/api/documents/${documentId}/inspect`,
  )
}

export async function processDocument(
  documentId: string,
): Promise<ProcessDocumentResponse> {
  const response = await requestJson<ProcessDocumentResponse>(
    `/api/documents/${documentId}/process`,
    {
      method: 'POST',
    },
  )

  updateStoredDocument(documentId, {
    status: 'PROCESSED',
    transaction_count: response.saved_transactions,
    invalid_row_count: response.invalid_rows,
    column_mapping: response.column_mapping,
    processing_errors: response.errors,
  })

  return response
}

export async function getDocumentTransactions(
  documentId: string,
): Promise<DocumentTransactionsResponse> {
  return requestJson<DocumentTransactionsResponse>(
    `/api/documents/${documentId}/transactions`,
  )
}

// ─── Anomalies & Duplicates ────────────────────────────────────────

export async function getDocumentAnomalies(
  documentId: string,
): Promise<DocumentAnomaliesResponse> {
  return requestJson<DocumentAnomaliesResponse>(
    `/api/documents/${documentId}/anomalies`,
  )
}

export async function getDocumentDuplicates(
  documentId: string,
): Promise<DocumentDuplicatesResponse> {
  return requestJson<DocumentDuplicatesResponse>(
    `/api/documents/${documentId}/duplicates`,
  )
}

// ─── Reconciliation ────────────────────────────────────────────────

export async function runReconciliation(
  req: ReconciliationRequest,
): Promise<ReconciliationResult> {
  return requestJson<ReconciliationResult>('/api/reconciliation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
}

export async function listReconciliations(): Promise<ReconciliationListResponse> {
  return requestJson<ReconciliationListResponse>('/api/reconciliation')
}

export async function getReconciliation(
  reconciliationId: string,
): Promise<ReconciliationResult> {
  return requestJson<ReconciliationResult>(
    `/api/reconciliation/${reconciliationId}`,
  )
}

// ─── Tax Validation & Compliance ───────────────────────────────────

export async function getTaxRules(): Promise<TaxRulesResponse> {
  return requestJson<TaxRulesResponse>('/api/tax-validation/rules')
}

export async function validateDocumentTaxCompliance(
  documentId: string,
  payload: {
    financial_year?: string
    is_senior_citizen?: boolean
    declared_income?: Record<string, number>
    claimed_deductions?: Record<string, number>
    tds_entries?: Array<Record<string, unknown>>
  } = {},
): Promise<DocumentTaxValidationResponse> {
  return requestJson<DocumentTaxValidationResponse>(
    `/api/tax-validation/documents/${documentId}/validate`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}

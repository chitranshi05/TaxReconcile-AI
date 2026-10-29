import type {
  DocumentInspectResponse,
  DocumentListItem,
  DocumentTransactionsResponse,
  DocumentUploadResponse,
  ProcessDocumentResponse,
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

  // Cache in local storage for document tracking in the UI
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

  // Update cached document record
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

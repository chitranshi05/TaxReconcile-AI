export interface ApiRootResponse {
  message: string
  status: 'success'
}

export interface HealthResponse {
  status: 'healthy' | 'unhealthy'
  database: 'connected' | 'disconnected'
}

export type SupportedUploadFileType = 'CSV' | 'XLSX' | 'XLS' | 'PDF' | 'JSON'

export interface DocumentUploadResponse {
  message: string
  document_id: string
  filename: string
  file_type: SupportedUploadFileType
  status: string
}

export interface ApiValidationIssue {
  loc: Array<string | number>
  msg: string
  type: string
}

export type ApiErrorResponse = {
  detail: string | ApiValidationIssue[]
}

// ─── Authentication Types ──────────────────────────────────────────

export interface TokenResponse {
  access_token: string
  token_type?: string
}

export interface UserResponse {
  id: string
  name: string
  email: string
  role: 'USER' | 'ADMIN' | string
}

// ─── Document Management Types ─────────────────────────────────────

export type DocumentStatus = 'UPLOADED' | 'PROCESSED' | 'FAILED' | 'PENDING'

export interface DocumentListItem {
  document_id: string
  filename: string
  file_type: string
  status: DocumentStatus
  transaction_count?: number
  invalid_row_count?: number
  uploaded_at?: string
  column_mapping?: Record<string, string>
  processing_errors?: Array<{ row?: number | null; field?: string | null; message?: string }>
}

export interface DocumentInspectionSheet {
  sheet_name?: string
  row_count?: number
  columns: string[]
  sample?: Array<Record<string, unknown>>
  column_mapping?: Record<string, string>
  validation_note?: string
  validation?: {
    valid: boolean
    total_rows: number
    valid_rows: number
    invalid_rows: number
    errors: Array<{ row?: number | null; field?: string | null; message: string }>
    warnings: Array<unknown>
  }
}

export interface DocumentInspectResponse {
  document_id: string
  filename: string
  file_type: string
  sheets: DocumentInspectionSheet[]
}

export interface ProcessDocumentResponse {
  message: string
  document_id: string
  total_rows: number
  valid_rows: number
  invalid_rows: number
  saved_transactions: number
  column_mapping: Record<string, string>
  errors: Array<{ row?: number | null; field?: string | null; message: string }>
}

export interface DocumentTransactionsResponse {
  document_id: string
  filename: string
  transaction_count: number
  transactions: Array<Record<string, unknown>>
  invalid_row_count: number
  processing_errors: Array<unknown>
}

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

export interface DocumentMetadata {
  id: string
  filename: string
  original_filename?: string
  file_type: SupportedUploadFileType
  document_type: string
  source: string
  status: string
  owner_id?: string
  uploaded_at?: string
  error_message?: string
}

export interface ApiValidationIssue {
  loc: Array<string | number>
  msg: string
  type: string
}

export type ApiErrorResponse = {
  detail: string | ApiValidationIssue[]
}

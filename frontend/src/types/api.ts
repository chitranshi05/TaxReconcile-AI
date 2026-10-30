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

export interface TransactionRecord {
  document_id?: string
  owner_id?: string
  transaction_date: string
  description?: string
  amount?: number | null
  debit?: number | null
  credit?: number | null
  balance?: number | null
  source_row?: number | null
  created_at?: string
  [key: string]: unknown
}

export interface DocumentTransactionsResponse {
  document_id: string
  filename: string
  transaction_count: number
  transactions: TransactionRecord[]
  invalid_row_count: number
  processing_errors: Array<unknown>
}

// ─── Anomaly Detection Types ───────────────────────────────────────

export interface AnomalyItem {
  transaction: TransactionRecord
  flags: string[]
  reasons: string[]
  severity: 'HIGH' | 'MEDIUM' | 'LOW' | string
  iqr_score?: number
}

export interface DuplicateGroup {
  group_id: string | number
  count: number
  canonical: TransactionRecord
  transactions: TransactionRecord[]
  match_keys?: string[]
}

export interface DocumentAnomaliesResponse {
  document_id: string
  filename: string
  total_transactions: number
  anomalous_transactions_count: number
  normal_transactions_count: number
  anomaly_rate: number
  flag_counts: Record<string, number>
  statistics: {
    debit?: Record<string, unknown>
    credit?: Record<string, unknown>
    amount?: Record<string, unknown>
    [key: string]: unknown
  }
  anomalies: AnomalyItem[]
  flagged_transactions: TransactionRecord[]
  notes?: string[]
  disclaimer?: string
}

export interface DocumentDuplicatesResponse {
  document_id: string
  filename: string
  total_transactions: number
  unique_count: number
  original_count: number
  duplicate_count: number
  duplicate_groups_count: number
  duplicates: TransactionRecord[]
  duplicate_groups: DuplicateGroup[]
  flagged_transactions: TransactionRecord[]
}

// ─── Reconciliation Types ──────────────────────────────────────────

export interface ReconciliationRequest {
  bank_document_id: string
  ledger_document_id: string
  date_tolerance_days?: number
  amount_tolerance?: number
}

export interface ReconciliationMatchPair {
  bank_transaction: TransactionRecord
  ledger_transaction: TransactionRecord
  match_type: 'EXACT' | 'FUZZY' | string
  confidence?: number
  date_diff_days?: number
  amount_diff?: number
}

export interface ReconciliationSummary {
  bank_total_transactions: number
  ledger_total_transactions: number
  matched_count: number
  bank_only_count: number
  ledger_only_count: number
  match_percentage: number
  bank_total_amount?: number
  ledger_total_amount?: number
  matched_total_amount?: number
  net_discrepancy?: number
}

export interface ReconciliationResult {
  reconciliation_id: string
  bank_document_id: string
  ledger_document_id: string
  bank_filename?: string
  ledger_filename?: string
  summary: ReconciliationSummary
  matches: ReconciliationMatchPair[]
  bank_only: TransactionRecord[]
  ledger_only: TransactionRecord[]
  created_at?: string
}

export interface ReconciliationListResponse {
  count: number
  reconciliations: ReconciliationResult[]
}

// ─── Tax Compliance Types ──────────────────────────────────────────

export interface TaxRuleConfig {
  section_80c_limit?: number
  section_80d_limit?: number
  section_80d_senior_limit?: number
  section_269st_cash_limit?: number
  [key: string]: unknown
}

export interface TaxRulesResponse {
  supported_financial_years: string[]
  rules_by_fy: Record<string, TaxRuleConfig>
}

export interface TaxFinding {
  rule_id: string
  section?: string
  severity: 'COMPLIANT' | 'WARNING' | 'BREACH' | 'INFO' | string
  title: string
  description: string
  amount?: number
  threshold?: number
  discrepancy?: number
  involved_transactions?: TransactionRecord[]
}

export interface TaxValidationSummary {
  status: 'COMPLIANT' | 'BREACH' | 'NEEDS_REVIEW' | string
  total_findings: number
  breaches_count: number
  warnings_count: number
  total_tax_exposure?: number
}

export interface DocumentTaxValidationResponse {
  document_id: string
  filename?: string
  transaction_count: number
  summary: TaxValidationSummary
  findings: TaxFinding[]
  findings_by_category?: Record<string, TaxFinding[]>
  disclaimer?: string
}

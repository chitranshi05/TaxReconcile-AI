import { requestJson } from './apiClient'

export interface TaxComplianceResult {
  status: string
  document_id: string
  filename: string
  total_transactions_audited: number
  total_findings: number
  summary: {
    financial_year: string
    assessment_year: string
    total_findings: number
    errors_count: number
    warnings_count: number
    info_count: number
    is_filing_ready: boolean
    tax_readiness_score: number
    findings_by_category_counts: Record<string, number>
  }
  findings: Array<{
    category: string
    severity: string
    rule_name: string
    description: string
    recommendation: string
    section_reference?: string
  }>
}

export function getTaxRules(): Promise<{
  supported_financial_years: string[]
  rules_by_fy: Record<string, Record<string, unknown>>
}> {
  return requestJson('/api/tax-validation/rules')
}

export function validateDocumentTaxCompliance(
  documentId: string,
  financialYear: string = '2024-25',
  declaredIncome?: Record<string, number>,
  claimedDeductions?: Record<string, number>,
): Promise<TaxComplianceResult> {
  return requestJson(`/api/tax-validation/documents/${documentId}/validate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      financial_year: financialYear,
      declared_income: declaredIncome || { salary: 0 },
      claimed_deductions: claimedDeductions || {},
    }),
  })
}

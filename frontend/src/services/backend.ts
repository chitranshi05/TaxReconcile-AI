import type { HealthResponse } from '../types/api'
import { requestJson } from './apiClient'

export function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/health')
}

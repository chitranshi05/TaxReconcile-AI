import type { DocumentUploadResponse } from '../types/api'
import { requestJson } from './apiClient'

export function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  return requestJson<DocumentUploadResponse>('/api/documents/upload', {
    method: 'POST',
    body: formData,
  })
}

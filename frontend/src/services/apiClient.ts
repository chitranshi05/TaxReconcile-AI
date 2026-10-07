import type { ApiErrorResponse, ApiValidationIssue } from '../types/api'

export class ApiError extends Error {
  readonly statusCode: number | null
  readonly responseBody?: unknown

  constructor(
    message: string,
    statusCode: number | null,
    responseBody?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
    this.statusCode = statusCode
    this.responseBody = responseBody
  }
}

function getApiBaseUrl(): string {
  const baseUrl = import.meta.env.VITE_API_BASE_URL?.trim()

  if (!baseUrl) {
    throw new Error(
      'VITE_API_BASE_URL is missing. Set it in frontend/.env.local.',
    )
  }

  return baseUrl.replace(/\/+$/, '')
}

function isValidationIssue(value: unknown): value is ApiValidationIssue {
  return (
    typeof value === 'object' &&
    value !== null &&
    'msg' in value &&
    typeof value.msg === 'string'
  )
}

function getErrorMessage(body: unknown, statusCode: number): string {
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const detail = (body as ApiErrorResponse).detail

    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const messages = detail.filter(isValidationIssue).map((issue) => issue.msg)
      if (messages.length > 0) return messages.join(' ')
    }
  }

  return `The backend request failed with status ${statusCode}.`
}

export async function requestJson<TResponse>(
  path: string,
  options: RequestInit = {},
): Promise<TResponse> {
  const baseUrl = getApiBaseUrl()
  const requestUrl = import.meta.env.DEV ? path : `${baseUrl}${path}`
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')

  let response: Response

  try {
    response = await fetch(requestUrl, { ...options, headers })
  } catch (error) {
    throw new ApiError(
      'Unable to reach the backend. Check VITE_API_BASE_URL and the server status.',
      null,
      error,
    )
  }

  const responseBody: unknown = await response.json().catch(() => undefined)

  if (!response.ok) {
    throw new ApiError(
      getErrorMessage(responseBody, response.status),
      response.status,
      responseBody,
    )
  }

  return responseBody as TResponse
}

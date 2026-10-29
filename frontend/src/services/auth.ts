import type { TokenResponse, UserResponse } from '../types/api'
import { requestJson, setAuthToken, getAuthToken } from './apiClient'

export async function register(
  name: string,
  email: string,
  password: string,
): Promise<UserResponse> {
  return requestJson<UserResponse>('/api/auth/register', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name, email, password }),
  })
}

export async function login(
  email: string,
  password: string,
): Promise<TokenResponse> {
  const data = await requestJson<TokenResponse>('/api/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  })

  if (data?.access_token) {
    setAuthToken(data.access_token)
  }

  return data
}

export function logout(): void {
  setAuthToken(null)
}

export async function getMe(): Promise<UserResponse> {
  return requestJson<UserResponse>('/api/auth/me')
}

export function isAuthenticated(): boolean {
  return Boolean(getAuthToken())
}


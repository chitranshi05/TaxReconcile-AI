import { requestJson } from './apiClient'

export interface AuthUser {
  id: string
  name: string
  email: string
  role: string
}

export async function loginUser(email: string, password: string): Promise<string> {
  const result = await requestJson<{ access_token: string; token_type: string }>('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  localStorage.setItem('token', result.access_token)
  return result.access_token
}

export async function registerUser(name: string, email: string, password: string): Promise<AuthUser> {
  const result = await requestJson<AuthUser>('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, password }),
  })
  return result
}

export async function getCurrentUser(): Promise<AuthUser> {
  return requestJson<AuthUser>('/api/auth/me')
}

export function logoutUser(): void {
  localStorage.removeItem('token')
  sessionStorage.removeItem('token')
}

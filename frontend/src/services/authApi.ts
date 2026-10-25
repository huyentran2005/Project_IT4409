import type { UserSummary } from '../types/task'
import { apiRequest } from './apiClient'

export interface LoginPayload {
  email: string
  password: string
}

export interface RegisterPayload extends LoginPayload {
  name: string
  phone?: string
}

export interface AuthResponse {
  accessToken: string
  refreshToken: string
  user: UserSummary
}

export type SsoProvider = 'google' | 'github'

export const authApi = {
  login(payload: LoginPayload) {
    return apiRequest<AuthResponse>('/api/auth/login', { method: 'POST', body: JSON.stringify(payload) })
  },
  register(payload: RegisterPayload) {
    return apiRequest<AuthResponse>('/api/auth/register', { method: 'POST', body: JSON.stringify(payload) })
  },
  getSsoUrl(provider: SsoProvider) {
    return `${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/api/auth/sso/${provider}`
  },
  getMe(token: string) {
    return apiRequest<UserSummary>('/api/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    })
  },
 logout(refreshToken?: string | null) {
    return apiRequest<void>('/api/auth/logout', {
      method: 'POST',
      body: JSON.stringify({ refreshToken: refreshToken ?? null }),
    })
  },
}


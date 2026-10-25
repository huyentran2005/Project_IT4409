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
  user: UserSummary
}

export type SsoProvider = 'google' | 'github'
//thêm kiểu dữ liệu ProfileResponse và ProfileUpdatePayload để sử dụng trong các API liên quan đến trang cá nhân
export interface ProfileResponse extends UserSummary {
  phone: string | null
}

export interface ProfileUpdatePayload {
  name?: string
  phone?: string | null
}

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
    return apiRequest<ProfileResponse>('/api/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    })
  },

  updateMe(token: string, payload: ProfileUpdatePayload) {
    return apiRequest<ProfileResponse>('/api/auth/me', {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    })
  },
  //phuong thuc phia client goi API de logout, la ham dau vao cua ham revoke_session trong file auth.py
  logout(refreshToken: string) {
    return apiRequest<void>('/api/auth/logout', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
  },
}


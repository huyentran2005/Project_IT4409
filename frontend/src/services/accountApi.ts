import { apiRequest } from './apiClient'

export interface ChangePasswordPayload {
  currentPassword?: string
  newPassword: string
  refreshToken?: string
}

export const accountApi = {
  changePassword(payload: ChangePasswordPayload) {
    return apiRequest<{ status: string }>('/api/auth/change-password', {
      method: 'POST', body: JSON.stringify(payload),
    })
  },
}

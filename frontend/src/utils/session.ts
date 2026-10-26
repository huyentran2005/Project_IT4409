import type { UserSummary } from '../types/task'

export const EMPTY_USER: UserSummary = {
  id: '',
  name: 'Người dùng',
  email: '',
  initials: 'ND',
  color: '#64748b',
}

export function getStoredUser(): UserSummary {
  try {
    const value = JSON.parse(localStorage.getItem('taskflow-current-user') ?? 'null') as Partial<UserSummary> | null
    if (value?.id && value.name && value.email && value.initials && value.color) {
      return value as UserSummary
    }
  } catch {
    // Session không hợp lệ sẽ dùng trạng thái người dùng rỗng.
  }
  return EMPTY_USER
}

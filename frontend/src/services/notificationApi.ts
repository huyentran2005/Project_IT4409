import { apiRequest } from './apiClient'

export interface AppNotification {
  id: string
  projectId: string | null
  taskId: string | null
  taskKey: string | null
  taskTitle: string | null
  projectName: string | null
  taskDeleted: boolean
  type: string
  title: string
  readAt: string | null
  createdAt: string
}

export interface NotificationPage {
  items: AppNotification[]
  unreadCount: number
  hasMore: boolean
}

export const notificationApi = {
  list(offset = 0) {
    return apiRequest<NotificationPage>(`/api/notifications?limit=20&offset=${offset}`)
  },
  read(id: string) {
    return apiRequest<AppNotification>(`/api/notifications/${id}/read`, { method: 'PATCH' })
  },
  readAll() {
    return apiRequest<void>('/api/notifications/read-all', { method: 'PATCH' })
  },
}

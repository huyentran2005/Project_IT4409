import type { BoardData, CreateTaskInput, Task, TaskComment, TaskPropertiesUpdate, TaskStatus, TimesheetEntry } from '../types/task'
import { apiRequest } from './apiClient'

export const taskApi = {
  getBoard(projectId: string) {
    return apiRequest<BoardData>(`/api/projects/${projectId}/board`)
  },
  createTask(projectId: string, payload: CreateTaskInput & { status: TaskStatus }) {
    return apiRequest<Task>(`/api/projects/${projectId}/tasks`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  updateTask(taskId: string, payload: Partial<Task>) {
    return apiRequest<Task>(`/api/tasks/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },
  deleteTask(taskId: string) {
    return apiRequest<void>(`/api/tasks/${taskId}`, {
      method: 'DELETE',
    })
  },
  moveTask(taskId: string, status: TaskStatus, position: number, reviewerId?: string, properties?: TaskPropertiesUpdate) {
    return apiRequest<Task>(`/api/tasks/${taskId}/move`, {
      method: 'PATCH',
      body: JSON.stringify({ status, position, reviewerId, ...properties }),
    })
  },
  setReviewer(taskId: string, reviewerId: string) {
    return apiRequest<Task>(`/api/tasks/${taskId}/reviewer`, {
      method: 'PATCH',
      body: JSON.stringify({ reviewerId }),
    })
  },
  updateProperties(taskId: string, payload: TaskPropertiesUpdate) {
    return apiRequest<Task>(`/api/tasks/${taskId}/properties`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },
  getTimesheets(taskId: string) {
    return apiRequest<TimesheetEntry[]>(`/api/tasks/${taskId}/timesheets`)
  },
  logTime(taskId: string, payload: Omit<TimesheetEntry, 'id' | 'user' | 'minutes'>) {
    return apiRequest<TimesheetEntry>(`/api/tasks/${taskId}/timesheets`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  getComments(taskId: string) {
    return apiRequest<TaskComment[]>(`/api/tasks/${taskId}/comments`)
  },
  addComment(taskId: string, body: string) {
    return apiRequest<TaskComment>(`/api/tasks/${taskId}/comments`, {
      method: 'POST', body: JSON.stringify({ body }),
    })
  },
}

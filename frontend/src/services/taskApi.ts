import type { BoardData, CreateTaskInput, Task, TaskComment, TaskPropertiesUpdate, TaskStatus, TimesheetEntry, TimesheetInput, TimesheetList, TimesheetSummary } from '../types/task'
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
  logTime(taskId: string, payload: TimesheetInput) {
    return apiRequest<TimesheetEntry>(`/api/tasks/${taskId}/timesheets`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  deleteTimesheet(entryId: string) {
    return apiRequest<void>(`/api/timesheets/${entryId}`, { method: 'DELETE' })
  },
  listMyTimesheets(filters: { dateFrom?: string; dateTo?: string; overtimeOnly?: boolean } = {}) {
    const params = new URLSearchParams()
    if (filters.dateFrom) params.set('date_from', filters.dateFrom)
    if (filters.dateTo) params.set('date_to', filters.dateTo)
    if (filters.overtimeOnly) params.set('overtime_only', 'true')
    const query = params.toString()
    return apiRequest<TimesheetList>(`/api/timesheets${query ? `?${query}` : ''}`)
  },
  getTimesheetSummary() {
    return apiRequest<TimesheetSummary>('/api/timesheets/summary')
  },
  getComments(taskId: string) {
    return apiRequest<TaskComment[]>(`/api/tasks/${taskId}/comments`)
  },
  addComment(taskId: string, body: string) {
    return apiRequest<TaskComment>(`/api/tasks/${taskId}/comments`, {
      method: 'POST', body: JSON.stringify({ body }),
    })
  },
  deleteComment(commentId: string) {
    return apiRequest<void>(`/api/comments/${commentId}`, { method: 'DELETE' })
  },
}

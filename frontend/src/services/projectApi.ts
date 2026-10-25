import type { ActivityLog, ProjectDocument, ProjectRole, RolePermission } from '../types/project'
import type { CreateProjectInput, ProjectSummary, UserSummary } from '../types/task'
import { API_BASE_URL, ApiError, apiRequest, authHeaders, readErrorMessage } from './apiClient'

export const projectApi = {
  createProject(payload: CreateProjectInput) {
    return apiRequest<ProjectSummary>('/api/projects', {
      method: 'POST', body: JSON.stringify(payload),
    })
  },
  getProject(projectId: string) {
    return apiRequest<ProjectSummary>(`/api/projects/${projectId}`)
  },
  getMembers(projectId: string) {
    return apiRequest<UserSummary[]>(`/api/projects/${projectId}/members`)
  },
  getDocuments(projectId: string) {
    return apiRequest<ProjectDocument[]>(`/api/projects/${projectId}/documents`)
  },
  getActivityLogs(projectId: string) {
    return apiRequest<ActivityLog[]>(`/api/projects/${projectId}/activity-logs`)
  },
  updateRolePermissions(projectId: string, permissions: RolePermission[]) {
    return apiRequest<RolePermission[]>(`/api/projects/${projectId}/role-permissions`, {
      method: 'PUT', body: JSON.stringify({ permissions }),
    })
  },
  async uploadDocument(projectId: string, file: File): Promise<ProjectDocument> {
    const form = new FormData()
    form.append('file', file)
    // Không đặt Content-Type: trình duyệt tự thêm boundary cho multipart
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/documents`, {
      method: 'POST', headers: authHeaders(), body: form,
    })
    if (!response.ok) throw new ApiError(response.status, await readErrorMessage(response))
    return response.json() as Promise<ProjectDocument>
  },
  async downloadDocument(projectId: string, document: ProjectDocument): Promise<void> {
    // Cần header Authorization nên không dùng được <a href> trực tiếp
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/documents/${document.id}/download`, { headers: authHeaders() })
    if (!response.ok) throw new ApiError(response.status, await readErrorMessage(response))
    const url = URL.createObjectURL(await response.blob())
    const link = window.document.createElement('a')
    link.href = url
    link.download = document.name
    link.click()
    URL.revokeObjectURL(url)
  },
  deleteDocument(projectId: string, documentId: string) {
    return apiRequest<void>(`/api/projects/${projectId}/documents/${documentId}`, { method: 'DELETE' })
  },
  updateMemberRole(projectId: string, userId: string, role: ProjectRole) {
    return apiRequest<void>(`/api/projects/${projectId}/members/${userId}/role`, {
      method: 'PATCH', body: JSON.stringify({ role }),
    })
  },
}

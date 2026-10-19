import type { ActivityLog, ProjectDocument, ProjectRole, RolePermission } from '../types/project'
import type { CreateProjectInput, ProjectSummary, UserSummary } from '../types/task'
import { apiRequest } from './apiClient'

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
  updateMemberRole(projectId: string, userId: string, role: ProjectRole) {
    return apiRequest<void>(`/api/projects/${projectId}/members/${userId}/role`, {
      method: 'PATCH', body: JSON.stringify({ role }),
    })
  },
}

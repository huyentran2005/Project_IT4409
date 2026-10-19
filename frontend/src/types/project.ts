export type ProjectRole = 'owner' | 'manager' | 'member' | 'viewer'

export interface RolePermission {
  key: string
  label: string
  description: string
  roles: ProjectRole[]
}

export interface ProjectDocument {
  id: string
  name: string
  type: string
  size: string
  updatedAt: string
  updatedBy: string
}

export interface ActivityLog {
  id: string
  actor: string
  actorInitials: string
  action: 'created' | 'updated' | 'deleted' | 'logged_time' | 'meeting_created'
  entityType: 'task' | 'timesheet' | 'member' | 'document' | 'meeting'
  description: string
  createdAt: string
  changeCount: number
}

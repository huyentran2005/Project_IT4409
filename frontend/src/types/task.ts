export type TaskStatus = 'backlog' | 'in-progress' | 'review' | 'done'
export type TaskPriority = 'urgent' | 'high' | 'medium' | 'low'
export type TaskType = 'epic' | 'story' | 'task' | 'bug'

export interface UserSummary {
  id: string
  name: string
  email: string
  avatarUrl?: string
  initials: string
  color: string
}

export interface TaskLabel {
  id: string
  name: string
  color: string
}

export interface TimesheetEntry {
  id: string
  user: UserSummary
  startTime: string
  endTime: string
  minutes: number
  note: string
  isOvertime?: boolean
  /** Ngày làm việc (yyyy-mm-dd, giờ Việt Nam). */
  date?: string
  taskId?: string
  taskKey?: string
  taskTitle?: string
  projectId?: string
  projectName?: string
}

/** Nhập theo (startTime + endTime) hoặc (date + hours). */
export interface TimesheetInput {
  startTime?: string
  endTime?: string
  date?: string
  hours?: number
  isOvertime?: boolean
  note: string
}

export interface TimesheetList {
  entries: TimesheetEntry[]
  totalMinutes: number
  overtimeMinutes: number
}

export interface TimesheetSummary {
  todayMinutes: number
  weekMinutes: number
  weekOvertimeMinutes: number
  missingDays: number
  missingDates: string[]
}

export interface TaskComment {
  id: string
  author: UserSummary
  body: string
  createdAt: string
  parentId?: string | null
}

export interface Task {
  id: string
  key: string
  title: string
  description: string
  type: TaskType
  priority: TaskPriority
  status: TaskStatus
  assignees: UserSummary[]
  reviewer?: UserSummary
  /** Tương thích tạm thời với API cũ chỉ trả về một người thực hiện. */
  assignee?: UserSummary
  labels: TaskLabel[]
  startDate: string
  endDate: string
  completedAt?: string
  overdueReason?: string
  acceptanceResult?: string
  storyPoints?: number
  comments: number
  attachments: number
  checklist: { completed: number; total: number }
  timesheets: TimesheetEntry[]
  commentItems: TaskComment[]
}

export interface CreateTaskInput {
  title: string
  description: string
  type: TaskType
  priority: TaskPriority
  startDate: string
  endDate: string
  assigneeIds: string[]
}

export interface TaskPropertiesUpdate {
  description: string
  priority: TaskPriority
  assigneeIds: string[]
  startDate: string
  endDate: string
  overdueReason: string
  acceptanceResult: string
}

export const getTaskAssignees = (task: Pick<Task, 'assignees' | 'assignee'>) =>
  task.assignees?.length ? task.assignees : task.assignee ? [task.assignee] : []

export interface BoardColumn {
  id: TaskStatus
  title: string
  accent: string
  limit?: number
  tasks: Task[]
}

export interface ProjectSummary {
  id: string
  key: string
  name: string
  description: string
  color: string
  progress: number
  members: UserSummary[]
}

export interface CreateProjectInput {
  name: string
  key: string
  description: string
  color: string
}

export interface BoardData {
  project: ProjectSummary
  columns: BoardColumn[]
}

export type BoardFilter = 'all' | 'mine' | 'priority' | 'due-soon'

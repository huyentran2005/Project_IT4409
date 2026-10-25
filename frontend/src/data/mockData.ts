import type { BoardData, TaskStatus, UserSummary } from '../types/task'
import type { ActivityLog, ProjectDocument } from '../types/project'
import type { Meeting } from '../types/meeting'

export const currentUser: UserSummary = {
  id: '71582378-5610-4306-bab5-71a3d94ba648', name: 'Huyền Trần', email: 'huyentranht05@gmail.com', avatarUrl: 'https://lh3.googleusercontent.com/a/ACg8ocKGEtGQEknVWjoyQX0i4KUt8nDV3T6yRrvtJWeTJhXSNfwQEVw=s96-c', initials: 'HT', color: '#5B5CE2',
}

export const mockNavigation = [
  { icon: 'grid', label: 'Tổng quan', badge: undefined },
  { icon: 'check', label: 'Công việc của tôi', badge: undefined },
]

export const mockNotifications: {
  id: string
  title: string
  time: string
  unread: boolean
}[] = []

export const mockStatusOptions: { id: TaskStatus; label: string }[] = [
  { id: 'backlog', label: 'Cần làm' },
  { id: 'in-progress', label: 'Đang làm' },
  { id: 'review', label: 'Đang duyệt' },
  { id: 'done', label: 'Hoàn thành' },
]

export const mockProjectDocuments: ProjectDocument[] = []

export const mockMeetings: Meeting[] = []

export const mockActivityLogs: ActivityLog[] = []

export const initialBoard: BoardData = {
  project: {
    id: '61f53fef-bd73-41dc-937a-f715c7db38aa', key: 'TFDEMO', name: 'TaskFlow Demo',
    description: 'Dự án dùng để kiểm tra thành viên và phân quyền',
    color: '#5B5CE2', progress: 0, members: [],
  },
  columns: [
    {
      id: 'backlog', title: 'Cần làm', accent: '#64748b',
      tasks: [],
    },
    {
      id: 'in-progress', title: 'Đang làm', accent: '#2563eb',
      tasks: [],
    },
    {
      id: 'review', title: 'Đang duyệt', accent: '#d97706',
      tasks: [],
    },
    {
      id: 'done', title: 'Hoàn thành', accent: '#0f9f8f',
      tasks: [],
    },
  ],
}

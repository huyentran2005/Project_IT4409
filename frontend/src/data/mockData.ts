import type { BoardData, Task, TaskStatus, UserSummary } from '../types/task'
import type { ActivityLog, ProjectDocument, ProjectRole, RolePermission } from '../types/project'
import type { Meeting } from '../types/meeting'

export const currentUser: UserSummary = {
  id: 'u-01', name: 'Minh Anh', email: 'minhanh@taskflow.local', initials: 'MA', color: '#4f46e5',
}

const users: UserSummary[] = [
  currentUser,
  { id: 'u-02', name: 'Hoàng Nam', email: 'hoangnam@taskflow.local', initials: 'HN', color: '#0f9f8f' },
  { id: 'u-03', name: 'Lan Chi', email: 'lanchi@taskflow.local', initials: 'LC', color: '#e06c46' },
  { id: 'u-04', name: 'Tuấn Vũ', email: 'tuanvu@taskflow.local', initials: 'TV', color: '#8b5cf6' },
]

export const mockNavigation = [
  { icon: 'grid', label: 'Tổng quan' },
  { icon: 'check', label: 'Công việc của tôi', badge: '6' },
]

export const mockProjects = [
  { name: 'TaskFlow Web App', color: '#5b5ce2', active: true },
]

export const mockNotifications = [
  { id: 'notification-01', title: 'TF-119 vừa được cập nhật', time: '10 phút trước', unread: true },
  { id: 'notification-02', title: 'Bạn được mời vào Sprint review', time: '1 giờ trước', unread: true },
  { id: 'notification-03', title: 'TF-109 đã hoàn thành', time: 'Hôm qua', unread: false },
]

export const mockStatusOptions: { id: TaskStatus; label: string }[] = [
  { id: 'backlog', label: 'Cần làm' },
  { id: 'in-progress', label: 'Đang làm' },
  { id: 'review', label: 'Đang duyệt' },
  { id: 'done', label: 'Hoàn thành' },
]

export const mockMemberRoles: Record<string, ProjectRole> = {
  'u-01': 'owner', 'u-02': 'manager', 'u-03': 'member', 'u-04': 'viewer',
}

export const mockRolePermissions: RolePermission[] = [
  { key: 'project.manage', label: 'Quản lý dự án', description: 'Sửa thông tin và cấu hình dự án', roles: ['owner'] },
  { key: 'member.manage', label: 'Quản lý thành viên', description: 'Mời, đổi vai trò và xóa thành viên', roles: ['owner', 'manager'] },
  { key: 'task.manage', label: 'Quản lý công việc', description: 'Tạo, sửa và di chuyển công việc', roles: ['owner', 'manager', 'member'] },
  { key: 'document.manage', label: 'Quản lý tài liệu', description: 'Tải lên, cập nhật và xóa tài liệu', roles: ['owner', 'manager', 'member'] },
  { key: 'project.view', label: 'Xem dự án', description: 'Xem bảng, thành viên và tài liệu', roles: ['owner', 'manager', 'member', 'viewer'] },
]

export const mockProjectDocuments: ProjectDocument[] = [
  { id: 'doc-01', name: 'Đặc tả yêu cầu TaskFlow.pdf', type: 'PDF', size: '2.4 MB', updatedAt: '2026-10-15', updatedBy: 'Minh Anh' },
  { id: 'doc-02', name: 'Quy chuẩn thiết kế UI.fig', type: 'FIG', size: '8.1 MB', updatedAt: '2026-10-14', updatedBy: 'Lan Chi' },
  { id: 'doc-03', name: 'Tài liệu API v1.docx', type: 'DOCX', size: '940 KB', updatedAt: '2026-10-12', updatedBy: 'Hoàng Nam' },
]

export const mockMeetings: Meeting[] = [
  { id: 'meet-01', projectId: 'p-01', title: 'Daily stand-up', date: '2026-10-16', startTime: '09:00', endTime: '09:20', location: 'Google Meet', meetingUrl: 'https://meet.google.com/', description: 'Cập nhật tiến độ và blocker trong ngày.' },
  { id: 'meet-02', projectId: 'p-01', title: 'Sprint review', date: '2026-10-19', startTime: '15:00', endTime: '16:00', location: 'Microsoft Teams', meetingUrl: 'https://teams.microsoft.com/', description: 'Demo các hạng mục đã hoàn thành trong sprint.' },
]

export const mockActivityLogs: ActivityLog[] = [
  { id: 'log-01', actor: 'Minh Anh', actorInitials: 'MA', action: 'updated', entityType: 'task', description: 'đã cập nhật công việc · Xây dựng giao diện bảng Kanban', createdAt: '2026-10-16T15:10:00+07:00', changeCount: 2 },
  { id: 'log-02', actor: 'Hoàng Nam', actorInitials: 'HN', action: 'logged_time', entityType: 'timesheet', description: 'đã tạo mới bản ghi thời gian · TF-121', createdAt: '2026-10-16T13:25:00+07:00', changeCount: 1 },
  { id: 'log-03', actor: 'Lan Chi', actorInitials: 'LC', action: 'updated', entityType: 'task', description: 'đã cập nhật công việc · Tối ưu thanh điều hướng mobile', createdAt: '2026-10-16T10:45:00+07:00', changeCount: 3 },
  { id: 'log-04', actor: 'Tuấn Vũ', actorInitials: 'TV', action: 'created', entityType: 'document', description: 'đã tải lên tài liệu · Tài liệu API v1.docx', createdAt: '2026-10-15T16:20:00+07:00', changeCount: 1 },
  { id: 'log-05', actor: 'Minh Anh', actorInitials: 'MA', action: 'meeting_created', entityType: 'meeting', description: 'đã tạo meeting · Sprint review', createdAt: '2026-10-15T09:15:00+07:00', changeCount: 1 },
]

const labels = {
  design: { id: 'l-01', name: 'Thiết kế', color: '#8b5cf6' },
  frontend: { id: 'l-02', name: 'Frontend', color: '#2563eb' },
  backend: { id: 'l-03', name: 'Backend', color: '#0f9f8f' },
  research: { id: 'l-04', name: 'Nghiên cứu', color: '#d97706' },
}

const task = (value: Partial<Task> & Pick<Task, 'id' | 'key' | 'title' | 'status'>): Task => ({
  description: 'Nội dung công việc sẽ được cập nhật trong phiên lập kế hoạch tiếp theo.',
  type: 'task', priority: 'medium', labels: [], comments: 0, attachments: 0,
  checklist: { completed: 0, total: 0 }, assignees: value.assignees ?? (value.assignee ? [value.assignee] : []),
  startDate: '2026-10-16', endDate: '2026-10-23', timesheets: [], commentItems: [],
  ...value,
})

export const initialBoard: BoardData = {
  project: {
    id: 'p-01', key: 'TF', name: 'TaskFlow Web App',
    description: 'Nền tảng quản lý công việc cho đội ngũ sản phẩm',
    color: '#5b5ce2', progress: 64, members: users,
  },
  columns: [
    {
      id: 'backlog', title: 'Cần làm', accent: '#64748b', limit: 8,
      tasks: [
        task({ id: 't-01', key: 'TF-124', title: 'Thiết kế luồng tạo dự án mới', status: 'backlog', type: 'story', priority: 'high', assignee: users[2], labels: [labels.design], storyPoints: 5, comments: 3, attachments: 2, checklist: { completed: 2, total: 6 }, startDate: '2026-10-18', endDate: '2026-10-20' }),
        task({ id: 't-02', key: 'TF-128', title: 'Nghiên cứu bộ lọc nâng cao', status: 'backlog', assignee: users[1], labels: [labels.research], storyPoints: 3, comments: 2, startDate: '2026-10-19', endDate: '2026-10-24' }),
        task({ id: 't-03', key: 'TF-131', title: 'Chuẩn hóa thông báo trong ứng dụng', status: 'backlog', priority: 'low', labels: [labels.frontend], storyPoints: 2, attachments: 1, startDate: '2026-10-22', endDate: '2026-10-26' }),
      ],
    },
    {
      id: 'in-progress', title: 'Đang làm', accent: '#2563eb', limit: 4,
      tasks: [
        task({
          id: 't-04', key: 'TF-119', title: 'Xây dựng giao diện bảng Kanban', status: 'in-progress', type: 'story', priority: 'urgent', assignees: [currentUser, users[2]],
          labels: [labels.frontend], storyPoints: 8, comments: 7, attachments: 3, checklist: { completed: 5, total: 8 }, startDate: '2026-10-14', endDate: '2026-10-18',
          description: 'Hoàn thiện board kéo thả, trạng thái trống và trải nghiệm responsive cho màn hình nhỏ.',
          timesheets: [
            { id: 'ts-01', user: currentUser, startTime: '2026-10-14T08:30:00+07:00', endTime: '2026-10-14T11:00:00+07:00', minutes: 150, note: 'Dựng layout và các cột Kanban' },
            { id: 'ts-02', user: currentUser, startTime: '2026-10-15T13:30:00+07:00', endTime: '2026-10-15T15:15:00+07:00', minutes: 105, note: 'Xử lý kéo thả và responsive' },
          ],
          commentItems: [
            { id: 'comment-01', author: users[2], body: 'Mình đã cập nhật lại spacing theo bản thiết kế mới.', createdAt: '2026-10-15T16:20:00+07:00' },
            { id: 'comment-02', author: currentUser, body: 'Đã xử lý responsive, nhờ mọi người kiểm tra lại trên mobile.', createdAt: '2026-10-16T09:10:00+07:00' },
          ],
        }),
        task({ id: 't-05', key: 'TF-121', title: 'API cập nhật trạng thái công việc', status: 'in-progress', priority: 'high', assignee: users[1], labels: [labels.backend], storyPoints: 5, comments: 4, checklist: { completed: 3, total: 5 }, startDate: '2026-10-15', endDate: '2026-10-19', timesheets: [{ id: 'ts-03', user: users[1], startTime: '2026-10-15T09:00:00+07:00', endTime: '2026-10-15T12:00:00+07:00', minutes: 180, note: 'Thiết kế request và transaction cập nhật trạng thái' }] }),
        task({ id: 't-06', key: 'TF-130', title: 'Tối ưu thanh điều hướng mobile', status: 'in-progress', assignee: users[2], labels: [labels.frontend, labels.design], storyPoints: 3, comments: 1, startDate: '2026-10-16', endDate: '2026-10-21' }),
      ],
    },
    {
      id: 'review', title: 'Đang duyệt', accent: '#d97706', limit: 3,
      tasks: [
        task({ id: 't-07', key: 'TF-116', title: 'Cập nhật quyền thành viên dự án', status: 'review', type: 'story', priority: 'high', assignee: users[3], reviewer: currentUser, labels: [labels.backend], storyPoints: 5, comments: 8, attachments: 1, checklist: { completed: 5, total: 5 }, startDate: '2026-10-12', endDate: '2026-10-17', timesheets: [{ id: 'ts-04', user: users[3], startTime: '2026-10-13T08:00:00+07:00', endTime: '2026-10-13T11:30:00+07:00', minutes: 210, note: 'Cài đặt project roles và kiểm tra quyền' }] }),
        task({ id: 't-08', key: 'TF-123', title: 'Kiểm tra accessibility cho task card', status: 'review', assignee: currentUser, reviewer: users[1], labels: [labels.frontend], storyPoints: 2, comments: 3, startDate: '2026-10-14', endDate: '2026-10-18' }),
      ],
    },
    {
      id: 'done', title: 'Hoàn thành', accent: '#0f9f8f',
      tasks: [
        task({ id: 't-09', key: 'TF-109', title: 'Thiết lập cấu trúc React + TypeScript', status: 'done', priority: 'high', assignee: currentUser, labels: [labels.frontend], storyPoints: 3, comments: 2, checklist: { completed: 4, total: 4 }, startDate: '2026-10-08', endDate: '2026-10-10', completedAt: '2026-10-10T16:30:00+07:00', timesheets: [{ id: 'ts-05', user: currentUser, startTime: '2026-10-09T08:15:00+07:00', endTime: '2026-10-09T10:15:00+07:00', minutes: 120, note: 'Khởi tạo Vite và cấu trúc thư mục' }] }),
        task({ id: 't-10', key: 'TF-112', title: 'Xây dựng hệ thống màu và typography', status: 'done', assignee: users[2], labels: [labels.design], storyPoints: 3, attachments: 4, startDate: '2026-10-09', endDate: '2026-10-12', completedAt: '2026-10-12T14:00:00+07:00' }),
      ],
    },
  ],
}

import { useEffect, useState } from 'react'
import type { BoardData, BoardFilter, Task, TaskStatus, UserSummary } from '../types/task'
import type { Meeting, MeetingDraft } from '../types/meeting'
import type { ProjectDocument } from '../types/project'
import { mockMeetings, mockProjectDocuments } from '../data/mockData'
import { meetingApi } from '../services/meetingApi'
import { projectApi } from '../services/projectApi'
import { BoardColumn } from '../components/board/BoardColumn'
import { CreateMeetingModal } from '../components/meetings/CreateMeetingModal'
import { ProjectSettingsDrawer } from '../components/projects/ProjectSettingsDrawer'
import { CalendarView } from '../components/views/CalendarView'
import { ProgressView } from '../components/views/ProgressView'
import { TaskListView } from '../components/views/TaskListView'
import { SystemLogView } from '../components/views/SystemLogView'
import { Avatar } from '../components/ui/Avatar'
import { Icon } from '../components/ui/Icon'

interface BoardPageProps {
  board: BoardData
  columns: BoardData['columns']
  filter: BoardFilter
  onFilter: (filter: BoardFilter) => void
  onOpenTask: (task: Task) => void
  onMoveTask: (taskId: string, status: TaskStatus) => void
  onDeleteTask: (taskId: string) => void
  onCreate: () => void
  onInviteMember: (member: UserSummary) => void
}

const filters: { id: BoardFilter; label: string }[] = [
  { id: 'all', label: 'Tất cả' }, { id: 'mine', label: 'Của tôi' },
  { id: 'priority', label: 'Ưu tiên cao' }, { id: 'due-soon', label: 'Sắp đến hạn' },
]

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false'

type ProjectView = 'board' | 'list' | 'calendar' | 'progress' | 'activity'

export function BoardPage({ board, columns, filter, onFilter, onOpenTask, onMoveTask, onDeleteTask, onCreate, onInviteMember }: BoardPageProps) {
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [meetingOpen, setMeetingOpen] = useState(false)
  const [meetingNotice, setMeetingNotice] = useState('')
  const [activeView, setActiveView] = useState<ProjectView>('board')
  const [meetings, setMeetings] = useState<Meeting[]>(() => {
    if (!USE_MOCKS) return []
    try {
      const stored = localStorage.getItem(`taskflow-meetings-${board.project.id}`)
      return stored ? JSON.parse(stored) as Meeting[] : mockMeetings
    } catch {
      return mockMeetings
    }
  })
  const [documents, setDocuments] = useState<ProjectDocument[]>(USE_MOCKS ? mockProjectDocuments : [])
  const [filtersOpen, setFiltersOpen] = useState(false)
  const total = board.columns.reduce((sum, column) => sum + column.tasks.length, 0)
  const done = board.columns.find((column) => column.id === 'done')?.tasks.length ?? 0
  const visibleTasks = columns.flatMap((column) => column.tasks)
  useEffect(() => {
    if (USE_MOCKS) localStorage.setItem(`taskflow-meetings-${board.project.id}`, JSON.stringify(meetings))
  }, [board.project.id, meetings])
  useEffect(() => {
    if (USE_MOCKS) return
    meetingApi.list(board.project.id).then(setMeetings).catch(() => setMeetings([]))
    projectApi.getDocuments(board.project.id).then(setDocuments).catch(() => setDocuments([]))
  }, [board.project.id])
  const uploadDocument = async (file: File) => {
    if (USE_MOCKS) {
      const type = file.name.split('.').pop()?.toUpperCase() ?? 'FILE'
      const size = `${Math.max(file.size / 1024 / 1024, .01).toFixed(2)} MB`
      setDocuments((current) => [{ id: `document-${Date.now()}`, name: file.name, type, size, updatedAt: new Date().toISOString(), updatedBy: 'Minh Anh' }, ...current])
      return
    }
    const created = await projectApi.uploadDocument(board.project.id, file)
    setDocuments((current) => [created, ...current])
  }
  const createMeeting = async (draft: MeetingDraft) => {
    // Chế độ thật: gọi API (lỗi được ném ra để modal hiển thị); chế độ mock: tạo cục bộ
    const meeting = USE_MOCKS ? { ...draft, id: `meeting-${Date.now()}`, projectId: board.project.id } : await meetingApi.create(board.project.id, draft)
    setMeetings((current) => [...current, meeting])
    setMeetingNotice(`Đã tạo “${meeting.title}” lúc ${meeting.startTime}, ngày ${new Intl.DateTimeFormat('vi-VN').format(new Date(meeting.date))}`)
    setActiveView('calendar')
  }
  return (
    <main className="page">
      <section className="project-hero">
        <div className="project-identity"><span className="project-icon" style={{ background: board.project.color }}>{board.project.key}</span><div><div className="eyebrow">DỰ ÁN PHẦN MỀM</div><h1>{board.project.name}</h1><p>{board.project.description}</p></div></div>
        <div className="project-summary">
          <div className="member-stack" onClick={() => setSettingsOpen(true)}>{board.project.members.slice(0, 4).map((member) => <Avatar user={member} size={32} key={member.id} />)}{board.project.members.length > 4 && <button>+{board.project.members.length - 4}</button>}</div>
          <button className="secondary-button" onClick={() => setSettingsOpen(true)}><Icon name="users" size={16} />Mời thành viên</button>
          <div className="progress-ring" style={{ '--progress': `${board.project.progress * 3.6}deg` } as React.CSSProperties}><span>{board.project.progress}%</span></div>
        </div>
      </section>

      <section className="view-tabs">
        <div className="view-tabs__main"><button className={activeView === 'board' ? 'active' : ''} onClick={() => setActiveView('board')}><Icon name="grid" size={17} />Bảng</button><button className={activeView === 'list' ? 'active' : ''} onClick={() => setActiveView('list')}><Icon name="list" size={17} />Danh sách</button><button className={activeView === 'calendar' ? 'active' : ''} onClick={() => setActiveView('calendar')}><Icon name="calendar" size={17} />Lịch</button><button className={activeView === 'progress' ? 'active' : ''} onClick={() => setActiveView('progress')}><Icon name="chart" size={17} />Tiến độ</button><button className="meeting-tab" onClick={() => setMeetingOpen(true)}><Icon name="video" size={17} />Tạo meeting</button><button className={activeView === 'activity' ? 'active' : ''} onClick={() => setActiveView('activity')}><Icon name="list" size={17} />Nhật ký hệ thống</button></div>
        <button className="project-settings-button" onClick={() => setSettingsOpen(true)}><Icon name="settings" size={17} />Cấu hình dự án</button>
      </section>

      {meetingNotice && <div className="meeting-notice"><Icon name="check" size={16} /><span>{meetingNotice}</span><button onClick={() => setMeetingNotice('')} aria-label="Đóng thông báo"><Icon name="close" size={14} /></button></div>}

      {activeView !== 'activity' && <section className="board-toolbar">
        <div className="filter-tabs">{filters.map((item) => <button className={filter === item.id ? 'active' : ''} onClick={() => onFilter(item.id)} key={item.id}>{item.label}</button>)}</div>
        <div className="board-stats"><span><strong>{total}</strong> công việc</span><span><strong>{done}</strong> hoàn thành</span><div className="filter-menu"><button className={`filter-button ${filtersOpen ? 'active' : ''}`} onClick={() => setFiltersOpen((value) => !value)}><Icon name="filter" size={16} />Bộ lọc</button>{filtersOpen && <div className="filter-popover"><strong>Lọc công việc</strong>{filters.map((item) => <button className={filter === item.id ? 'active' : ''} onClick={() => { onFilter(item.id); setFiltersOpen(false) }} key={item.id}>{item.label}<span>{filter === item.id ? '✓' : ''}</span></button>)}</div>}</div></div>
      </section>}

      {activeView === 'board' && <section className="board" aria-label="Bảng Kanban">{columns.map((column) => <BoardColumn column={column} onOpenTask={onOpenTask} onMoveTask={onMoveTask} onDeleteTask={onDeleteTask} onQuickAdd={() => onCreate()} key={column.id} />)}</section>}
      {activeView === 'list' && <TaskListView tasks={visibleTasks} onOpenTask={onOpenTask} />}
      {activeView === 'calendar' && <CalendarView tasks={visibleTasks} meetings={meetings} onOpenTask={onOpenTask} />}
      {activeView === 'progress' && <ProgressView columns={columns} tasks={visibleTasks} />}
      {activeView === 'activity' && <SystemLogView />}
      {settingsOpen && <ProjectSettingsDrawer project={board.project} documents={documents} onInvite={onInviteMember} onUpload={uploadDocument} onDownload={USE_MOCKS ? undefined : (document) => projectApi.downloadDocument(board.project.id, document)} onClose={() => setSettingsOpen(false)} />}
      {meetingOpen && <CreateMeetingModal project={board.project} onClose={() => setMeetingOpen(false)} onCreate={createMeeting} />}
    </main>
  )
}

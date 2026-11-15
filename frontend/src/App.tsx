import { useState, useEffect } from 'react'

import './styles/index.css'
import { AppSidebar } from './components/layout/AppSidebar'
import { TopBar } from './components/layout/TopBar'
import { CreateTaskModal } from './components/tasks/CreateTaskModal'
import { TaskDrawer } from './components/tasks/TaskDrawer'
import { CreateProjectModal } from './components/projects/CreateProjectModal'
import { useBoard } from './hooks/useBoard'
import { BoardPage } from './pages/BoardPage'
import { AuthPage } from './pages/AuthPage'
import { MyTasksPage } from './pages/MyTasksPage'
import { OverviewPage } from './pages/OverviewPage'
import { ProfilePage } from './pages/ProfilePage'
import { InvitationPage } from './pages/InvitationPage'
import { authApi, type LoginPayload, type RegisterPayload, type SsoProvider } from './services/authApi'
import { taskApi } from './services/taskApi'
import type { AppNotification } from './services/notificationApi'
import { getTaskAssignees, type Task, type TaskPropertiesUpdate, type TaskStatus, type TimeEntryInput, type UserSummary } from './types/task'

function App() {
  const [authenticated, setAuthenticated] = useState(() => localStorage.getItem('taskflow-authenticated') === 'true')
  const { board, projects, columns, query, setQuery, filter, setFilter, loading, selectProject, loadProject, createProject, moveTask, addTask, deleteTask, updateProjectMembers, logTime, addComment, updateReviewer, updateProperties } = useBoard('p-01', authenticated)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [pendingTaskMove, setPendingTaskMove] = useState<{ taskId: string; status: TaskStatus } | null>(null)
  const [creating, setCreating] = useState(false)
  const [creatingProject, setCreatingProject] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarHidden, setSidebarHidden] = useState(() => localStorage.getItem('taskflow-sidebar-hidden') === 'true')
  const [dark, setDark] = useState(false)
  const [activeSection, setActiveSection] = useState('Tổng quan')
  const invitationMatch = window.location.pathname.match(/^\/invitations\/([^/]+)$/)
  const invitationToken = invitationMatch ? decodeURIComponent(invitationMatch[1]) : null

  const isTaskOverdue = (task: Task) => {
    const reference = task.completedAt ? new Date(task.completedAt) : new Date()
    return reference > new Date(`${task.endDate}T23:59:59`)
  }
  const getTaskProperties = (task: Task): TaskPropertiesUpdate => ({
    description: task.description,
    priority: task.priority,
    assigneeIds: getTaskAssignees(task).map((member) => member.id),
    startDate: task.startDate,
    endDate: task.endDate,
    overdueReason: task.overdueReason ?? '',
    acceptanceResult: task.acceptanceResult ?? '',
  })

  const setDesktopSidebarHidden = (hidden: boolean) => {
    localStorage.setItem('taskflow-sidebar-hidden', String(hidden))
    setSidebarHidden(hidden)
  }

  const finishAuthentication = () => {
    localStorage.setItem('taskflow-authenticated', 'true')
    setAuthenticated(true)
  }

  const authenticate = async (data: { mode: 'login' | 'register'; name?: string; email: string; phone?: string; password: string }) => {
    const response = data.mode === 'login'
      ? await authApi.login({ email: data.email, password: data.password } satisfies LoginPayload)
      : await authApi.register({ name: data.name ?? '', email: data.email, phone: data.phone ?? '', password: data.password } satisfies RegisterPayload)
    localStorage.setItem('taskflow-token', response.accessToken)
    localStorage.setItem('taskflow-refresh-token', response.refreshToken)
    localStorage.setItem('taskflow-current-user', JSON.stringify(response.user))
    finishAuthentication()
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')
    const refreshToken = params.get('refresh_token')
    const error = params.get('error')

    if (error) {
      alert(`Đăng nhập thất bại: ${decodeURIComponent(error)}`)
      window.history.replaceState({}, '', '/')
      return
    }

    if (token) {
      localStorage.setItem('taskflow-token', token)
      if (refreshToken) {
        localStorage.setItem('taskflow-refresh-token', refreshToken)
      }

      authApi
        .getMe(token)
        .then((user) => {
          localStorage.setItem('taskflow-current-user', JSON.stringify(user))
          finishAuthentication()
        })
        .catch(() => {
          finishAuthentication()
        })
        .finally(() => {
          const pendingInvitation = localStorage.getItem('taskflow-pending-invitation')
          if (pendingInvitation) {
            localStorage.removeItem('taskflow-pending-invitation')
            window.history.replaceState({}, '', `/invitations/${encodeURIComponent(pendingInvitation)}`)
          } else {
            window.history.replaceState({}, '', '/')
          }
        })
    }
  }, [])

  const authenticateWithSso = (provider: SsoProvider) => {
    if (invitationToken) {
      localStorage.setItem('taskflow-pending-invitation', invitationToken)
    }
    window.location.assign(authApi.getSsoUrl(provider))
  }


  const logout = async () => {
    const refreshToken = localStorage.getItem('taskflow-refresh-token')

    try {
      if (!refreshToken) {
        throw new Error('Missing refresh token')
      }

      await authApi.logout(refreshToken)
    } catch {
      alert(
        'Chưa xác nhận được việc thu hồi phiên trên máy chủ. ' +
        'Dữ liệu đăng nhập trên trình duyệt sẽ được xóa.'
      )
    } finally {
      localStorage.removeItem('taskflow-authenticated')
      localStorage.removeItem('taskflow-token')
      localStorage.removeItem('taskflow-refresh-token')
      localStorage.removeItem('taskflow-current-user')
      setAuthenticated(false)
    }
  }

  const saveSelectedTask = async (save: () => Promise<Task>) => {
    try {
      const saved = await save()
      setSelectedTask((current) => current?.id === saved.id ? saved : current)
      return true
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Không thể lưu công việc. Vui lòng thử lại.')
      return false
    }
  }
  const moveSelectedTask = async (status: TaskStatus) => {
    if (!selectedTask || selectedTask.status === status) return false
    const needsReviewer = status === 'review' && !selectedTask.reviewer
    const needsOverdueReason = isTaskOverdue(selectedTask) && !selectedTask.overdueReason?.trim()
    if (needsReviewer || needsOverdueReason) {
      setPendingTaskMove({ taskId: selectedTask.id, status })
      return false
    }
    const saved = await saveSelectedTask(() => moveTask(selectedTask.id, status))
    if (saved) setPendingTaskMove(null)
    return saved
  }
  const moveBoardTask = async (taskId: string, status: TaskStatus) => {
    const task = board.columns.flatMap((column) => column.tasks).find((item) => item.id === taskId)
    if (!task || task.status === status) return
    const needsReviewer = status === 'review' && !task.reviewer
    const needsOverdueReason = isTaskOverdue(task) && !task.overdueReason?.trim()
    if (needsReviewer || needsOverdueReason) {
      setSelectedTask(task)
      setPendingTaskMove({ taskId: task.id, status })
      return
    }
    await saveSelectedTask(() => moveTask(taskId, status))
  }
  const changeReviewer = async (reviewer: UserSummary) => {
    if (!selectedTask) return false
    const pendingMove = pendingTaskMove?.taskId === selectedTask.id ? pendingTaskMove : null
    const stillNeedsOverdueReason = isTaskOverdue(selectedTask) && !selectedTask.overdueReason?.trim()
    const canFinishMove = pendingMove && !stillNeedsOverdueReason
    const saved = await saveSelectedTask(() => canFinishMove
      ? moveTask(selectedTask.id, pendingMove.status, reviewer, getTaskProperties(selectedTask))
      : updateReviewer(selectedTask.id, reviewer))
    if (saved && canFinishMove) setPendingTaskMove(null)
    return saved
  }
  const changeProperties = async (properties: TaskPropertiesUpdate) => {
    if (!selectedTask) return false
    const normalizedProperties = {
      ...properties,
      description: properties.description.trim(),
      overdueReason: properties.overdueReason.trim(),
      acceptanceResult: properties.acceptanceResult.trim(),
    }
    const pendingMove = pendingTaskMove?.taskId === selectedTask.id ? pendingTaskMove : null
    const canFinishMove = pendingMove
      && (!isTaskOverdue(selectedTask) || Boolean(normalizedProperties.overdueReason))
      && (pendingMove.status !== 'review' || Boolean(selectedTask.reviewer))
    const saved = await saveSelectedTask(() => canFinishMove
      ? moveTask(selectedTask.id, pendingMove.status, selectedTask.reviewer, normalizedProperties)
      : updateProperties(selectedTask.id, normalizedProperties))
    if (saved && canFinishMove) setPendingTaskMove(null)
    return saved
  }
  const openNotification = async (notification: AppNotification) => {
    if (!notification.taskId || !notification.projectId) return
    await taskApi.getTask(notification.taskId)
    const nextBoard = await loadProject(notification.projectId)
    const task = nextBoard.columns.flatMap((column) => column.tasks).find((item) => item.id === notification.taskId)
    if (!task) throw new Error('Công việc không còn tồn tại hoặc bạn không có quyền truy cập.')
    setQuery('')
    setFilter('all')
    setActiveSection('Dự án')
    setPendingTaskMove(null)
    setSelectedTask(task)
  }
  const openTask = (task: Task) => {
    setPendingTaskMove(null)
    setSelectedTask(task)
  }
  const logSelectedTime = async (payload: TimeEntryInput) => {
    if (!selectedTask) return false
    try {
      const entry = await logTime(selectedTask.id, payload)
      setSelectedTask((current) => current?.id === selectedTask.id
        ? { ...current, timesheets: [...current.timesheets, entry] } : current)
      return true
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Không thể lưu thời gian làm việc.')
      return false
    }
  }
  const commentOnSelectedTask = async (body: string) => {
    if (!selectedTask) return false
    try {
      const comment = await addComment(selectedTask.id, body)
      setSelectedTask((current) => current?.id === selectedTask.id
        ? { ...current, comments: current.comments + 1, commentItems: [...current.commentItems, comment] } : current)
      return true
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Không thể lưu bình luận.')
      return false
    }
  }
  const deleteSelectedTask = async () => {
    if (!selectedTask || !await deleteTask(selectedTask.id)) return false
    setPendingTaskMove(null)
    setSelectedTask((current) => current?.id === selectedTask.id ? null : current)
    return true
  }

  if (!authenticated) return <AuthPage onAuthenticate={authenticate} onSso={authenticateWithSso} />
  if (invitationToken) return <InvitationPage token={invitationToken} />

  return (
    <div className={`app${dark ? ' app--dark' : ''}${sidebarHidden ? ' app--sidebar-hidden' : ''}`}>
      <AppSidebar open={sidebarOpen} activeSection={activeSection} activeProjectId={board.project.id} projects={projects} onNavigate={(section) => { setActiveSection(section); setFilter(section === 'Công việc của tôi' ? 'mine' : 'all'); setSidebarOpen(false) }} onSelectProject={selectProject} onCreateProject={() => setCreatingProject(true)} onToggleHidden={() => setDesktopSidebarHidden(true)} onClose={() => setSidebarOpen(false)} />
      <div className="app__content">
        <TopBar projectName={activeSection === 'Hồ sơ' ? 'Hồ sơ cá nhân' : board.project.name} query={query} onQueryChange={setQuery} onCreate={() => setCreating(true)} onMenu={() => { if (window.matchMedia('(max-width: 900px)').matches) setSidebarOpen(true); else setDesktopSidebarHidden(false) }} onToggleTheme={() => setDark((value) => !value)} onProfile={() => setActiveSection('Hồ sơ')} onLogout={logout} onOpenNotification={openNotification} />
        {loading && <div className="loading-state">Đang tải dữ liệu...</div>}
        {!loading && activeSection === 'Tổng quan' && <OverviewPage board={board} onOpenProject={() => setActiveSection('Dự án')} onOpenMyTasks={() => setActiveSection('Công việc của tôi')} onOpenTask={openTask} />}
        {!loading && activeSection === 'Công việc của tôi' && <MyTasksPage board={board} onOpenTask={openTask} />}
        {!loading && activeSection === 'Dự án' && <BoardPage board={board} columns={columns} filter={filter} onFilter={setFilter} onOpenTask={openTask} onMoveTask={moveBoardTask} onDeleteTask={deleteTask} onCreate={() => setCreating(true)} onMembersChange={updateProjectMembers} />}
        {!loading && activeSection === 'Hồ sơ' && <ProfilePage />}
      </div>
      {selectedTask && <TaskDrawer key={selectedTask.id} task={selectedTask} members={board.project.members} reviewRequested={pendingTaskMove?.taskId === selectedTask.id && pendingTaskMove.status === 'review' && !selectedTask.reviewer} overdueReasonRequired={pendingTaskMove?.taskId === selectedTask.id && isTaskOverdue(selectedTask) && !selectedTask.overdueReason?.trim()} onClose={() => { setSelectedTask(null); setPendingTaskMove(null) }} onMove={moveSelectedTask} onReviewerChange={changeReviewer} onUpdateProperties={changeProperties} onDelete={deleteSelectedTask} onLogTime={logSelectedTime} onAddComment={commentOnSelectedTask} />}
      {creating && <CreateTaskModal projectName={board.project.name} members={board.project.members} onClose={() => setCreating(false)} onCreate={addTask} />}
      {creatingProject && <CreateProjectModal onClose={() => setCreatingProject(false)} onCreate={createProject} />}
    </div>
  )
}

export default App

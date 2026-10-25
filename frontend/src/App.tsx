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
import { currentUser } from './data/mockData'
import { authApi, type LoginPayload, type RegisterPayload, type SsoProvider } from './services/authApi'
import { getTaskAssignees, type Task, type TaskComment, type TaskPropertiesUpdate, type TaskStatus, type TimesheetEntry, type UserSummary } from './types/task'

function App() {
  const [authenticated, setAuthenticated] = useState(() => localStorage.getItem('taskflow-authenticated') === 'true')
  const { board, projects, columns, query, setQuery, filter, setFilter, loading, selectProject, createProject, moveTask, addTask, deleteTask, updateProjectMembers, logTime, addComment, updateReviewer, updateProperties } = useBoard('p-01', authenticated)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [pendingTaskMove, setPendingTaskMove] = useState<{ taskId: string; status: TaskStatus } | null>(null)
  const [creating, setCreating] = useState(false)
  const [creatingProject, setCreatingProject] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarHidden, setSidebarHidden] = useState(() => localStorage.getItem('taskflow-sidebar-hidden') === 'true')
  const [dark, setDark] = useState(false)
  const [activeSection, setActiveSection] = useState('Tổng quan')
  const useMocks = import.meta.env.VITE_USE_MOCKS !== 'false'
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
    if (useMocks) {
      localStorage.setItem('taskflow-current-user', JSON.stringify({ ...currentUser, name: data.name || currentUser.name, email: data.email }))
      finishAuthentication()
      return
    }
    const response = data.mode === 'login'
      ? await authApi.login({ email: data.email, password: data.password } satisfies LoginPayload)
      : await authApi.register({ name: data.name ?? '', email: data.email, phone: data.phone, password: data.password } satisfies RegisterPayload)
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
      if (!useMocks) {
        if (!refreshToken) {
          throw new Error('Missing refresh token')
        }

        await authApi.logout(refreshToken)
      }
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

  const moveSelectedTask = (status: TaskStatus) => {
    if (!selectedTask || selectedTask.status === status) return
    const needsReviewer = status === 'review' && !selectedTask.reviewer
    const needsOverdueReason = isTaskOverdue(selectedTask) && !selectedTask.overdueReason?.trim()
    if (needsReviewer || needsOverdueReason) {
      setPendingTaskMove({ taskId: selectedTask.id, status })
      return
    }
    moveTask(selectedTask.id, status)
    setPendingTaskMove(null)
    setSelectedTask({ ...selectedTask, status })
  }
  const moveBoardTask = (taskId: string, status: TaskStatus) => {
    const task = board.columns.flatMap((column) => column.tasks).find((item) => item.id === taskId)
    if (!task || task.status === status) return
    const needsReviewer = status === 'review' && !task.reviewer
    const needsOverdueReason = isTaskOverdue(task) && !task.overdueReason?.trim()
    if (needsReviewer || needsOverdueReason) {
      setSelectedTask(task)
      setPendingTaskMove({ taskId: task.id, status })
      return
    }
    moveTask(taskId, status)
  }
  const changeReviewer = (reviewer: UserSummary) => {
    if (!selectedTask) return
    const pendingMove = pendingTaskMove?.taskId === selectedTask.id ? pendingTaskMove : null
    const stillNeedsOverdueReason = isTaskOverdue(selectedTask) && !selectedTask.overdueReason?.trim()
    const canFinishMove = pendingMove && !stillNeedsOverdueReason
    if (canFinishMove) moveTask(selectedTask.id, pendingMove.status, reviewer, getTaskProperties(selectedTask))
    else updateReviewer(selectedTask.id, reviewer)
    setSelectedTask({ ...selectedTask, reviewer, ...(canFinishMove ? { status: pendingMove.status } : {}) })
    if (canFinishMove) setPendingTaskMove(null)
  }
  const changeProperties = (properties: TaskPropertiesUpdate) => {
    if (!selectedTask) return
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
    if (canFinishMove) moveTask(selectedTask.id, pendingMove.status, selectedTask.reviewer, normalizedProperties)
    else updateProperties(selectedTask.id, normalizedProperties)
    const assignees = board.project.members.filter((member) => normalizedProperties.assigneeIds.includes(member.id))
    setSelectedTask({
      ...selectedTask,
      ...(canFinishMove ? { status: pendingMove.status } : {}),
      description: normalizedProperties.description,
      priority: normalizedProperties.priority,
      assignees,
      startDate: normalizedProperties.startDate,
      endDate: normalizedProperties.endDate,
      overdueReason: normalizedProperties.overdueReason || undefined,
      acceptanceResult: normalizedProperties.acceptanceResult || undefined,
    })
    if (canFinishMove) setPendingTaskMove(null)
  }
  const openTask = (task: Task) => {
    setPendingTaskMove(null)
    setSelectedTask(task)
  }
  const logSelectedTime = (entry: TimesheetEntry) => {
    if (!selectedTask) return
    logTime(selectedTask.id, entry)
    setSelectedTask({ ...selectedTask, timesheets: [...selectedTask.timesheets, entry] })
  }
  const commentOnSelectedTask = (comment: TaskComment) => {
    if (!selectedTask) return
    addComment(selectedTask.id, comment)
    setSelectedTask({ ...selectedTask, comments: selectedTask.comments + 1, commentItems: [...selectedTask.commentItems, comment] })
  }
  const deleteSelectedTask = () => {
    if (!selectedTask) return
    deleteTask(selectedTask.id)
    setPendingTaskMove(null)
    setSelectedTask(null)
  }

  if (!authenticated) return <AuthPage onAuthenticate={authenticate} onSso={authenticateWithSso} />
  if (invitationToken) return <InvitationPage token={invitationToken} />

  return (
    <div className={`app${dark ? ' app--dark' : ''}${sidebarHidden ? ' app--sidebar-hidden' : ''}`}>
      <AppSidebar open={sidebarOpen} activeSection={activeSection} activeProjectId={board.project.id} projects={projects} onNavigate={(section) => { setActiveSection(section); setFilter(section === 'Công việc của tôi' ? 'mine' : 'all'); setSidebarOpen(false) }} onSelectProject={selectProject} onCreateProject={() => setCreatingProject(true)} onToggleHidden={() => setDesktopSidebarHidden(true)} onClose={() => setSidebarOpen(false)} />
      <div className="app__content">
        <TopBar projectName={activeSection === 'Hồ sơ' ? 'Hồ sơ cá nhân' : board.project.name} query={query} onQueryChange={setQuery} onCreate={() => setCreating(true)} onMenu={() => { if (window.matchMedia('(max-width: 900px)').matches) setSidebarOpen(true); else setDesktopSidebarHidden(false) }} onToggleTheme={() => setDark((value) => !value)} onProfile={() => setActiveSection('Hồ sơ')} onLogout={logout} />
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

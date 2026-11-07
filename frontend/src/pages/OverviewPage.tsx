import { getTaskAssignees, type BoardData, type ProjectSummary, type Task } from '../types/task'
import { Avatar } from '../components/ui/Avatar'
import { Icon } from '../components/ui/Icon'
import { getStoredUser } from '../utils/session'

const statusLabels: Record<Task['status'], string> = {
  backlog: 'Cần làm',
  'in-progress': 'Đang làm',
  review: 'Đang duyệt',
  done: 'Hoàn thành',
}

interface OverviewPageProps {
  board: BoardData
  projects: ProjectSummary[]
  allTasks: Task[]
  onSelectProject: (projectId: string) => void
  onOpenProject: () => void
  onOpenMyTasks: () => void
  onOpenTask: (task: Task) => void
}

export function OverviewPage({ board, projects, allTasks, onSelectProject, onOpenProject, onOpenMyTasks, onOpenTask }: OverviewPageProps) {
  const displayUser = getStoredUser()
  const now = new Date()
  const tasks = allTasks.length > 0 ? allTasks : board.columns.flatMap((column) => column.tasks)
  const myTasks = tasks.filter((task) => getTaskAssignees(task).some((member) => member.id === displayUser.id) && task.status !== 'done')
  const overdue = tasks.filter((task) => task.status !== 'done' && new Date(`${task.endDate}T23:59:59`) < now)
  const done = tasks.filter((task) => task.status === 'done')
  const overallProgress = tasks.length > 0 ? Math.round((done.length / tasks.length) * 100) : 0
  const statusCards = board.columns.map((column) => ({
    ...column,
    count: tasks.filter((task) => task.status === column.id).length,
  }))
  const completedProjectsCount = projects.filter((project) => {
    const projTotal = project.totalTasks ?? tasks.filter((t) => t.projectId === project.id).length
    return projTotal > 0 && project.progress === 100
  }).length
  const activeProjectsCount = Math.max(0, projects.length - completedProjectsCount)

  return (
    <main className="dashboard-page">
      <header className="dashboard-heading"><div><h1>Xin chào, {displayUser.name} <span>👋</span></h1><p>Tổng quan các dự án và công việc của bạn.</p></div></header>

      <section className="dashboard-stats">
        <article><span>Tổng dự án</span><i className="stat-icon stat-icon--blue"><Icon name="folder" size={21} /></i><strong>{projects.length}</strong><small>{activeProjectsCount} đang hoạt động</small></article>
        <article><span>Dự án hoàn thành</span><i className="stat-icon stat-icon--green"><Icon name="check" size={21} /></i><strong>{completedProjectsCount}</strong><small>đã nghiệm thu / đóng</small></article>
        <article><span>Công việc của tôi</span><i className="stat-icon stat-icon--cyan"><Icon name="list" size={21} /></i><strong>{myTasks.length}</strong><small>đang được giao cho bạn</small></article>
        <article><span>Quá hạn</span><i className="stat-icon stat-icon--red"><Icon name="flag" size={21} /></i><strong>{overdue.length}</strong><small>công việc cần xử lý</small></article>
      </section>

      <section className="dashboard-panel project-status-panel">
        <header><h2>Công việc theo trạng thái (Tất cả dự án)</h2><button onClick={onOpenProject}>Xem dự án</button></header>
        <div className="project-progress"><span style={{ width: `${overallProgress}%` }} /></div>
        <div className="status-summary">{statusCards.map((status) => <article key={status.id}><i style={{ background: `${status.accent}18`, color: status.accent }}><Icon name={status.id === 'done' ? 'check' : status.id === 'in-progress' ? 'chart' : 'folder'} size={18} /></i><div><span>{status.title}</span><strong>{status.count}</strong></div></article>)}</div>
      </section>

      <section className="dashboard-columns">
        <article className="dashboard-panel recent-project">
          <header><h2>Dự án của bạn ({projects.length})</h2><button onClick={onOpenProject}>Xem tất cả</button></header>
          {projects.map((project) => {
            const projTotal = project.totalTasks ?? tasks.filter((t) => t.projectId === project.id).length
            const projDone = project.doneTasks ?? tasks.filter((t) => t.projectId === project.id && t.status === 'done').length
            const projProgress = projTotal > 0 ? Math.round((projDone / projTotal) * 100) : project.progress
            return (
              <button className="project-summary-row" onClick={() => { onSelectProject(project.id); onOpenProject() }} key={project.id}>
                <span className="project-icon" style={{ background: project.color }}>{project.key}</span>
                <div>
                  <strong>{project.name}</strong>
                  <span>{projTotal} công việc · {projDone} hoàn thành</span>
                  <div><i style={{ width: `${projProgress}%` }} /></div>
                </div>
                <b>{projProgress}%</b>
              </button>
            )
          })}
          {projects.length === 0 && <div className="empty-dashboard">Bạn chưa tham gia dự án nào.</div>}
        </article>
        <article className="dashboard-panel my-task-panel"><header><h2>Công việc của tôi</h2><button onClick={onOpenMyTasks}>Xem tất cả</button></header><span className="panel-caption">Đang thực hiện ({myTasks.length})</span>{myTasks.slice(0, 5).map((task) => <button className="dashboard-task-row" onClick={() => onOpenTask(task)} key={task.id}><Avatar user={displayUser} size={29} /><span><strong>{task.title}</strong><small>{task.key}{task.projectName ? ` (${task.projectName})` : ''} · {getTaskAssignees(task).length} người thực hiện · Hạn {new Intl.DateTimeFormat('vi-VN').format(new Date(task.endDate))}</small></span><i className={`status-pill status-pill--${task.status}`}>{statusLabels[task.status]}</i></button>)}{myTasks.length === 0 && <div className="empty-dashboard">Chưa có công việc nào đang giao cho bạn.</div>}</article>
      </section>
    </main>
  )
}

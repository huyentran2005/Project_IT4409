import { currentUser } from '../data/mockData'
import { getTaskAssignees, type BoardData, type Task } from '../types/task'
import { Avatar } from '../components/ui/Avatar'
import { Icon } from '../components/ui/Icon'

export function OverviewPage({ board, onOpenProject, onOpenMyTasks, onOpenTask }: { board: BoardData; onOpenProject: () => void; onOpenMyTasks: () => void; onOpenTask: (task: Task) => void }) {
  const displayUser = (() => {
    try {
      const savedUser = JSON.parse(localStorage.getItem('taskflow-current-user') ?? 'null')
      return savedUser?.name ? { ...currentUser, ...savedUser } : currentUser
    } catch {
      return currentUser
    }
  })()
  const tasks = board.columns.flatMap((column) => column.tasks)
  const myTasks = tasks.filter((task) => getTaskAssignees(task).some((member) => member.id === displayUser.id) && task.status !== 'done')
  const overdue = tasks.filter((task) => task.status !== 'done' && new Date(task.endDate) < new Date('2026-10-16'))
  const done = tasks.filter((task) => task.status === 'done')
  const statusCards = board.columns.map((column) => ({ ...column, count: column.tasks.length }))

  return (
    <main className="dashboard-page">
      <header className="dashboard-heading"><div><h1>Xin chào, {displayUser.name} <span>👋</span></h1><p>Tổng quan các dự án và công việc của bạn.</p></div></header>

      <section className="dashboard-stats">
        <article><span>Tổng dự án</span><i className="stat-icon stat-icon--blue"><Icon name="folder" size={21} /></i><strong>1</strong><small>1 đang hoạt động</small></article>
        <article><span>Dự án hoàn thành</span><i className="stat-icon stat-icon--green"><Icon name="check" size={21} /></i><strong>0</strong><small>đã nghiệm thu / đóng</small></article>
        <article><span>Công việc của tôi</span><i className="stat-icon stat-icon--cyan"><Icon name="list" size={21} /></i><strong>{myTasks.length}</strong><small>đang được giao cho bạn</small></article>
        <article><span>Quá hạn</span><i className="stat-icon stat-icon--red"><Icon name="flag" size={21} /></i><strong>{overdue.length}</strong><small>công việc cần xử lý</small></article>
      </section>

      <section className="dashboard-panel project-status-panel">
        <header><h2>Dự án theo trạng thái</h2><button onClick={onOpenProject}>Xem dự án</button></header>
        <div className="project-progress"><span style={{ width: `${board.project.progress}%` }} /></div>
        <div className="status-summary">{statusCards.map((status) => <article key={status.id}><i style={{ background: `${status.accent}18`, color: status.accent }}><Icon name={status.id === 'done' ? 'check' : status.id === 'in-progress' ? 'chart' : 'folder'} size={18} /></i><div><span>{status.title}</span><strong>{status.count}</strong></div></article>)}</div>
      </section>

      <section className="dashboard-columns">
        <article className="dashboard-panel recent-project"><header><h2>Dự án gần đây</h2><button onClick={onOpenProject}>Xem tất cả</button></header><button className="project-summary-row" onClick={onOpenProject}><span className="project-icon" style={{ background: board.project.color }}>{board.project.key}</span><div><strong>{board.project.name}</strong><span>{tasks.length} công việc · {done.length} hoàn thành</span><div><i style={{ width: `${board.project.progress}%` }} /></div></div><b>{board.project.progress}%</b></button></article>
        <article className="dashboard-panel my-task-panel"><header><h2>Công việc của tôi</h2><button onClick={onOpenMyTasks}>Xem tất cả</button></header><span className="panel-caption">Đang thực hiện ({myTasks.length})</span>{myTasks.slice(0, 4).map((task) => <button className="dashboard-task-row" onClick={() => onOpenTask(task)} key={task.id}><Avatar user={displayUser} size={29} /><span><strong>{task.title}</strong><small>{task.key} · {getTaskAssignees(task).length} người thực hiện · Hạn {new Intl.DateTimeFormat('vi-VN').format(new Date(task.endDate))}</small></span><i className={`status-pill status-pill--${task.status}`}>{task.status === 'in-progress' ? 'Đang làm' : 'Đang duyệt'}</i></button>)}</article>
      </section>
    </main>
  )
}

import { currentUser } from '../data/mockData'
import { getTaskAssignees, type BoardData, type Task } from '../types/task'
import { Icon } from '../components/ui/Icon'

const dateKey = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
const formatMinutes = (minutes: number) => `${Math.floor(minutes / 60)}h ${minutes % 60}m`

export function MyTasksPage({ board, onOpenTask }: { board: BoardData; onOpenTask: (task: Task) => void }) {
  const activeUserId = (() => {
    try {
      const raw = localStorage.getItem('taskflow-current-user')
      if (raw) return (JSON.parse(raw) as { id?: string }).id ?? currentUser.id
    } catch {
      // ignore
    }
    return currentUser.id
  })()
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const weekEnd = new Date(today); weekEnd.setDate(today.getDate() + 7); weekEnd.setHours(23, 59, 59, 999)
  const weekStart = new Date(today); weekStart.setDate(today.getDate() - ((today.getDay() + 6) % 7)); weekStart.setHours(0, 0, 0, 0)
  const last14Days = Array.from({ length: 14 }, (_, index) => { const date = new Date(today); date.setDate(today.getDate() - (13 - index)); return date })
  const allTasks = board.columns.flatMap((column) => column.tasks)
  const tasks = allTasks.filter((task) => getTaskAssignees(task).some((member) => member.id === activeUserId))
  const openTasks = tasks.filter((task) => task.status !== 'done')
  const overdue = openTasks.filter((task) => new Date(task.endDate) < today)
  const dueThisWeek = openTasks.filter((task) => new Date(task.endDate) >= today && new Date(task.endDate) <= weekEnd)
  const inProgress = tasks.filter((task) => task.status === 'in-progress')
  const completed = tasks.filter((task) => task.status === 'done' && task.completedAt && new Date(task.completedAt) >= last14Days[0])
  const todayTasks = tasks.filter((task) => task.endDate === dateKey(today))
  const timesheets = tasks.flatMap((task) => task.timesheets).filter((entry) => new Date(entry.startTime) >= weekStart && new Date(entry.startTime) <= weekEnd)
  const loggedMinutes = timesheets.reduce((sum, item) => sum + item.minutes, 0)
  const weekdays = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']
  const dailyMinutes = weekdays.map((_, index) => timesheets.filter((item) => ((new Date(item.startTime).getDay() + 6) % 7) === index).reduce((sum, item) => sum + item.minutes, 0))
  const maxMinutes = Math.max(...dailyMinutes, 1)
  const dailyCompleted = last14Days.map((date) => completed.filter((task) => task.completedAt && dateKey(new Date(task.completedAt)) === dateKey(date)).length)
  const maxCompleted = Math.max(...dailyCompleted, 1)

  return (
    <main className="dashboard-page my-work-page">
      <header className="dashboard-heading"><div><h1>Công việc của tôi</h1><p>Theo dõi deadline, tiến độ và thời gian làm việc cá nhân.</p></div></header>

      <section className="work-stats">
        <article className="work-stat work-stat--danger"><i><Icon name="flag" size={20} /></i><small>{overdue.length}</small><strong>{overdue.length}</strong><span>Quá hạn</span><p>cần xử lý ngay</p></article>
        <article><i><Icon name="calendar" size={20} /></i><small>—</small><strong>{dueThisWeek.length}</strong><span>Đến hạn tuần này</span><p>trong 7 ngày tới</p></article>
        <article><i><Icon name="chart" size={20} /></i><small>▲ {inProgress.length}</small><strong>{inProgress.length}</strong><span>Đang làm</span><p>In Progress</p></article>
        <article><i><Icon name="check" size={20} /></i><small>—</small><strong>{completed.length}</strong><span>Hoàn thành</span><p>trong 14 ngày qua</p></article>
      </section>

      <section className="work-grid">
        <article className="dashboard-panel today-panel"><header><h2>Công việc hôm nay ({todayTasks.length})</h2></header>{todayTasks.length ? todayTasks.map((task) => <button className="dashboard-task-row" onClick={() => onOpenTask(task)} key={task.id}><span><strong>{task.title}</strong><small>{task.key}</small></span><i className={`status-pill status-pill--${task.status}`}>{task.status}</i></button>) : <div className="empty-dashboard">Hôm nay bạn không có task nào đến hạn.</div>}</article>
        <article className="dashboard-panel project-donut-panel"><header><h2>Task theo dự án</h2></header><div className="donut-content"><div className="donut" style={{ '--donut-value': `${openTasks.length ? 360 : 0}deg` } as React.CSSProperties}><span><strong>{openTasks.length}</strong><small>task mở</small></span></div><div><p><i style={{ background: board.project.color }} />{board.project.name}<strong>100%</strong></p><small>{openTasks.length} task đang mở trên 1 dự án.</small></div></div></article>
        <article className="dashboard-panel timesheet-chart"><header><h2>Timesheet tuần này</h2></header><div className="chart-total"><strong>{formatMinutes(loggedMinutes)}</strong><span>tuần này</span></div><div className="bar-chart">{dailyMinutes.map((minutes, index) => <div className="chart-bar" data-tooltip={`${weekdays[index]}: ${formatMinutes(minutes)}`} key={weekdays[index]}><span style={{ height: `${Math.max(minutes / maxMinutes * 100, 2)}%` }} /><small>{weekdays[index]}</small></div>)}</div></article>
        <article className="dashboard-panel completion-chart"><header><h2>Hoàn thành 14 ngày qua</h2></header><div className="chart-total"><strong>{completed.length}</strong><span>task hoàn thành</span></div><div className="completion-bars">{dailyCompleted.map((count, index) => <div className="completion-bar chart-bar" data-tooltip={`${new Intl.DateTimeFormat('vi-VN').format(last14Days[index])}: ${count} task`} key={dateKey(last14Days[index])}><span style={{ height: `${Math.max(count / maxCompleted * 100, 3)}%` }} /><small>{index % 3 === 1 || index === 13 ? `${last14Days[index].getDate()}/${last14Days[index].getMonth() + 1}` : ''}</small></div>)}</div></article>
        <article className="dashboard-panel activity-panel"><header><h2>Hoạt động gần đây</h2></header>{timesheets.slice(0, 4).map((entry) => <div className="activity-row" key={entry.id}><i><Icon name="check" size={15} /></i><span><strong>{entry.note}</strong><small>{entry.user.name} · {new Intl.DateTimeFormat('vi-VN').format(new Date(entry.startTime))}</small></span><b>{Math.floor(entry.minutes / 60)}h {entry.minutes % 60}m</b></div>)}</article>
      </section>
    </main>
  )
}

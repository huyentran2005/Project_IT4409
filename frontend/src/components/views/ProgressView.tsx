import { getTaskAssignees, type BoardColumn, type Task } from '../../types/task'
import { Avatar } from '../ui/Avatar'

export function ProgressView({ columns, tasks }: { columns: BoardColumn[]; tasks: Task[] }) {
  const total = tasks.length
  const done = tasks.filter((task) => task.status === 'done').length
  const completion = total ? Math.round(done / total * 100) : 0
  const loggedMinutes = tasks.flatMap((task) => task.timesheets).reduce((sum, entry) => sum + entry.minutes, 0)
  const averageLoggedMinutes = total ? Math.round(loggedMinutes / total) : 0
  const assignees = Array.from(new Map(tasks.flatMap(getTaskAssignees).map((member) => [member.id, member])).values())

  return (
    <section className="progress-view" aria-label="Tiến độ dự án">
      <div className="progress-kpis"><article><span>Hoàn thành</span><strong>{completion}%</strong><small>{done}/{total} công việc</small></article><article><span>Thời gian đã log</span><strong>{Math.floor(loggedMinutes / 60)}h {loggedMinutes % 60}m</strong><small>Tổng từ timesheet</small></article><article><span>Trung bình mỗi công việc</span><strong>{Math.floor(averageLoggedMinutes / 60)}h {averageLoggedMinutes % 60}m</strong><small>Dựa trên {total} công việc</small></article></div>
      <div className="progress-panels">
        <article className="progress-panel"><header><h2>Tiến độ theo trạng thái</h2><span>{total} công việc</span></header><div className="status-progress-list">{columns.map((column) => { const value = total ? Math.round(column.tasks.length / total * 100) : 0; return <div key={column.id}><div><span><i style={{ background: column.accent }} />{column.title}</span><strong>{column.tasks.length} <small>({value}%)</small></strong></div><div className="status-progress"><span style={{ width: `${value}%`, background: column.accent }} /></div></div> })}</div></article>
        <article className="progress-panel"><header><h2>Khối lượng thành viên</h2><span>{assignees.length} người</span></header><div className="workload-list">{assignees.map((user) => { const count = tasks.filter((task) => getTaskAssignees(task).some((member) => member.id === user.id)).length; return <div key={user.id}><Avatar user={user} size={31} /><span><strong>{user.name}</strong><small>{count} công việc được giao</small></span><div><i style={{ width: `${Math.min(count / Math.max(total, 1) * 200, 100)}%` }} /></div></div> })}</div></article>
      </div>
    </section>
  )
}

import { getTaskAssignees, type Task } from '../../types/task'
import { Avatar } from '../ui/Avatar'
import { Icon } from '../ui/Icon'

const statusLabels = { backlog: 'Cần làm', 'in-progress': 'Đang làm', review: 'Đang duyệt', done: 'Hoàn thành' }
const formatDuration = (minutes: number) => `${Math.floor(minutes / 60)}h ${minutes % 60}m`

export function TaskListView({ tasks, onOpenTask }: { tasks: Task[]; onOpenTask: (task: Task) => void }) {
  return (
    <section className="list-view" aria-label="Danh sách công việc">
      <div className="task-table task-table--head"><span>Công việc</span><span>Trạng thái</span><span>Người thực hiện</span><span>Thời gian</span><span>Đã log</span></div>
      {tasks.map((task) => {
        const assignees = getTaskAssignees(task)
        return (
        <button className="task-table task-table--row" onClick={() => onOpenTask(task)} key={task.id}>
          <span className="list-task-title"><i className={`task-type task-type--${task.type}`}>{task.type}</i><span><strong>{task.title}</strong><small>{task.key}</small></span></span>
          <span><i className={`status-pill status-pill--${task.status}`}>{statusLabels[task.status]}</i></span>
          <span>{assignees.length ? <span className="list-assignee"><span className="task-assignee-stack">{assignees.slice(0, 2).map((member) => <Avatar user={member} size={27} key={member.id} />)}</span><span>{assignees.map((member) => member.name).join(', ')}</span></span> : 'Chưa giao'}</span>
          <span className="list-date"><Icon name="calendar" size={14} />{new Intl.DateTimeFormat('vi-VN').format(new Date(task.startDate))} – {new Intl.DateTimeFormat('vi-VN').format(new Date(task.endDate))}</span>
          <strong>{formatDuration(task.timesheets.reduce((sum, entry) => sum + entry.minutes, 0))}</strong>
        </button>
      )})}
      {!tasks.length && <div className="view-empty">Không có công việc phù hợp với bộ lọc.</div>}
    </section>
  )
}

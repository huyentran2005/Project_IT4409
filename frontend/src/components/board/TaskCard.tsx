import { useState } from 'react'
import { getTaskAssignees, type Task } from '../../types/task'
import { Avatar } from '../ui/Avatar'
import { Icon } from '../ui/Icon'

const typeLabels = { epic: 'Epic', story: 'Story', task: 'Task', bug: 'Bug' }
const priorityLabels = { urgent: 'Khẩn cấp', high: 'Cao', medium: 'Trung bình', low: 'Thấp' }
const formatDate = (date: string) => new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(`${date}T00:00:00`))

interface TaskCardProps {
  task: Task
  onOpen: (task: Task) => void
  onDelete: (taskId: string) => void
}

export function TaskCard({ task, onOpen, onDelete }: TaskCardProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const progress = task.checklist.total ? Math.round(task.checklist.completed / task.checklist.total * 100) : 0
  const assignees = getTaskAssignees(task)
  const overdue = task.status !== 'done' && new Date(`${task.endDate}T23:59:59`) < new Date()
  const deleteTask = () => {
    setMenuOpen(false)
    if (window.confirm(`Xóa công việc “${task.title}”? Hành động này không thể hoàn tác.`)) onDelete(task.id)
  }
  return (
    <article className="task-card" draggable onDragStart={(event) => event.dataTransfer.setData('text/task-id', task.id)} onClick={() => onOpen(task)}>
      <div className="task-card__top">
        <h3>{task.title}</h3>
        <div className="task-card__actions" onClick={(event) => event.stopPropagation()}>
          <button className="task-card__more" onClick={() => setMenuOpen((value) => !value)} aria-label={`Tùy chọn cho ${task.title}`} aria-expanded={menuOpen}><Icon name="more" size={18} /></button>
          {menuOpen && <div className="task-card__menu"><button onClick={deleteTask}><Icon name="trash" size={15} />Xóa công việc</button></div>}
        </div>
      </div>
      <div className="task-card__details">
        <div className="task-card__detail"><span><Icon name="flag" size={16} />Ưu tiên</span><strong className={`task-card__priority task-card__priority--${task.priority}`}><i />{priorityLabels[task.priority]}</strong></div>
        <div className="task-card__detail"><span><Icon name="user" size={16} />PIC</span><strong className="task-card__assignees">{assignees.length ? <><span className="task-assignee-stack">{assignees.slice(0, 3).map((member) => <Avatar user={member} size={27} key={member.id} />)}{assignees.length > 3 && <i>+{assignees.length - 3}</i>}</span><b title={assignees.map((member) => member.name).join(', ')}>{assignees.map((member) => member.name).join(', ')}</b></> : <b>Chưa giao</b>}</strong></div>
        {task.status === 'review' && <div className="task-card__detail"><span><Icon name="check" size={16} />Người duyệt</span><strong className={task.reviewer ? 'task-card__reviewer' : 'task-card__reviewer task-card__reviewer--missing'}>{task.reviewer ? <><Avatar user={task.reviewer} size={25} /><b>{task.reviewer.name}</b></> : 'Chưa chọn'}</strong></div>}
        <div className="task-card__detail"><span><Icon name="tag" size={16} />Loại công việc</span><strong>{typeLabels[task.type]}</strong></div>
        <div className="task-card__detail"><span><Icon name="calendar" size={16} />Ngày bắt đầu</span><strong>{formatDate(task.startDate)}</strong></div>
        <div className="task-card__detail"><span><Icon name="calendar-clock" size={16} />Ngày kết thúc dự kiến</span><strong className={overdue ? 'task-card__overdue' : ''}>{formatDate(task.endDate)}</strong></div>
      </div>
      {task.checklist.total > 0 && (
        <div className="checklist-progress"><span style={{ width: `${progress}%` }} /><small>{task.checklist.completed}/{task.checklist.total}</small></div>
      )}
      {(task.labels.length > 0 || task.comments > 0 || task.attachments > 0) && <div className="task-card__supplement"><div>{task.labels.map((label) => <span key={label.id} style={{ '--label-color': label.color } as React.CSSProperties}>{label.name}</span>)}</div><small>{task.key}{task.comments > 0 && <> · <Icon name="comment" size={13} />{task.comments}</>}{task.attachments > 0 && <> · <Icon name="paperclip" size={13} />{task.attachments}</>}</small></div>}
    </article>
  )
}

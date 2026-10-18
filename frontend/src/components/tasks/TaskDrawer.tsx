import { useState } from 'react'
import { getTaskAssignees, type Task, type TaskComment, type TaskPriority, type TaskPropertiesUpdate, type TaskStatus, type TimesheetEntry, type UserSummary } from '../../types/task'
import { currentUser, mockStatusOptions } from '../../data/mockData'
import { Avatar } from '../ui/Avatar'
import { Icon } from '../ui/Icon'
import { ReviewerPicker } from './ReviewerPicker'
import { AssigneePicker } from './AssigneePicker'

const formatDate = (date: string) => new Intl.DateTimeFormat('vi-VN').format(new Date(date))
const formatTime = (date: string) => new Intl.DateTimeFormat('vi-VN', { hour: '2-digit', minute: '2-digit' }).format(new Date(date))
const formatDuration = (minutes: number) => `${Math.floor(minutes / 60)}h ${minutes % 60}m`

interface TaskDrawerProps {
  task: Task
  members: UserSummary[]
  reviewRequested: boolean
  overdueReasonRequired: boolean
  onClose: () => void
  onMove: (status: TaskStatus) => void
  onReviewerChange: (reviewer: UserSummary) => void
  onUpdateProperties: (properties: TaskPropertiesUpdate) => void
  onDelete: () => void
  onLogTime: (entry: TimesheetEntry) => void
  onAddComment: (comment: TaskComment) => void
}

export function TaskDrawer({ task, members, reviewRequested, overdueReasonRequired, onClose, onMove, onReviewerChange, onUpdateProperties, onDelete, onLogTime, onAddComment }: TaskDrawerProps) {
  const [activeTab, setActiveTab] = useState<'timesheet' | 'comments'>('timesheet')
  const [menuOpen, setMenuOpen] = useState(false)
  const [logging, setLogging] = useState(false)
  const [startTime, setStartTime] = useState('')
  const [endTime, setEndTime] = useState('')
  const [note, setNote] = useState('')
  const [commentBody, setCommentBody] = useState('')
  const [description, setDescription] = useState(task.description)
  const [priority, setPriority] = useState<TaskPriority>(task.priority)
  const [assigneeIds, setAssigneeIds] = useState(() => getTaskAssignees(task).map((member) => member.id))
  const [startDate, setStartDate] = useState(task.startDate)
  const [taskEndDate, setTaskEndDate] = useState(task.endDate)
  const [overdueReason, setOverdueReason] = useState(task.overdueReason ?? '')
  const [acceptanceResult, setAcceptanceResult] = useState(task.acceptanceResult ?? '')
  const totalMinutes = task.timesheets.reduce((sum, entry) => sum + entry.minutes, 0)
  const overdueReference = task.completedAt ? new Date(task.completedAt) : new Date()
  const isOverdue = overdueReference > new Date(`${taskEndDate}T23:59:59`)
  const originalAssigneeIds = getTaskAssignees(task).map((member) => member.id)
  const propertiesChanged = description !== task.description
    || priority !== task.priority
    || assigneeIds.join(',') !== originalAssigneeIds.join(',')
    || startDate !== task.startDate
    || taskEndDate !== task.endDate
    || overdueReason !== (task.overdueReason ?? '')
    || acceptanceResult !== (task.acceptanceResult ?? '')
  const propertiesValid = Boolean(description.trim() && startDate && taskEndDate && taskEndDate >= startDate)

  const saveProperties = () => {
    const properties = {
      description: description.trim(), priority, assigneeIds, startDate, endDate: taskEndDate,
      overdueReason: overdueReason.trim(), acceptanceResult: acceptanceResult.trim(),
    }
    if (!properties.description || !properties.startDate || properties.endDate < properties.startDate) return
    onUpdateProperties(properties)
    setDescription(properties.description)
    setOverdueReason(properties.overdueReason)
    setAcceptanceResult(properties.acceptanceResult)
  }
  const deleteTask = () => {
    setMenuOpen(false)
    if (window.confirm(`Xóa công việc “${task.title}”? Hành động này không thể hoàn tác.`)) onDelete()
  }

  const submitTime = (event: React.FormEvent) => {
    event.preventDefault()
    const start = new Date(startTime)
    const end = new Date(endTime)
    const minutes = Math.round((end.getTime() - start.getTime()) / 60000)
    if (!startTime || !endTime || minutes <= 0 || !note.trim()) return
    onLogTime({ id: `timesheet-${Date.now()}`, user: currentUser, startTime: start.toISOString(), endTime: end.toISOString(), minutes, note: note.trim() })
    setStartTime(''); setEndTime(''); setNote(''); setLogging(false)
  }

  const submitComment = (event: React.FormEvent) => {
    event.preventDefault()
    if (!commentBody.trim()) return
    onAddComment({ id: `comment-${Date.now()}`, author: currentUser, body: commentBody.trim(), createdAt: new Date().toISOString() })
    setCommentBody('')
  }

  return (
    <>
      <button className="drawer-scrim" onClick={onClose} aria-label="Đóng chi tiết" />
      <aside className="task-drawer" aria-label="Chi tiết công việc">
        <div className="drawer-header"><span>{task.key}</span><div className="drawer-actions"><div className="drawer-menu"><button className="icon-button" onClick={() => setMenuOpen((value) => !value)} aria-label="Tùy chọn công việc" aria-expanded={menuOpen}><Icon name="more" /></button>{menuOpen && <div className="task-card__menu"><button onClick={deleteTask}><Icon name="trash" size={15} />Xóa công việc</button></div>}</div><button className="icon-button" onClick={onClose} aria-label="Đóng"><Icon name="close" /></button></div></div>
        <div className="drawer-content">
          <span className={`task-type task-type--${task.type}`}>{task.type.toUpperCase()}</span>
          <h2>{task.title}</h2>
          <div className="detail-grid">
            <span>Mô tả</span><textarea className="task-property-input" required value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Nhập mô tả công việc..." />
            <span>Trạng thái</span><select value={task.status} onChange={(event) => onMove(event.target.value as TaskStatus)}>{mockStatusOptions.map((status) => <option value={status.id} key={status.id}>{status.label}</option>)}</select>
            <span>Người thực hiện</span><AssigneePicker members={members} selectedIds={assigneeIds} onChange={setAssigneeIds} />
            {(task.status === 'review' || reviewRequested || task.reviewer) && <><span>Người duyệt</span><ReviewerPicker members={members} reviewer={task.reviewer} required={reviewRequested || task.status === 'review'} onChange={onReviewerChange} /></>}
            <span>Ưu tiên</span><select value={priority} onChange={(event) => setPriority(event.target.value as TaskPriority)}><option value="urgent">Khẩn cấp</option><option value="high">Cao</option><option value="medium">Trung bình</option><option value="low">Thấp</option></select>
            <span>Thời gian đã log</span><strong>{formatDuration(totalMinutes)}</strong>
            <span>Ngày bắt đầu</span><input className="task-property-date" type="date" required value={startDate} max={taskEndDate} onChange={(event) => setStartDate(event.target.value)} /><span>Ngày kết thúc</span><input className="task-property-date" type="date" required value={taskEndDate} min={startDate} onChange={(event) => setTaskEndDate(event.target.value)} />
            {isOverdue && <><span className="detail-label--overdue">Lý do quá hạn</span><div className="overdue-reason-field"><textarea className="task-property-input task-property-input--overdue" required={overdueReasonRequired} aria-invalid={overdueReasonRequired && !overdueReason.trim()} value={overdueReason} onChange={(event) => setOverdueReason(event.target.value)} placeholder="Nhập nguyên nhân công việc hoàn thành trễ..." />{overdueReasonRequired && !overdueReason.trim() && <small>Bắt buộc nhập lý do trước khi chuyển trạng thái.</small>}</div></>}
            <span>Kết quả nghiệm thu</span><textarea className="task-property-input" value={acceptanceResult} onChange={(event) => setAcceptanceResult(event.target.value)} placeholder="Nhập kết quả bàn giao hoặc nhận xét nghiệm thu..." />
            <span /><div className="task-property-actions"><button className="secondary-button" type="button" disabled={!propertiesChanged || !propertiesValid || (overdueReasonRequired && !overdueReason.trim())} onClick={saveProperties}>{overdueReasonRequired ? 'Lưu lý do và chuyển trạng thái' : 'Lưu thay đổi'}</button></div>
          </div>

          <nav className="task-detail-tabs"><button className={activeTab === 'timesheet' ? 'active' : ''} onClick={() => setActiveTab('timesheet')}>Timesheet <span>{task.timesheets.length}</span></button><button className={activeTab === 'comments' ? 'active' : ''} onClick={() => setActiveTab('comments')}>Bình luận <span>{task.commentItems.length}</span></button></nav>

          {activeTab === 'timesheet' && <section className="timesheet-section">
            <div className="timesheet-toolbar"><div><Icon name="calendar" size={16} /><span>Đã log</span><strong>{formatDuration(totalMinutes)}</strong></div><button className="primary-button" onClick={() => setLogging((value) => !value)}><Icon name="plus" size={16} />Ghi nhận giờ</button></div>
            {logging && <form className="time-log-form" onSubmit={submitTime}><label>Bắt đầu<input type="datetime-local" required value={startTime} onChange={(event) => setStartTime(event.target.value)} /></label><label>Kết thúc<input type="datetime-local" required min={startTime} value={endTime} onChange={(event) => setEndTime(event.target.value)} /></label><label className="time-note">Nội dung<input required value={note} onChange={(event) => setNote(event.target.value)} placeholder="Bạn đã làm gì?" /></label><button className="primary-button" type="submit">Lưu thời gian</button></form>}
            {task.timesheets.length ? <div className="timesheet-list">{task.timesheets.map((entry) => <div className="timesheet-entry" key={entry.id}><Avatar user={entry.user} size={28} /><div><strong>{entry.note}</strong><span>{entry.user.name} · {formatDate(entry.startTime)}</span></div><time>{formatTime(entry.startTime)}–{formatTime(entry.endTime)}<strong>{formatDuration(entry.minutes)}</strong></time></div>)}</div> : <div className="empty-timesheet">Chưa có thời gian làm việc được ghi nhận.</div>}
          </section>}

          {activeTab === 'comments' && <section className="comment-section">
            <form className="comment-form" onSubmit={submitComment}><Avatar user={currentUser} size={31} /><textarea value={commentBody} onChange={(event) => setCommentBody(event.target.value)} placeholder="Viết bình luận..." /><button className="primary-button" type="submit" disabled={!commentBody.trim()}>Gửi</button></form>
            <div className="comment-list">{task.commentItems.map((comment) => <article key={comment.id}><Avatar user={comment.author} size={32} /><div><header><strong>{comment.author.name}</strong><time>{formatDate(comment.createdAt)} · {formatTime(comment.createdAt)}</time></header><p>{comment.body}</p></div></article>)}{!task.commentItems.length && <div className="empty-timesheet">Chưa có bình luận nào.</div>}</div>
          </section>}
        </div>
      </aside>
    </>
  )
}

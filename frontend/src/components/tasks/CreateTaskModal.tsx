import { useEffect, useMemo, useRef, useState } from 'react'
import type { CreateTaskInput, TaskPriority, TaskType, UserSummary } from '../../types/task'
import { Avatar } from '../ui/Avatar'
import { Icon } from '../ui/Icon'

const toDateInput = (date: Date) => {
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 10)
}

interface CreateTaskModalProps {
  projectName: string
  members: UserSummary[]
  onClose: () => void
  onCreate: (input: CreateTaskInput) => Promise<void> | void
}

export function CreateTaskModal({ projectName, members, onClose, onCreate }: CreateTaskModalProps) {
  const today = new Date()
  const nextWeek = new Date(today)
  nextWeek.setDate(today.getDate() + 7)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [type, setType] = useState<TaskType>('task')
  const [priority, setPriority] = useState<TaskPriority>('medium')
  const [assigneeIds, setAssigneeIds] = useState<string[]>([])
  const [assigneeOpen, setAssigneeOpen] = useState(false)
  const [assigneeQuery, setAssigneeQuery] = useState('')
  const [startDate, setStartDate] = useState(() => toDateInput(today))
  const [endDate, setEndDate] = useState(() => toDateInput(nextWeek))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const assigneePickerRef = useRef<HTMLFieldSetElement>(null)
  const selectedMembers = useMemo(
    () => members.filter((member) => assigneeIds.includes(member.id)),
    [assigneeIds, members],
  )
  const filteredMembers = useMemo(() => {
    const query = assigneeQuery.trim().toLocaleLowerCase('vi')
    if (!query) return members
    return members.filter((member) => `${member.name} ${member.email}`.toLocaleLowerCase('vi').includes(query))
  }, [assigneeQuery, members])

  useEffect(() => {
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!assigneePickerRef.current?.contains(event.target as Node)) {
        setAssigneeOpen(false)
        setAssigneeQuery('')
      }
    }
    document.addEventListener('mousedown', closeOnOutsideClick)
    return () => document.removeEventListener('mousedown', closeOnOutsideClick)
  }, [])

  const toggleAssignee = (memberId: string) => {
    setAssigneeIds((current) => current.includes(memberId)
      ? current.filter((id) => id !== memberId)
      : [...current, memberId])
  }
  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!title.trim() || !description.trim() || !startDate || !endDate || endDate < startDate) return
    setError('')
    setSubmitting(true)
    try {
      await onCreate({ title: title.trim(), description: description.trim(), type, priority, assigneeIds, startDate, endDate })
      onClose()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể tạo công việc. Vui lòng thử lại.')
    } finally {
      setSubmitting(false)
    }
  }
  return (
    <div className="modal-layer" role="dialog" aria-modal="true" aria-label="Tạo công việc">
      <button className="modal-scrim" onClick={onClose} aria-label="Đóng" />
      <form className="create-modal" onSubmit={submit}>
        <div className="create-modal__header"><div><span>{projectName.toUpperCase()}</span><h2>Tạo công việc mới</h2></div><button type="button" className="icon-button" onClick={onClose}><Icon name="close" /></button></div>
        <label>Tiêu đề công việc<input autoFocus value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Ví dụ: Hoàn thiện trang đăng nhập" /></label>
        <label className="task-description-field">Mô tả<textarea required value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Mục tiêu, yêu cầu và kết quả mong đợi của công việc" /></label>
        <div className="create-modal__fields"><label>Loại<select value={type} onChange={(event) => setType(event.target.value as TaskType)}><option value="task">Task</option><option value="story">Story</option><option value="bug">Bug</option><option value="epic">Epic</option></select></label><label>Ưu tiên<select value={priority} onChange={(event) => setPriority(event.target.value as TaskPriority)}><option value="medium">Trung bình</option><option value="high">Cao</option><option value="urgent">Khẩn cấp</option><option value="low">Thấp</option></select></label></div>
        <fieldset className="assignee-picker" ref={assigneePickerRef}>
          <legend>Người thực hiện <span>(có thể chọn nhiều người)</span></legend>
          <div className="assignee-picker__control">
            <button
              className="assignee-picker__trigger"
              type="button"
              aria-expanded={assigneeOpen}
              aria-controls="assignee-options"
              onClick={() => setAssigneeOpen((open) => !open)}
            >
              <span>{assigneeIds.length ? `Đã chọn ${assigneeIds.length} người` : 'Chọn người thực hiện'}</span>
              <Icon name="chevron" size={17} />
            </button>
            {assigneeOpen && <div className="assignee-picker__dropdown" id="assignee-options">
              <label className="assignee-picker__search">
                <Icon name="search" size={18} />
                <input
                  autoFocus
                  value={assigneeQuery}
                  onChange={(event) => setAssigneeQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Escape') {
                      setAssigneeOpen(false)
                      setAssigneeQuery('')
                    }
                  }}
                  placeholder="Tìm theo tên hoặc email..."
                  aria-label="Tìm người thực hiện"
                />
              </label>
              <div className="assignee-picker__options" role="listbox" aria-multiselectable="true">
                {filteredMembers.map((member) => {
                  const selected = assigneeIds.includes(member.id)
                  return <button
                    className={selected ? 'selected' : ''}
                    type="button"
                    role="option"
                    aria-selected={selected}
                    key={member.id}
                    onClick={() => toggleAssignee(member.id)}
                  >
                    <Avatar user={member} size={29} />
                    <span><strong>{member.name}</strong><small>{member.email}</small></span>
                    {selected && <Icon name="check" size={18} />}
                  </button>
                })}
                {!filteredMembers.length && <p>Không tìm thấy thành viên phù hợp.</p>}
              </div>
            </div>}
          </div>
          {selectedMembers.length > 0 && <div className="assignee-picker__selected">
            {selectedMembers.map((member) => <span className="assignee-chip" key={member.id}>
              <Avatar user={member} size={25} />
              <span>{member.name}</span>
              <button type="button" onClick={() => toggleAssignee(member.id)} aria-label={`Bỏ chọn ${member.name}`}>
                <Icon name="close" size={13} />
              </button>
            </span>)}
          </div>}
        </fieldset>
        <div className="create-modal__fields"><label>Ngày bắt đầu<input type="date" required value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label><label>Ngày kết thúc<input type="date" required min={startDate} value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label></div>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <div className="create-modal__actions"><button type="button" className="secondary-button" onClick={onClose}>Hủy</button><button className="primary-button" type="submit" disabled={submitting}>{submitting ? 'Đang tạo...' : 'Tạo công việc'}</button></div>
      </form>
    </div>
  )
}

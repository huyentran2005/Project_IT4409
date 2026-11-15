import { useState } from 'react'
import type { Task, TimesheetInput } from '../../types/task'
import { Icon } from '../ui/Icon'

const todayKey = () => {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

interface LogTimeDrawerProps {
  tasks: Task[]
  defaultTaskId?: string
  onClose: () => void
  onSubmit: (taskId: string, input: TimesheetInput) => Promise<void>
}

/** Form "Thêm bản ghi timesheet": chọn task, ngày, số giờ, OT, ghi chú. */
export function LogTimeDrawer({ tasks, defaultTaskId, onClose, onSubmit }: LogTimeDrawerProps) {
  const [taskId, setTaskId] = useState(defaultTaskId ?? '')
  const [date, setDate] = useState(todayKey)
  const [hours, setHours] = useState('')
  const [overtime, setOvertime] = useState(false)
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const hoursValue = Number(hours.replace(',', '.'))
  const valid = Boolean(taskId && date && hours && hoursValue > 0 && hoursValue <= 24)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!valid) return
    setError('')
    setSubmitting(true)
    try {
      await onSubmit(taskId, { date, hours: hoursValue, isOvertime: overtime, note: note.trim() })
      onClose()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể ghi nhận giờ làm. Vui lòng thử lại.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <button className="drawer-scrim" onClick={onClose} aria-label="Đóng" />
      <aside className="timelog-drawer" aria-label="Thêm bản ghi timesheet">
        <header className="timelog-drawer__header"><button className="icon-button" onClick={onClose} aria-label="Đóng"><Icon name="close" /></button><h2>Thêm bản ghi timesheet</h2></header>
        <form className="timelog-form" onSubmit={submit}>
          <label>Ghi giờ cho <b>*</b>
            <select value={taskId} onChange={(event) => setTaskId(event.target.value)} required>
              <option value="">— Chọn task —</option>
              {tasks.map((task) => <option value={task.id} key={task.id}>{task.key} · {task.title}</option>)}
            </select>
          </label>
          <div className="timelog-form__row">
            <label>Ngày <b>*</b><input type="date" value={date} onChange={(event) => setDate(event.target.value)} required /></label>
            <label>Số giờ <b>*</b><input type="number" inputMode="decimal" step="0.25" min="0.25" max="24" value={hours} onChange={(event) => setHours(event.target.value)} placeholder="VD: 1.5" required /></label>
          </div>
          <label className="timelog-ot"><input type="checkbox" checked={overtime} onChange={(event) => setOvertime(event.target.checked)} /><span><strong>Giờ OT</strong><small>Làm ngoài giờ hành chính hoặc cuối tuần. Giờ OT không tính vào cảnh báo quá 8h/ngày.</small></span></label>
          <label>Ghi chú<textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength={2000} placeholder="VD: Debug callback, review PR…" /></label>
          {error && <p className="auth-error" role="alert">{error}</p>}
          {!tasks.length && <p className="timelog-hint">Dự án chưa có công việc nào để ghi giờ.</p>}
          <footer className="timelog-form__actions"><button type="button" className="text-button" onClick={onClose}>Hủy</button><button className="primary-button" type="submit" disabled={!valid || submitting}>{submitting ? 'Đang ghi...' : 'Ghi nhận'}</button></footer>
        </form>
      </aside>
    </>
  )
}

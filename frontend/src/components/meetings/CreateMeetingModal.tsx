import { useState } from 'react'
import type { MeetingDraft } from '../../types/meeting'
import type { ProjectSummary } from '../../types/task'
import { Avatar } from '../ui/Avatar'
import { Icon } from '../ui/Icon'

export function CreateMeetingModal({ project, onClose, onCreate }: { project: ProjectSummary; onClose: () => void; onCreate: (meeting: MeetingDraft) => Promise<void> | void }) {
  const [meeting, setMeeting] = useState<MeetingDraft>({ title: '', date: '2026-10-17', startTime: '09:00', endTime: '09:30', location: 'Google Meet', meetingUrl: '', description: '' })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const update = (field: keyof MeetingDraft, value: string) => setMeeting((current) => ({ ...current, [field]: value }))
  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!meeting.title.trim() || !meeting.meetingUrl.trim() || meeting.endTime <= meeting.startTime) return
    setError('')
    setSubmitting(true)
    try {
      await onCreate(meeting)
      onClose()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể tạo meeting. Vui lòng thử lại.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-layer" role="dialog" aria-modal="true" aria-label="Tạo meeting">
      <button className="modal-scrim" onClick={onClose} aria-label="Đóng" />
      <form className="create-modal meeting-modal" onSubmit={submit}>
        <div className="create-modal__header"><div><span>{project.name.toUpperCase()}</span><h2>Tạo meeting mới</h2></div><button type="button" className="icon-button" onClick={onClose}><Icon name="close" /></button></div>
        <label>Tiêu đề<input autoFocus required value={meeting.title} onChange={(event) => update('title', event.target.value)} placeholder="Ví dụ: Sprint planning tuần 4" /></label>
        <div className="create-modal__fields"><label>Ngày họp<input type="date" required value={meeting.date} onChange={(event) => update('date', event.target.value)} /></label><label>Địa điểm<select value={meeting.location} onChange={(event) => update('location', event.target.value)}><option>Google Meet</option><option>Microsoft Teams</option><option>Phòng họp A</option><option>Phòng họp B</option></select></label></div>
        <div className="create-modal__fields"><label>Bắt đầu<input type="time" required value={meeting.startTime} onChange={(event) => update('startTime', event.target.value)} /></label><label>Kết thúc<input type="time" required min={meeting.startTime} value={meeting.endTime} onChange={(event) => update('endTime', event.target.value)} /></label></div>
        <label className="meeting-description">Link tham gia<input type="url" required value={meeting.meetingUrl} onChange={(event) => update('meetingUrl', event.target.value)} placeholder="https://meet.google.com/abc-defg-hij" /></label>
        <label className="meeting-description">Nội dung<textarea value={meeting.description} onChange={(event) => update('description', event.target.value)} placeholder="Mục tiêu và nội dung chính của cuộc họp" /></label>
        <div className="meeting-attendees"><span>Người tham gia</span><div>{project.members.map((member) => <Avatar user={member} size={30} key={member.id} />)}<small>{project.members.length} thành viên</small></div></div>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <div className="create-modal__actions"><button type="button" className="secondary-button" onClick={onClose}>Hủy</button><button className="primary-button" type="submit" disabled={submitting}><Icon name="video" size={16} />{submitting ? 'Đang tạo...' : 'Tạo meeting'}</button></div>
      </form>
    </div>
  )
}

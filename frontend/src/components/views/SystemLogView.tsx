import { useMemo, useState } from 'react'
import { mockActivityLogs } from '../../data/mockData'
import type { ActivityLog } from '../../types/project'
import { Icon } from '../ui/Icon'

const actionLabels: Record<ActivityLog['action'], string> = {
  created: 'Tạo mới', updated: 'Cập nhật', deleted: 'Xóa', logged_time: 'Ghi giờ', meeting_created: 'Meeting',
}

const relativeTime = (date: string) => {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(date).getTime()) / 60000))
  if (minutes < 60) return `${minutes} phút trước`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} giờ trước`
  return new Intl.DateTimeFormat('vi-VN').format(new Date(date))
}

export function SystemLogView() {
  const [action, setAction] = useState('all')
  const [entity, setEntity] = useState('all')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const logs = useMemo(() => mockActivityLogs.filter((log) => (
    (action === 'all' || log.action === action)
    && (entity === 'all' || log.entityType === entity)
    && (!fromDate || new Date(log.createdAt) >= new Date(`${fromDate}T00:00:00`))
    && (!toDate || new Date(log.createdAt) <= new Date(`${toDate}T23:59:59`))
  )), [action, entity, fromDate, toDate])

  return (
    <section className="system-log-view">
      <header><h2>Nhật ký thay đổi</h2><p>Toàn bộ hoạt động tạo, cập nhật và thay đổi trong dự án — ai làm gì và khi nào.</p></header>
      <div className="log-filters">
        <select value={action} onChange={(event) => setAction(event.target.value)}><option value="all">Mọi hành động</option><option value="created">Tạo mới</option><option value="updated">Cập nhật</option><option value="logged_time">Ghi giờ</option><option value="meeting_created">Meeting</option><option value="deleted">Xóa</option></select>
        <select value={entity} onChange={(event) => setEntity(event.target.value)}><option value="all">Mọi đối tượng</option><option value="task">Công việc</option><option value="timesheet">Timesheet</option><option value="meeting">Meeting</option><option value="document">Tài liệu</option><option value="member">Thành viên</option></select>
        <label>Từ ngày<input type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} /></label><label>Đến ngày<input type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} /></label><strong>{logs.length} hoạt động</strong>
      </div>
      <h3>GẦN ĐÂY</h3>
      <div className="log-list">{logs.map((log) => <article key={log.id}><span className={`log-action log-action--${log.action}`}><Icon name={log.action === 'created' || log.action === 'logged_time' ? 'plus' : log.action === 'meeting_created' ? 'video' : 'check'} size={17} /></span><span className="log-avatar">{log.actorInitials}</span><div><p><strong>{log.actor}</strong> {log.description}</p><small>{relativeTime(log.createdAt)} · {log.changeCount} trường thay đổi</small></div><i>{actionLabels[log.action]}</i><Icon name="chevron" size={17} /></article>)}{!logs.length && <div className="view-empty">Không có hoạt động phù hợp với bộ lọc.</div>}</div>
    </section>
  )
}

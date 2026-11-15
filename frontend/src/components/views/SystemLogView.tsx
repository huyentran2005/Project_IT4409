import { useEffect, useMemo, useState } from 'react'
import type { ActivityLog } from '../../types/project'
import { projectApi } from '../../services/projectApi'
import { Icon } from '../ui/Icon'

const actionLabels: Record<ActivityLog['action'], string> = {
  created: 'Tạo mới', updated: 'Cập nhật', deleted: 'Xóa', logged_time: 'Ghi giờ', meeting_created: 'Meeting',
}

const emptyLogs: ActivityLog[] = []

interface LogResult {
  key: string
  logs: ActivityLog[]
  error: string
}

const relativeTime = (date: string) => {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(date).getTime()) / 60000))
  if (minutes < 60) return `${minutes} phút trước`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} giờ trước`
  return new Intl.DateTimeFormat('vi-VN').format(new Date(date))
}

export function SystemLogView({ projectId }: { projectId: string }) {
  const [action, setAction] = useState('all')
  const [entity, setEntity] = useState('all')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<LogResult | null>(null)
  const requestKey = `${projectId}:${attempt}`
  const loading = result?.key !== requestKey
  const error = loading ? '' : result.error
  const activityLogs = loading ? emptyLogs : result.logs

  useEffect(() => {
    let cancelled = false
    projectApi.getActivityLogs(projectId)
      .then((logs) => {
        if (!cancelled) setResult({ key: requestKey, logs, error: '' })
      })
      .catch(() => {
        if (!cancelled) setResult({ key: requestKey, logs: [], error: 'Không tải được nhật ký. Vui lòng thử lại.' })
      })
    return () => { cancelled = true }
  }, [projectId, requestKey])

  const logs = useMemo(() => activityLogs.filter((log) => (
    (action === 'all' || log.action === action)
    && (entity === 'all' || log.entityType === entity)
    && (!fromDate || new Date(log.createdAt) >= new Date(`${fromDate}T00:00:00`))
    && (!toDate || new Date(log.createdAt) <= new Date(`${toDate}T23:59:59`))
  )), [action, activityLogs, entity, fromDate, toDate])

  return (
    <section className="system-log-view">
      <header><h2>Nhật ký thay đổi</h2><p>Các hoạt động đã được ghi nhận trong dự án — ai làm gì và khi nào.</p><button className="secondary-button" type="button" disabled={loading} onClick={() => setAttempt((value) => value + 1)}>Làm mới nhật ký</button></header>
      <div className="log-filters">
        <select value={action} onChange={(event) => setAction(event.target.value)}><option value="all">Mọi hành động</option><option value="created">Tạo mới</option><option value="updated">Cập nhật</option><option value="logged_time">Ghi giờ</option><option value="meeting_created">Meeting</option><option value="deleted">Xóa</option></select>
        <select value={entity} onChange={(event) => setEntity(event.target.value)}><option value="all">Mọi đối tượng</option><option value="task">Công việc</option><option value="timesheet">Timesheet</option><option value="meeting">Meeting</option><option value="document">Tài liệu</option><option value="member">Thành viên</option></select>
        <label>Từ ngày<input type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} /></label><label>Đến ngày<input type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} /></label>{!loading && !error && <strong>{logs.length} hoạt động</strong>}
      </div>
      <h3>GẦN ĐÂY</h3>
      <div className="log-list" aria-busy={loading}>
        {loading && <div className="view-empty" role="status">Đang tải nhật ký...</div>}
        {error && <div className="view-empty" role="alert"><p>{error}</p><button className="primary-button" type="button" onClick={() => setAttempt((value) => value + 1)}>Thử lại</button></div>}
        {!loading && !error && <>{logs.map((log) => (
          <article className="log-entry" key={log.id}>
            <span className={`log-action log-action--${log.action}`}><Icon name={log.action === 'created' || log.action === 'logged_time' ? 'plus' : log.action === 'meeting_created' ? 'video' : 'check'} size={17} /></span>
            <span className="log-avatar">{log.actorInitials}</span>
            <div className="log-entry-content">
              <p><strong>{log.actor}</strong> {log.description}</p>
              <small>{relativeTime(log.createdAt)} · {log.changeCount} trường được ghi nhận</small>
              {!!log.changeDetails?.length && <dl className="log-changes">
                {log.changeDetails.map((change) => <div className="log-change" key={change.field}>
                  <dt>{change.label}</dt>
                  <dd>
                    {change.hasPreviousValue ? <>
                      <div className="log-change-value"><span className="log-change-caption">Trước</span><span>{change.oldValue ?? 'Chưa có'}</span></div>
                      <span className="log-change-arrow" aria-label="thay đổi thành">→</span>
                      <div className="log-change-value"><span className="log-change-caption">Sau</span><span>{change.newValue ?? 'Chưa có'}</span></div>
                    </> : <div className="log-change-value"><span>{change.newValue ?? 'Chưa có'}</span></div>}
                  </dd>
                </div>)}
              </dl>}
              {log.action === 'updated' && !log.changeDetails?.length && <small>Nhật ký này chưa lưu chi tiết thay đổi.</small>}
            </div>
            <i>{actionLabels[log.action]}</i>
          </article>
        ))}{!logs.length && <div className="view-empty">{activityLogs.length ? 'Không có hoạt động phù hợp với bộ lọc.' : 'Dự án chưa có hoạt động được ghi nhận.'}</div>}</>}
      </div>
    </section>
  )
}

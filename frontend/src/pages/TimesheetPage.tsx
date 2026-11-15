import { useCallback, useEffect, useMemo, useState } from 'react'
import { taskApi } from '../services/taskApi'
import type { TimesheetEntry, TimesheetList } from '../types/task'
import { Icon } from '../components/ui/Icon'

type RangeKey = 'today' | 'week' | 'month' | 'all' | 'custom'

const pad = (value: number) => String(value).padStart(2, '0')
const toKey = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
const formatHours = (minutes: number) => `${Math.floor(minutes / 60)}h${minutes % 60 ? ` ${minutes % 60}m` : ''}`
const formatDay = (key: string) => new Intl.DateTimeFormat('vi-VN', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(`${key}T00:00:00`))
const formatTime = (iso: string) => new Intl.DateTimeFormat('vi-VN', { hour: '2-digit', minute: '2-digit' }).format(new Date(iso))

function presetRange(range: RangeKey): { from: string; to: string } {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  if (range === 'today') return { from: toKey(today), to: toKey(today) }
  if (range === 'week') {
    const monday = new Date(today); monday.setDate(today.getDate() - ((today.getDay() + 6) % 7))
    const sunday = new Date(monday); sunday.setDate(monday.getDate() + 6)
    return { from: toKey(monday), to: toKey(sunday) }
  }
  if (range === 'month') return { from: toKey(new Date(today.getFullYear(), today.getMonth(), 1)), to: toKey(new Date(today.getFullYear(), today.getMonth() + 1, 0)) }
  return { from: '', to: '' }
}

interface TimesheetPageProps {
  /** Tăng lên mỗi khi có bản ghi mới để tải lại danh sách. */
  version: number
  onAdd: () => void
}

export function TimesheetPage({ version, onAdd }: TimesheetPageProps) {
  const [tab, setTab] = useState<'log' | 'chart'>('log')
  const [range, setRange] = useState<RangeKey>('all')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [overtimeOnly, setOvertimeOnly] = useState(false)
  const [data, setData] = useState<TimesheetList>({ entries: [], totalMinutes: 0, overtimeMinutes: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  const choose = (next: RangeKey) => {
    const preset = presetRange(next)
    setRange(next); setFrom(preset.from); setTo(preset.to)
  }

  const load = useCallback(() => {
    taskApi.listMyTimesheets({ dateFrom: from || undefined, dateTo: to || undefined, overtimeOnly })
      .then((result) => { setData(result); setError('') })
      .catch((reason) => setError(reason instanceof Error ? reason.message : 'Không tải được timesheet.'))
      .finally(() => setLoading(false))
  }, [from, to, overtimeOnly])

  useEffect(() => { load() }, [load, version, reloadKey])

  const removeEntry = async (entry: TimesheetEntry) => {
    if (!window.confirm('Xóa bản ghi timesheet này?')) return
    try {
      await taskApi.deleteTimesheet(entry.id)
      setReloadKey((value) => value + 1)
    } catch (reason) {
      alert(reason instanceof Error ? reason.message : 'Không thể xóa bản ghi.')
    }
  }

  const days = useMemo(() => {
    const grouped = new Map<string, TimesheetEntry[]>()
    for (const entry of data.entries) {
      const key = entry.date ?? entry.startTime.slice(0, 10)
      grouped.set(key, [...(grouped.get(key) ?? []), entry])
    }
    return Array.from(grouped.entries()).sort((a, b) => b[0].localeCompare(a[0]))
  }, [data.entries])

  const chartDays = useMemo(() => [...days].reverse().slice(-31).map(([key, entries]) => ({
    key,
    normal: entries.filter((entry) => !entry.isOvertime).reduce((sum, entry) => sum + entry.minutes, 0),
    overtime: entries.filter((entry) => entry.isOvertime).reduce((sum, entry) => sum + entry.minutes, 0),
  })), [days])
  const chartMax = Math.max(...chartDays.map((day) => day.normal + day.overtime), 60)

  return (
    <main className="dashboard-page timesheet-page">
      <header className="dashboard-heading">
        <div><h1>Timesheet</h1><p>Nhật ký giờ làm việc của bạn trên tất cả dự án.</p></div>
        <button className="primary-button" onClick={onAdd}><Icon name="plus" size={16} />Thêm bản ghi mới</button>
      </header>

      <nav className="timesheet-tabs"><button className={tab === 'log' ? 'active' : ''} onClick={() => setTab('log')}>Nhật ký</button><button className={tab === 'chart' ? 'active' : ''} onClick={() => setTab('chart')}>Biểu đồ</button></nav>

      <section className="timesheet-filters">
        <div className="timesheet-range">{([['today', 'Hôm nay'], ['week', 'Tuần này'], ['month', 'Tháng này'], ['all', 'Tất cả']] as [RangeKey, string][]).map(([key, label]) => <button className={range === key ? 'active' : ''} onClick={() => choose(key)} key={key}>{label}</button>)}</div>
        <label className="timesheet-date"><span>Từ ngày</span><input type="date" value={from} max={to || undefined} onChange={(event) => { setRange('custom'); setFrom(event.target.value) }} /></label>
        <span>—</span>
        <label className="timesheet-date"><span>Đến ngày</span><input type="date" value={to} min={from || undefined} onChange={(event) => { setRange('custom'); setTo(event.target.value) }} /></label>
        <button className={`timesheet-ot-toggle ${overtimeOnly ? 'active' : ''}`} onClick={() => setOvertimeOnly((value) => !value)} aria-pressed={overtimeOnly}><b>OT</b>Chỉ giờ OT</button>
        <div className="timesheet-total">Tổng cộng: <strong>{formatHours(data.totalMinutes)}</strong>{data.overtimeMinutes > 0 && <small> (OT {formatHours(data.overtimeMinutes)})</small>}</div>
      </section>

      {error && <p className="auth-error" role="alert">{error}</p>}
      {loading && !data.entries.length && <div className="timesheet-empty">Đang tải...</div>}
      {!loading && !data.entries.length && !error && <div className="timesheet-empty">Không có bản ghi timesheet nào khớp với bộ lọc hiện tại.</div>}

      {tab === 'log' && days.map(([key, entries]) => {
        const dayMinutes = entries.reduce((sum, entry) => sum + entry.minutes, 0)
        const regularMinutes = entries.filter((entry) => !entry.isOvertime).reduce((sum, entry) => sum + entry.minutes, 0)
        return (
          <section className="timesheet-day" key={key}>
            <header><h2>{formatDay(key)}</h2><span className={regularMinutes > 480 ? 'over-limit' : ''}>{formatHours(dayMinutes)}{regularMinutes > 480 && ' · vượt 8h'}</span></header>
            {entries.map((entry) => (
              <article className="timesheet-row" key={entry.id}>
                <span className="timesheet-row__key">{entry.taskKey}</span>
                <div><strong>{entry.taskTitle}</strong><small>{entry.projectName}{entry.note ? ` · ${entry.note}` : ''}</small></div>
                {entry.isOvertime && <em className="ot-badge">OT</em>}
                <time>{formatTime(entry.startTime)}–{formatTime(entry.endTime)}</time>
                <b>{formatHours(entry.minutes)}</b>
                <button className="icon-button entry-delete" onClick={() => removeEntry(entry)} aria-label="Xóa bản ghi"><Icon name="trash" size={15} /></button>
              </article>
            ))}
          </section>
        )
      })}

      {tab === 'chart' && chartDays.length > 0 && (
        <section className="dashboard-panel timesheet-chart-panel">
          <header><h2>Giờ làm theo ngày</h2><span><i className="legend legend--normal" />Giờ thường <i className="legend legend--ot" />OT</span></header>
          <div className="timesheet-bars">{chartDays.map((day) => (
            <div className="timesheet-bar" key={day.key} title={`${formatDay(day.key)}: ${formatHours(day.normal + day.overtime)}${day.overtime ? ` (OT ${formatHours(day.overtime)})` : ''}`}>
              <div><span className="timesheet-bar__ot" style={{ height: `${day.overtime / chartMax * 100}%` }} /><span className="timesheet-bar__normal" style={{ height: `${day.normal / chartMax * 100}%` }} /></div>
              <small>{day.key.slice(8)}/{day.key.slice(5, 7)}</small>
            </div>
          ))}</div>
        </section>
      )}
    </main>
  )
}

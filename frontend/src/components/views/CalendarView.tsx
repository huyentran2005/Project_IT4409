import { useState } from 'react'
import type { Task } from '../../types/task'
import type { Meeting } from '../../types/meeting'
import { Icon } from '../ui/Icon'

const weekdays = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']

export function CalendarView({ tasks, meetings, onOpenTask }: { tasks: Task[]; meetings: Meeting[]; onOpenTask: (task: Task) => void }) {
  const today = new Date()
  const [visibleMonth, setVisibleMonth] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1))
  const year = visibleMonth.getFullYear()
  const month = visibleMonth.getMonth()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const mondayOffset = (new Date(year, month, 1).getDay() + 6) % 7
  const cells = Array.from({ length: Math.ceil((mondayOffset + daysInMonth) / 7) * 7 }, (_, index) => {
    const day = index - mondayOffset + 1
    return day > 0 && day <= daysInMonth ? day : null
  })
  const tasksForDay = (day: number) => tasks.filter((task) => {
    const end = new Date(`${task.endDate}T00:00:00`)
    return end.getFullYear() === year && end.getMonth() === month && end.getDate() === day
  })
  const meetingsForDay = (day: number) => meetings.filter((meeting) => {
    const date = new Date(`${meeting.date}T00:00:00`)
    return date.getFullYear() === year && date.getMonth() === month && date.getDate() === day
  })
  const changeMonth = (offset: number) => {
    setVisibleMonth((current) => new Date(current.getFullYear(), current.getMonth() + offset, 1))
  }
  const goToToday = () => setVisibleMonth(new Date(today.getFullYear(), today.getMonth(), 1))
  const isToday = (day: number) => (
    day === today.getDate()
    && month === today.getMonth()
    && year === today.getFullYear()
  )

  return (
    <section className="calendar-view" aria-label="Lịch công việc">
      <header>
        <div className="calendar-heading">
          <div><h2>Tháng {month + 1}, {year}</h2><p>Deadline công việc và lịch meeting của dự án</p></div>
          <div className="calendar-navigation">
            <button className="calendar-navigation__previous" type="button" onClick={() => changeMonth(-1)} aria-label="Tháng trước"><Icon name="chevron" size={16} /></button>
            <button className="calendar-navigation__today" type="button" onClick={goToToday}>Hôm nay</button>
            <button type="button" onClick={() => changeMonth(1)} aria-label="Tháng sau"><Icon name="chevron" size={16} /></button>
          </div>
        </div>
        <div className="calendar-legends"><div className="calendar-legend"><span /><small>Deadline</small></div><div className="calendar-legend calendar-legend--meeting"><span /><small>Meeting</small></div></div>
      </header>
      <div className="calendar-grid">
        {weekdays.map((day) => <strong className="calendar-weekday" key={day}>{day}</strong>)}
        {cells.map((day, index) => <div className={`calendar-day ${day && isToday(day) ? 'calendar-day--today' : ''}`} key={index}>{day && <><time>{day}</time>{meetingsForDay(day).map((meeting) => <a className="calendar-meeting" href={meeting.meetingUrl} target="_blank" rel="noreferrer" title={`Mở ${meeting.location}`} key={meeting.id}><Icon name="video" size={11} /><span>{meeting.startTime}</span>{meeting.title}</a>)}{tasksForDay(day).slice(0, 3).map((task) => <button className={`calendar-task calendar-task--${task.status}`} onClick={() => onOpenTask(task)} key={task.id}><span>{task.key}</span>{task.title}</button>)}</>}</div>)}
      </div>
    </section>
  )
}

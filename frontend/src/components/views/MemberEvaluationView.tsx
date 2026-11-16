import { useEffect, useState } from 'react'
import { evaluationApi } from '../../services/evaluationApi'
import type {
  EvaluationGrade, EvaluationRules, MemberEvaluation, MemberEvaluationDetail, ProjectEvaluation, TaskEvaluationResult,
} from '../../types/evaluation'
import { Avatar } from '../ui/Avatar'

const resultLabels: Record<TaskEvaluationResult, string> = {
  on_time: 'Đúng hạn', late: 'Trễ hạn', not_submitted: 'Chưa nộp',
}

const formatDate = (value: string) => new Intl.DateTimeFormat('vi-VN').format(new Date(value))
const formatDateTime = (value: string) => new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value))
const percent = (value: number | null) => (value === null ? '—' : `${value}%`)

function GradeBadge({ grade, label }: { grade: EvaluationGrade; label: string }) {
  return <span className={`evaluation-grade evaluation-grade--${grade}`}>{label}</span>
}

function RulesNote({ rules }: { rules: EvaluationRules }) {
  return (
    <details className="evaluation-rules">
      <summary>Cách tính điểm</summary>
      <ul>
        <li>Điểm = {rules.timelinessWeight * 100}% <strong>Đúng hạn</strong> + {rules.qualityWeight * 100}% <strong>Chất lượng</strong>.</li>
        <li><strong>Đúng hạn</strong>: tỉ lệ task được nộp lần đầu (vào cột “Đang duyệt” hoặc “Hoàn thành”) không muộn hơn ngày kết thúc.</li>
        <li><strong>Chất lượng</strong>: mỗi task bắt đầu từ 100%, mỗi lần bị người khác trả lại trừ {rules.returnPenalty * 100}%.</li>
        <li>Chỉ tính task đã hoàn thành hoặc đã quá hạn. Cần ít nhất {rules.minTasks} task mới có điểm.</li>
        <li>Xếp loại: Xuất sắc ≥ {rules.thresholds.excellent}, Tốt ≥ {rules.thresholds.good}, Đạt ≥ {rules.thresholds.pass}, còn lại là Cần cải thiện.</li>
      </ul>
    </details>
  )
}

function MemberDetail({ projectId, member, from, to, onClose }: {
  projectId: string; member: MemberEvaluation; from: string; to: string; onClose: () => void
}) {
  const [state, setState] = useState<{ key: string; data: MemberEvaluationDetail | null; error: string } | null>(null)
  const key = `${member.user.id}:${from}:${to}`
  const loading = state?.key !== key

  useEffect(() => {
    let cancelled = false
    evaluationApi.detail(projectId, member.user.id, { from, to })
      .then((data) => { if (!cancelled) setState({ key, data, error: '' }) })
      .catch((error: Error) => { if (!cancelled) setState({ key, data: null, error: error.message || 'Không tải được chi tiết.' }) })
    return () => { cancelled = true }
  }, [projectId, member.user.id, from, to, key])

  return (
    <section className="evaluation-detail" aria-label={`Chi tiết đánh giá của ${member.user.name}`}>
      <header>
        <Avatar user={member.user} size={34} />
        <div><h3>{member.user.name}</h3><small>{member.evaluatedTasks} task được đánh giá · {member.returnCount} lần bị trả lại</small></div>
        <button className="secondary-button" type="button" onClick={onClose}>Đóng</button>
      </header>
      {loading && <div className="view-empty" role="status">Đang tải chi tiết...</div>}
      {!loading && state.error && <div className="view-empty" role="alert">{state.error}</div>}
      {!loading && state.data && (state.data.tasks.length === 0
        ? <div className="view-empty">Chưa có task nào được đánh giá trong khoảng thời gian này.</div>
        : <div className="evaluation-table-wrap"><table className="evaluation-table">
          <thead><tr><th>Task</th><th>Hạn</th><th>Nộp lần đầu</th><th>Kết quả</th><th>Bị trả lại</th><th>Chất lượng</th></tr></thead>
          <tbody>{state.data.tasks.map((task) => (
            <tr key={task.id}>
              <td><strong>{task.key}</strong> {task.title}<small>{task.statusName}</small></td>
              <td>{formatDate(task.deadline)}</td>
              <td>{task.submittedAt ? formatDateTime(task.submittedAt) : '—'}</td>
              <td><span className={`evaluation-result evaluation-result--${task.result}`}>{resultLabels[task.result]}</span></td>
              <td>{task.returnCount}</td>
              <td>{percent(task.qualityScore)}</td>
            </tr>
          ))}</tbody>
        </table></div>)}
    </section>
  )
}

export function MemberEvaluationView({ projectId }: { projectId: string }) {
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [state, setState] = useState<{ key: string; data: ProjectEvaluation | null; error: string } | null>(null)
  const rangeInvalid = !!from && !!to && from > to
  const key = `${projectId}:${from}:${to}:${attempt}`
  const loading = !rangeInvalid && state?.key !== key

  useEffect(() => {
    if (rangeInvalid) return
    let cancelled = false
    evaluationApi.list(projectId, { from, to })
      .then((data) => { if (!cancelled) setState({ key, data, error: '' }) })
      .catch((error: Error) => { if (!cancelled) setState({ key, data: null, error: error.message || 'Không tải được đánh giá.' }) })
    return () => { cancelled = true }
  }, [projectId, from, to, key, rangeInvalid])

  const data = state?.key === key ? state.data : null
  const error = state?.key === key ? state.error : ''
  const selected = data?.members.find((member) => member.user.id === selectedId) ?? null

  return (
    <section className="evaluation-view">
      <header>
        <div><h2>Đánh giá mức độ hoàn thành</h2><p>Dựa trên việc hoàn thành đúng hạn và số lần task bị trả lại.</p></div>
        <button className="secondary-button" type="button" disabled={loading} onClick={() => setAttempt((value) => value + 1)}>Làm mới</button>
      </header>
      <div className="evaluation-filters">
        <label>Hạn từ ngày<input type="date" value={from} max={to || undefined} onChange={(event) => setFrom(event.target.value)} /></label>
        <label>Đến ngày<input type="date" value={to} min={from || undefined} onChange={(event) => setTo(event.target.value)} /></label>
        {(from || to) && <button className="secondary-button" type="button" onClick={() => { setFrom(''); setTo('') }}>Xóa lọc</button>}
      </div>
      {rangeInvalid && <div className="view-empty" role="alert">Ngày bắt đầu không được sau ngày kết thúc.</div>}
      {loading && <div className="view-empty" role="status">Đang tải đánh giá...</div>}
      {error && <div className="view-empty" role="alert"><p>{error}</p><button className="primary-button" type="button" onClick={() => setAttempt((value) => value + 1)}>Thử lại</button></div>}
      {data && !rangeInvalid && <>
        {!data.canViewAll && <p className="evaluation-hint">Bạn chỉ xem được đánh giá của chính mình.</p>}
        <div className="evaluation-table-wrap"><table className="evaluation-table evaluation-table--members">
          <thead><tr><th>Thành viên</th><th>Task</th><th>Đúng hạn</th><th>Trả lại</th><th>Chất lượng</th><th>Điểm</th><th>Xếp loại</th></tr></thead>
          <tbody>{data.members.map((member) => (
            <tr key={member.user.id} className={member.user.id === selectedId ? 'selected' : ''}>
              <td><button type="button" className="evaluation-member" onClick={() => setSelectedId(member.user.id === selectedId ? null : member.user.id)}><Avatar user={member.user} size={28} />{member.user.name}</button></td>
              <td>{member.evaluatedTasks}</td>
              <td>{member.onTimeTasks}/{member.evaluatedTasks}<small>{percent(member.timelinessScore)}</small></td>
              <td>{member.returnCount}</td>
              <td>{percent(member.qualityScore)}</td>
              <td><strong>{member.score ?? '—'}</strong></td>
              <td><GradeBadge grade={member.grade} label={member.gradeLabel} /></td>
            </tr>
          ))}</tbody>
        </table></div>
        {data.members.length === 0 && <div className="view-empty">Dự án chưa có thành viên.</div>}
        {selected && <MemberDetail projectId={projectId} member={selected} from={from} to={to} onClose={() => setSelectedId(null)} />}
        <RulesNote rules={data.rules} />
      </>}
    </section>
  )
}

import { useState } from 'react'
import type { CreateProjectInput } from '../../types/task'
import { Icon } from '../ui/Icon'

const projectColors = ['#5b5ce2', '#2563eb', '#0f9f8f', '#d97706', '#dc4c64', '#8b5cf6']

interface CreateProjectModalProps {
  onClose: () => void
  onCreate: (input: CreateProjectInput) => void | Promise<void>
}

export function CreateProjectModal({ onClose, onCreate }: CreateProjectModalProps) {
  const [name, setName] = useState('')
  const [key, setKey] = useState('')
  const [description, setDescription] = useState('')
  const [color, setColor] = useState(projectColors[0])
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!name.trim() || !key.trim() || !description.trim()) return
    setSubmitting(true)
    setError('')
    try {
      await onCreate({ name: name.trim(), key: key.trim().toUpperCase(), description: description.trim(), color })
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo dự án. Vui lòng thử lại.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-layer" role="dialog" aria-modal="true" aria-label="Tạo dự án">
      <button className="modal-scrim" onClick={onClose} aria-label="Đóng" />
      <form className="create-modal create-project-modal" onSubmit={submit}>
        <div className="create-modal__header"><div><span>DỰ ÁN MỚI</span><h2>Tạo dự án</h2></div><button type="button" className="icon-button" onClick={onClose}><Icon name="close" /></button></div>
        <label>Tên dự án<input autoFocus required value={name} onChange={(event) => setName(event.target.value)} placeholder="Ví dụ: Website thương mại điện tử" /></label>
        <label className="project-description-field">Mô tả<textarea required value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Mục tiêu và phạm vi của dự án" /></label>
        <div className="create-modal__fields"><label>Mã dự án<input required maxLength={8} value={key} onChange={(event) => setKey(event.target.value.replace(/[^a-zA-Z0-9]/g, ''))} placeholder="VD: WEB" /></label><fieldset className="project-color-picker"><legend>Màu dự án</legend><div>{projectColors.map((item) => <button type="button" className={color === item ? 'selected' : ''} style={{ background: item }} onClick={() => setColor(item)} aria-label={`Chọn màu ${item}`} key={item}>{color === item ? '✓' : ''}</button>)}</div></fieldset></div>
        {error && <p role="alert" style={{ color: '#dc2626', fontSize: 13, margin: 0 }}>{error}</p>}
        <div className="create-modal__actions"><button type="button" className="secondary-button" onClick={onClose}>Hủy</button><button className="primary-button" type="submit" disabled={submitting}>{submitting ? 'Đang tạo...' : 'Tạo dự án'}</button></div>
      </form>
    </div>
  )
}

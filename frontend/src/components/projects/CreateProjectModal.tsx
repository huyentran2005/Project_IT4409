import { useState } from 'react'
import type { CreateProjectInput } from '../../types/task'
import { Icon } from '../ui/Icon'

const projectColors = ['#5b5ce2', '#2563eb', '#0f9f8f', '#d97706', '#dc4c64', '#8b5cf6']

interface CreateProjectModalProps {
  onClose: () => void
  onCreate: (input: CreateProjectInput) => void
}

export function CreateProjectModal({ onClose, onCreate }: CreateProjectModalProps) {
  const [name, setName] = useState('')
  const [key, setKey] = useState('')
  const [description, setDescription] = useState('')
  const [color, setColor] = useState(projectColors[0])

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!name.trim() || !key.trim() || !description.trim()) return
    onCreate({ name: name.trim(), key: key.trim().toUpperCase(), description: description.trim(), color })
    onClose()
  }

  return (
    <div className="modal-layer" role="dialog" aria-modal="true" aria-label="Tạo dự án">
      <button className="modal-scrim" onClick={onClose} aria-label="Đóng" />
      <form className="create-modal create-project-modal" onSubmit={submit}>
        <div className="create-modal__header"><div><span>DỰ ÁN MỚI</span><h2>Tạo dự án</h2></div><button type="button" className="icon-button" onClick={onClose}><Icon name="close" /></button></div>
        <label>Tên dự án<input autoFocus required value={name} onChange={(event) => setName(event.target.value)} placeholder="Ví dụ: Website thương mại điện tử" /></label>
        <label className="project-description-field">Mô tả<textarea required value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Mục tiêu và phạm vi của dự án" /></label>
        <div className="create-modal__fields"><label>Mã dự án<input required maxLength={8} value={key} onChange={(event) => setKey(event.target.value.replace(/[^a-zA-Z0-9]/g, ''))} placeholder="VD: WEB" /></label><fieldset className="project-color-picker"><legend>Màu dự án</legend><div>{projectColors.map((item) => <button type="button" className={color === item ? 'selected' : ''} style={{ background: item }} onClick={() => setColor(item)} aria-label={`Chọn màu ${item}`} key={item}>{color === item ? '✓' : ''}</button>)}</div></fieldset></div>
        <div className="create-modal__actions"><button type="button" className="secondary-button" onClick={onClose}>Hủy</button><button className="primary-button" type="submit">Tạo dự án</button></div>
      </form>
    </div>
  )
}

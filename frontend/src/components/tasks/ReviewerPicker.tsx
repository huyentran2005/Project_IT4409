import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { UserSummary } from '../../types/task'
import { Avatar } from '../ui/Avatar'
import { Icon } from '../ui/Icon'

interface ReviewerPickerProps {
  members: UserSummary[]
  reviewer?: UserSummary
  required?: boolean
  onChange: (reviewer: UserSummary) => void
}

export function ReviewerPicker({ members, reviewer, required = false, onChange }: ReviewerPickerProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const pickerRef = useRef<HTMLDivElement>(null)
  const optionsId = useId()
  const filteredMembers = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase('vi')
    if (!normalizedQuery) return members
    return members.filter((member) => `${member.name} ${member.email}`.toLocaleLowerCase('vi').includes(normalizedQuery))
  }, [members, query])

  useEffect(() => {
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!pickerRef.current?.contains(event.target as Node)) {
        setOpen(false)
        setQuery('')
      }
    }
    document.addEventListener('mousedown', closeOnOutsideClick)
    return () => document.removeEventListener('mousedown', closeOnOutsideClick)
  }, [])

  const selectReviewer = (member: UserSummary) => {
    onChange(member)
    setOpen(false)
    setQuery('')
  }

  return (
    <div className="assignee-picker reviewer-picker" ref={pickerRef}>
      <div className="assignee-picker__control">
        <button
          className="assignee-picker__trigger"
          type="button"
          aria-expanded={open}
          aria-controls={optionsId}
          aria-invalid={required && !reviewer}
          onClick={() => setOpen((current) => !current)}
        >
          <span>{reviewer ? 'Đã chọn 1 người' : 'Chọn người duyệt'}</span>
          <Icon name="chevron" size={17} />
        </button>
        {open && <div className="assignee-picker__dropdown" id={optionsId}>
          <label className="assignee-picker__search">
            <Icon name="search" size={18} />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  setOpen(false)
                  setQuery('')
                }
              }}
              placeholder="Tìm theo tên hoặc email..."
              aria-label="Tìm người duyệt"
            />
          </label>
          <div className="assignee-picker__options" role="listbox">
            {filteredMembers.map((member) => {
              const selected = reviewer?.id === member.id
              return <button className={selected ? 'selected' : ''} type="button" role="option" aria-selected={selected} key={member.id} onClick={() => selectReviewer(member)}>
                <Avatar user={member} size={29} />
                <span><strong>{member.name}</strong><small>{member.email}</small></span>
                {selected && <Icon name="check" size={18} />}
              </button>
            })}
            {!filteredMembers.length && <p>Không tìm thấy thành viên phù hợp.</p>}
          </div>
        </div>}
      </div>
      {reviewer && <div className="assignee-picker__selected">
        <span className="assignee-chip"><Avatar user={reviewer} size={25} /><span>{reviewer.name}</span></span>
      </div>}
      {required && !reviewer && <small className="reviewer-picker__message">Hãy chọn người duyệt để chuyển sang “Đang duyệt”.</small>}
    </div>
  )
}

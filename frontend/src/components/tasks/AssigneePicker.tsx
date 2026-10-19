import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { UserSummary } from '../../types/task'
import { Avatar } from '../ui/Avatar'
import { Icon } from '../ui/Icon'

interface AssigneePickerProps {
  members: UserSummary[]
  selectedIds: string[]
  onChange: (selectedIds: string[]) => void
}

export function AssigneePicker({ members, selectedIds, onChange }: AssigneePickerProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const pickerRef = useRef<HTMLFieldSetElement>(null)
  const optionsId = useId()
  const selectedMembers = useMemo(() => members.filter((member) => selectedIds.includes(member.id)), [members, selectedIds])
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

  const toggleMember = (memberId: string) => {
    onChange(selectedIds.includes(memberId)
      ? selectedIds.filter((id) => id !== memberId)
      : [...selectedIds, memberId])
  }

  return (
    <fieldset className="assignee-picker assignee-picker--compact" ref={pickerRef}>
      <div className="assignee-picker__control">
        <button className="assignee-picker__trigger" type="button" aria-expanded={open} aria-controls={optionsId} onClick={() => setOpen((current) => !current)}>
          <span>{selectedIds.length ? `Đã chọn ${selectedIds.length} người` : 'Chọn người thực hiện'}</span>
          <Icon name="chevron" size={17} />
        </button>
        {open && <div className="assignee-picker__dropdown" id={optionsId}>
          <label className="assignee-picker__search"><Icon name="search" size={18} /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Escape') { setOpen(false); setQuery('') } }} placeholder="Tìm theo tên hoặc email..." aria-label="Tìm người thực hiện" /></label>
          <div className="assignee-picker__options" role="listbox" aria-multiselectable="true">
            {filteredMembers.map((member) => {
              const selected = selectedIds.includes(member.id)
              return <button className={selected ? 'selected' : ''} type="button" role="option" aria-selected={selected} key={member.id} onClick={() => toggleMember(member.id)}><Avatar user={member} size={29} /><span><strong>{member.name}</strong><small>{member.email}</small></span>{selected && <Icon name="check" size={18} />}</button>
            })}
            {!filteredMembers.length && <p>Không tìm thấy thành viên phù hợp.</p>}
          </div>
        </div>}
      </div>
      {selectedMembers.length > 0 && <div className="assignee-picker__selected">{selectedMembers.map((member) => <span className="assignee-chip" key={member.id}><Avatar user={member} size={25} /><span>{member.name}</span><button type="button" onClick={() => toggleMember(member.id)} aria-label={`Bỏ chọn ${member.name}`}><Icon name="close" size={13} /></button></span>)}</div>}
    </fieldset>
  )
}

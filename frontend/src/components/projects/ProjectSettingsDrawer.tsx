import { useRef, useState } from 'react'
import { mockMemberRoles, mockRolePermissions } from '../../data/mockData'
import type { ProjectSummary, UserSummary } from '../../types/task'
import type { ProjectDocument, ProjectRole, RolePermission } from '../../types/project'
import { Avatar } from '../ui/Avatar'
import { Icon } from '../ui/Icon'

type SettingsTab = 'members' | 'roles' | 'documents'

const tabs: { id: SettingsTab; label: string; icon: string }[] = [
  { id: 'members', label: 'Thành viên', icon: 'users' },
  { id: 'roles', label: 'Vai trò & phân quyền', icon: 'shield' },
  { id: 'documents', label: 'Tài liệu', icon: 'file' },
]

const roleLabels: Record<ProjectRole, string> = {
  owner: 'Chủ dự án', manager: 'Quản lý', member: 'Thành viên', viewer: 'Chỉ xem',
}
const projectRoles: ProjectRole[] = ['owner', 'manager', 'member', 'viewer']
const permissionIcons: Record<string, string> = {
  'project.manage': 'settings',
  'member.manage': 'users',
  'task.manage': 'check',
  'document.manage': 'file',
  'project.view': 'eye',
}

interface ProjectSettingsDrawerProps {
  project: ProjectSummary
  documents: ProjectDocument[]
  onInvite: (member: UserSummary) => void
  onUpload: (file: File) => Promise<void>
  onDownload?: (document: ProjectDocument) => Promise<void>
  onClose: () => void
}

export function ProjectSettingsDrawer({ project, documents, onInvite, onUpload, onDownload, onClose }: ProjectSettingsDrawerProps) {
  const [activeTab, setActiveTab] = useState<SettingsTab>('members')
  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [memberRoles, setMemberRoles] = useState<Record<string, ProjectRole>>(() => {
    try { return JSON.parse(localStorage.getItem(`taskflow-member-roles-${project.id}`) ?? 'null') ?? mockMemberRoles } catch { return mockMemberRoles }
  })
  const [rolePermissions, setRolePermissions] = useState<RolePermission[]>(() => {
    try { return JSON.parse(localStorage.getItem(`taskflow-role-permissions-${project.id}`) ?? 'null') ?? mockRolePermissions } catch { return mockRolePermissions }
  })
  const [permissionsDirty, setPermissionsDirty] = useState(false)
  const [permissionsSaved, setPermissionsSaved] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [documentError, setDocumentError] = useState('')
  
  const invite = (event: React.FormEvent) => {
    event.preventDefault()
    const email = inviteEmail.trim().toLowerCase()
    if (!email || project.members.some((member) => member.email === email)) return
    const name = email.split('@')[0].split(/[._-]/).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' ')
    const id = `member-${Date.now()}`
    onInvite({ id, name, email, initials: name.split(' ').map((part) => part[0]).join('').slice(0, 2), color: '#64748b' })
    setMemberRoles((current) => ({ ...current, [id]: 'member' }))
    setInviteEmail('')
    setInviteOpen(false)
  }

  const upload = async (file?: File) => {
    if (!file) return
    setDocumentError('')
    setUploading(true)
    try {
      await onUpload(file)
    } catch (reason) {
      setDocumentError(reason instanceof Error ? reason.message : 'Không thể tải tệp lên.')
    } finally {
      setUploading(false)
      if (fileInput.current) fileInput.current.value = '' // cho phép chọn lại cùng một tệp
    }
  }
  const download = async (document: ProjectDocument) => {
    setDocumentError('')
    try { await onDownload?.(document) } catch (reason) { setDocumentError(reason instanceof Error ? reason.message : 'Không thể tải tệp xuống.') }
  }

  const changeMemberRole = (memberId: string, role: ProjectRole) => {
    setMemberRoles((current) => {
      const next = { ...current, [memberId]: role }
      localStorage.setItem(`taskflow-member-roles-${project.id}`, JSON.stringify(next))
      return next
    })
  }

  const togglePermission = (permissionKey: string, role: ProjectRole) => {
    setRolePermissions((current) => current.map((permission) => permission.key === permissionKey
      ? { ...permission, roles: permission.roles.includes(role) ? permission.roles.filter((item) => item !== role) : [...permission.roles, role] }
      : permission))
    setPermissionsDirty(true)
    setPermissionsSaved(false)
  }

  const savePermissions = () => {
    localStorage.setItem(`taskflow-role-permissions-${project.id}`, JSON.stringify(rolePermissions))
    setPermissionsDirty(false)
    setPermissionsSaved(true)
  }

  const resetPermissions = () => {
    setRolePermissions(mockRolePermissions.map((permission) => ({ ...permission, roles: [...permission.roles] })))
    setPermissionsDirty(true)
    setPermissionsSaved(false)
  }

  return (
    <>
      <button className="drawer-scrim" onClick={onClose} aria-label="Đóng cấu hình dự án" />
      <aside className="project-settings" aria-label="Cấu hình dự án">
        <header className="settings-header">
          <div><span className="settings-icon"><Icon name="settings" size={18} /></span><div><strong>Cấu hình dự án</strong><small>{project.name}</small></div></div>
          <button className="icon-button" onClick={onClose} aria-label="Đóng"><Icon name="close" /></button>
        </header>

        <nav className="settings-tabs">
          {tabs.map((tab) => <button className={activeTab === tab.id ? 'active' : ''} onClick={() => setActiveTab(tab.id)} key={tab.id}><Icon name={tab.icon} size={16} />{tab.label}</button>)}
        </nav>

        <div className="settings-content">
          {activeTab === 'members' && (
            <section>
              <div className="settings-section-title"><div><h2>Danh sách thành viên</h2><p>{project.members.length} người đang tham gia dự án</p></div><button className="primary-button" onClick={() => setInviteOpen((value) => !value)}><Icon name="plus" size={15} />Mời thành viên</button></div>
              {inviteOpen && <form className="invite-form" onSubmit={invite}><Icon name="mail" size={16} /><input type="email" autoFocus required value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} placeholder="email@company.com" /><button type="button" onClick={() => setInviteOpen(false)}>Hủy</button><button className="primary-button" type="submit">Gửi lời mời</button></form>}
              <div className="member-list">
                {project.members.map((member) => {
                  const role = memberRoles[member.id] ?? 'member'
                  return <div className="member-row" key={member.id}><Avatar user={member} size={36} /><div><strong>{member.name}</strong><span>{member.email}</span></div><select className={`role-badge role-badge--${role}`} value={role} onChange={(event) => changeMemberRole(member.id, event.target.value as ProjectRole)} aria-label={`Vai trò của ${member.name}`}>{(Object.keys(roleLabels) as ProjectRole[]).map((value) => <option value={value} key={value}>{roleLabels[value]}</option>)}</select></div>
                })}
              </div>
            </section>
          )}

          {activeTab === 'roles' && (
            <section>
              <div className="settings-section-title"><div><h2>Vai trò và phân quyền</h2><p>Nhấn vào từng ô để bật hoặc tắt quyền của vai trò</p></div><div className="permission-actions"><button className="secondary-button" onClick={resetPermissions}>Khôi phục</button><button className="primary-button" disabled={!permissionsDirty} onClick={savePermissions}>Lưu thay đổi</button></div></div>
              {permissionsSaved && <div className="permission-saved"><Icon name="check" size={15} />Đã lưu cấu hình phân quyền của dự án.</div>}
              <div className="permission-table">
                <div className="permission-head"><span>Quyền truy cập</span>{projectRoles.map((role) => <span className={`permission-role permission-role--${role}`} key={role}>{roleLabels[role]}</span>)}</div>
                {rolePermissions.map((permission) => <div className="permission-row" key={permission.key}><div className="permission-name"><span className="permission-name__icon"><Icon name={permissionIcons[permission.key] ?? 'shield'} size={16} /></span><span><strong>{permission.label}</strong><small>{permission.description}</small></span></div>{projectRoles.map((role) => { const allowed = permission.roles.includes(role); return <button className={`permission-toggle permission-toggle--${role} ${allowed ? 'allowed' : ''}`} data-role-label={roleLabels[role]} aria-pressed={allowed} aria-label={`${allowed ? 'Tắt' : 'Bật'} quyền ${permission.label} cho ${roleLabels[role]}`} onClick={() => togglePermission(permission.key, role)} key={role}><span>{allowed ? '✓' : ''}</span></button> })}</div>)}
              </div>
            </section>
          )}

          {activeTab === 'documents' && (
            <section>
              <div className="settings-section-title"><div><h2>Tài liệu dự án</h2><p>Tài liệu dùng chung cho các thành viên</p></div><button className="primary-button" disabled={uploading} onClick={() => fileInput.current?.click()}><Icon name="upload" size={15} />{uploading ? 'Đang tải lên...' : 'Tải lên'}</button><input ref={fileInput} type="file" hidden onChange={(event) => upload(event.target.files?.[0])} /></div>
              {documentError && <p className="auth-error" role="alert">{documentError}</p>}
              <div className="document-list">
               {documents.map((document) => <div className="document-row" key={document.id}><span className="document-icon"><Icon name="file" size={18} /></span><div><strong>{document.name}</strong><span>{document.type} · {document.size} · {document.updatedBy}{onDownload && <> · <button type="button" onClick={() => void download(document)}>Tải xuống</button></>}</span></div><time>{new Intl.DateTimeFormat('vi-VN').format(new Date(document.updatedAt))}</time></div>)}
              </div>
            </section>
          )}
        </div>
      </aside>
    </>
  )
}

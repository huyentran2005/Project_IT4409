import { useEffect, useRef, useState } from 'react'
import type { ProjectSummary, UserSummary } from '../../types/task'
import type { ProjectDocument, ProjectInvitation, ProjectMember, ProjectRole, RolePermission } from '../../types/project'
import { Avatar } from '../ui/Avatar'
import { Icon } from '../ui/Icon'
import { ApiError } from '../../services/apiClient'
import { projectApi } from '../../services/projectApi'

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

const clonePermissions = (permissions: RolePermission[]) => permissions.map((permission) => ({
  ...permission,
  roles: [...permission.roles],
}))

const memberToUserSummary = (member: ProjectMember): UserSummary => ({
  id: member.id,
  name: member.name,
  email: member.email,
  avatarUrl: member.avatarUrl ?? undefined,
  initials: member.initials,
  color: member.color,
})

interface ProjectSettingsDrawerProps {
  project: ProjectSummary
  documents: ProjectDocument[]
  onMembersChange: (members: UserSummary[]) => void
  onUpload: (file: File) => Promise<void>
  onDownload?: (document: ProjectDocument) => Promise<void>
  onClose: () => void
}

export function ProjectSettingsDrawer({ project, documents, onMembersChange, onUpload, onDownload, onClose }: ProjectSettingsDrawerProps) {
  const [activeTab, setActiveTab] = useState<SettingsTab>('members')
  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<ProjectRole>('member')
  const [inviteSending, setInviteSending] = useState(false)
  const [inviteResult, setInviteResult] = useState<{ kind: 'success' | 'error'; message: string } | null>(null)
  const [members, setMembers] = useState<ProjectMember[]>([])
  const [invitations, setInvitations] = useState<ProjectInvitation[]>([])
  const [rolePermissions, setRolePermissions] = useState<RolePermission[]>([])
  const [savedRolePermissions, setSavedRolePermissions] = useState<RolePermission[]>([])
  const [loadingSettings, setLoadingSettings] = useState(true)
  const [permissionsDirty, setPermissionsDirty] = useState(false)
  const [permissionsSaved, setPermissionsSaved] = useState(false)
  const [permissionError, setPermissionError] = useState<string | null>(null)
  const [savingPermissions, setSavingPermissions] = useState(false)
  const [changingMemberId, setChangingMemberId] = useState<string | null>(null)
  const [removingMemberId, setRemovingMemberId] = useState<string | null>(null)
  const [cancellingInvitationId, setCancellingInvitationId] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [documentError, setDocumentError] = useState('')
  const currentUserId = (() => {
    try { return JSON.parse(localStorage.getItem('taskflow-current-user') ?? 'null')?.id as string | undefined } catch { return undefined }
  })()
  const currentRole = currentUserId ? members.find((member) => member.id === currentUserId)?.role.code : undefined
  const hasPermission = (permissionKey: string) => {
    if (!currentRole) return false
    return rolePermissions.some((permission) => permission.key === permissionKey && permission.roles.includes(currentRole))
  }
  const canManageMembers = hasPermission('member.manage')
  const canManageProject = hasPermission('project.manage')
  const canManageDocuments = hasPermission('document.manage')

  useEffect(() => {
    let active = true

    Promise.all([
      projectApi.getMembers(project.id),
      projectApi.getRolePermissions(project.id),
    ])
      .then(([members, permissions]) => {
        if (!active) return
        setMembers(members)
        onMembersChange(members.map(memberToUserSummary))
        setRolePermissions(clonePermissions(permissions))
        setSavedRolePermissions(clonePermissions(permissions))
        setPermissionError(null)
      })
      .catch((error) => {
        if (!active) return
        setPermissionError(error instanceof ApiError ? error.message : 'Không thể tải dữ liệu phân quyền')
      })
      .finally(() => {
        if (active) setLoadingSettings(false)
      })

    return () => { active = false }
  }, [project.id, onMembersChange])

  useEffect(() => {
    if (!canManageMembers) return
    let active = true
    projectApi.getInvitations(project.id)
      .then((items) => {
        if (active) setInvitations(items)
      })
      .catch((error) => {
        if (active) setPermissionError(error instanceof ApiError ? error.message : 'Không thể tải danh sách lời mời')
      })
    return () => { active = false }
  }, [canManageMembers, project.id])

  const invite = async (event: React.FormEvent) => {
    event.preventDefault()
    const email = inviteEmail.trim().toLowerCase()
    if (!email || members.some((member) => member.email.toLowerCase() === email)) return
    setInviteSending(true)
    setInviteResult(null)
    try {
      const invitation = await projectApi.inviteMember(project.id, email, inviteRole)
      setInvitations((current) => [invitation, ...current.filter((item) => item.id !== invitation.id)])
      setInviteEmail('')
      setInviteResult({ kind: 'success', message: `Đã gửi lời mời tới ${email}` })
    } catch (error) {
      setInviteResult({ kind: 'error', message: error instanceof ApiError ? error.message : 'Không thể gửi lời mời' })
    } finally {
      setInviteSending(false)
    }
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

  const changeMemberRole = async (memberId: string, role: ProjectRole) => {
    if (!canManageMembers) return
    const previousRole = members.find((member) => member.id === memberId)?.role.code
    if (!previousRole) return
    setChangingMemberId(memberId)
    setPermissionError(null)
    setMembers((current) => current.map((member) => member.id === memberId
      ? { ...member, role: { ...member.role, code: role, name: roleLabels[role] } }
      : member))
    try {
      await projectApi.updateMemberRole(project.id, memberId, role)
    } catch (error) {
      setMembers((current) => current.map((member) => member.id === memberId
        ? { ...member, role: { ...member.role, code: previousRole, name: roleLabels[previousRole] } }
        : member))
      setPermissionError(error instanceof ApiError ? error.message : 'Không thể thay đổi vai trò')
    } finally {
      setChangingMemberId(null)
    }
  }

  const removeMember = async (memberId: string) => {
    if (!canManageMembers) return
    setRemovingMemberId(memberId)
    setPermissionError(null)
    try {
      await projectApi.removeMember(project.id, memberId)
      const nextMembers = members.filter((member) => member.id !== memberId)
      setMembers(nextMembers)
      onMembersChange(nextMembers.map(memberToUserSummary))
    } catch (error) {
      setPermissionError(error instanceof ApiError ? error.message : 'Không thể xóa thành viên')
    } finally {
      setRemovingMemberId(null)
    }
  }

  const cancelInvitation = async (invitationId: string) => {
    if (!canManageMembers) return
    setCancellingInvitationId(invitationId)
    setPermissionError(null)
    try {
      await projectApi.cancelInvitation(project.id, invitationId)
      setInvitations((current) => current.filter((item) => item.id !== invitationId))
    } catch (error) {
      setPermissionError(error instanceof ApiError ? error.message : 'Không thể hủy lời mời')
    } finally {
      setCancellingInvitationId(null)
    }
  }

  const togglePermission = (permissionKey: string, role: ProjectRole) => {
    if (!canManageProject || role === 'owner' || permissionKey === 'project.view') return
    setRolePermissions((current) => current.map((permission) => permission.key === permissionKey
      ? { ...permission, roles: permission.roles.includes(role) ? permission.roles.filter((item) => item !== role) : [...permission.roles, role] }
      : permission))
    setPermissionsDirty(true)
    setPermissionsSaved(false)
  }

  const savePermissions = async () => {
    if (!canManageProject) return
    setSavingPermissions(true)
    setPermissionError(null)
    try {
      const saved = await projectApi.updateRolePermissions(project.id, rolePermissions)
      setRolePermissions(clonePermissions(saved))
      setSavedRolePermissions(clonePermissions(saved))
      setPermissionsDirty(false)
      setPermissionsSaved(true)
    } catch (error) {
      setPermissionError(error instanceof ApiError ? error.message : 'Không thể lưu cấu hình phân quyền')
    } finally {
      setSavingPermissions(false)
    }
  }

  const resetPermissions = () => {
    if (!canManageProject) return
    setRolePermissions(clonePermissions(savedRolePermissions))
    setPermissionsDirty(false)
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
              <div className="settings-section-title"><div><h2>Danh sách thành viên</h2><p>{members.length} người đang tham gia dự án</p></div><button className="primary-button" disabled={!canManageMembers} title={canManageMembers ? 'Mời thành viên' : 'Bạn không có quyền quản lý thành viên'} onClick={() => { setInviteResult(null); setInviteOpen(true) }}><Icon name="plus" size={15} />Mời thành viên</button></div>
              {permissionError && <div className="invitation-result invitation-result--error">{permissionError}</div>}
              <div className="member-list">
                {loadingSettings && <div className="settings-empty">Đang tải thành viên...</div>}
                {!loadingSettings && members.length === 0 && <div className="settings-empty">Chưa có thành viên nào.</div>}
                {members.map((member) => {
                  const role = member.role.code
                  const locked = !canManageMembers || changingMemberId === member.id || removingMemberId === member.id || role === 'owner' || member.id === currentUserId
                  return <div className="member-row" key={member.id}><Avatar user={memberToUserSummary(member)} size={36} /><div><strong>{member.name}</strong><span>{member.email}</span></div><select className={`role-badge role-badge--${role}`} value={role} disabled={locked} onChange={(event) => void changeMemberRole(member.id, event.target.value as ProjectRole)} aria-label={`Vai trò của ${member.name}`}>{(Object.keys(roleLabels) as ProjectRole[]).map((value) => <option value={value} disabled={value === 'owner' || (currentRole !== 'owner' && value === 'manager')} key={value}>{roleLabels[value]}</option>)}</select><button className="member-remove-button" disabled={locked} title={locked ? 'Không thể xóa thành viên này' : `Xóa ${member.name} khỏi dự án`} onClick={() => void removeMember(member.id)} aria-label={`Xóa ${member.name} khỏi dự án`}><Icon name="trash" size={15} /></button></div>
                })}
              </div>
              {canManageMembers && (
                <div className="pending-invitations">
                  <div className="pending-invitations__title"><div><h3>Lời mời đang chờ</h3><p>{invitations.filter((item) => item.status === 'pending').length} lời mời chưa được chấp nhận</p></div></div>
                  <div className="invitation-list">
                    {invitations.filter((item) => item.status === 'pending').length === 0 && <div className="settings-empty">Không có lời mời đang chờ.</div>}
                    {invitations.filter((item) => item.status === 'pending').map((invitation) => <div className="pending-invitation-row" key={invitation.id}><span className="pending-invitation-row__icon"><Icon name="mail" size={17} /></span><div><strong>{invitation.email}</strong><span>{roleLabels[invitation.roleCode]} · hết hạn {new Intl.DateTimeFormat('vi-VN').format(new Date(invitation.expiresAt))}</span></div><button disabled={cancellingInvitationId === invitation.id} onClick={() => void cancelInvitation(invitation.id)}>{cancellingInvitationId === invitation.id ? 'Đang hủy...' : 'Hủy lời mời'}</button></div>)}
                  </div>
                </div>
              )}
            </section>
          )}

          {activeTab === 'roles' && (
            <section>
              <div className="settings-section-title"><div><h2>Vai trò và phân quyền</h2><p>{canManageProject ? 'Nhấn vào từng ô để bật hoặc tắt quyền của vai trò' : 'Bạn chỉ có quyền xem cấu hình phân quyền'}</p></div><div className="permission-actions"><button className="secondary-button" disabled={!canManageProject || !permissionsDirty || savingPermissions} title={canManageProject ? 'Hoàn tác các thay đổi chưa lưu' : 'Bạn không có quyền quản lý dự án'} onClick={resetPermissions}>Hoàn tác</button><button className="primary-button" disabled={!canManageProject || !permissionsDirty || savingPermissions} title={canManageProject ? 'Lưu cấu hình phân quyền' : 'Bạn không có quyền quản lý dự án'} onClick={() => void savePermissions()}>{savingPermissions ? 'Đang lưu...' : 'Lưu thay đổi'}</button></div></div>
              {permissionsSaved && <div className="permission-saved"><Icon name="check" size={15} />Đã lưu cấu hình phân quyền của dự án.</div>}
              {permissionError && <div className="invitation-result invitation-result--error">{permissionError}</div>}
              <div className="permission-table">
                <div className="permission-head"><span>Quyền truy cập</span>{projectRoles.map((role) => <span className={`permission-role permission-role--${role}`} key={role}>{roleLabels[role]}</span>)}</div>
                {loadingSettings && <div className="settings-empty">Đang tải cấu hình phân quyền...</div>}
                {rolePermissions.map((permission) => <div className="permission-row" key={permission.key}><div className="permission-name"><span className="permission-name__icon"><Icon name={permissionIcons[permission.key] ?? 'shield'} size={16} /></span><span><strong>{permission.label}</strong><small>{permission.description}</small></span></div>{projectRoles.map((role) => { const allowed = permission.roles.includes(role); const locked = !canManageProject || role === 'owner' || permission.key === 'project.view'; return <button className={`permission-toggle permission-toggle--${role} ${allowed ? 'allowed' : ''}`} disabled={locked} data-role-label={roleLabels[role]} aria-pressed={allowed} aria-label={`${allowed ? 'Tắt' : 'Bật'} quyền ${permission.label} cho ${roleLabels[role]}`} onClick={() => togglePermission(permission.key, role)} key={role}><span>{allowed ? '✓' : ''}</span></button> })}</div>)}
              </div>
            </section>
          )}

          {activeTab === 'documents' && (
            <section>
              <div className="settings-section-title"><div><h2>Tài liệu dự án</h2><p>Tài liệu dùng chung cho các thành viên</p></div><button className="primary-button" disabled={!canManageDocuments || uploading} title={canManageDocuments ? 'Tải tài liệu lên' : 'Bạn không có quyền quản lý tài liệu'} onClick={() => fileInput.current?.click()}><Icon name="upload" size={15} />{uploading ? 'Đang tải lên...' : 'Tải lên'}</button><input ref={fileInput} type="file" hidden onChange={(event) => upload(event.target.files?.[0])} /></div>
              {documentError && <p className="auth-error" role="alert">{documentError}</p>}
              <div className="document-list">
               {documents.map((document) => <div className="document-row" key={document.id}><span className="document-icon"><Icon name="file" size={18} /></span><div><strong>{document.name}</strong><span>{document.type} · {document.size} · {document.updatedBy}{onDownload && <> · <button type="button" onClick={() => void download(document)}>Tải xuống</button></>}</span></div><time>{new Intl.DateTimeFormat('vi-VN').format(new Date(document.updatedAt))}</time></div>)}
              </div>
            </section>
          )}
        </div>
      </aside>

      {inviteOpen && (
        <div className="modal-layer" role="dialog" aria-modal="true" aria-label="Mời thành viên">
          <button className="modal-scrim" disabled={inviteSending} onClick={() => setInviteOpen(false)} aria-label="Đóng" />
          <form className="create-modal invite-member-modal" onSubmit={(event) => void invite(event)}>
            <div className="create-modal__header">
              <div><span>{project.key}</span><h2>Mời thành viên</h2></div>
              <button type="button" className="icon-button" disabled={inviteSending} onClick={() => setInviteOpen(false)} aria-label="Đóng"><Icon name="close" /></button>
            </div>

            {inviteResult?.kind === 'success' ? (
              <div className="invite-member-success">
                <span><Icon name="check" size={22} /></span>
                <strong>Đã gửi lời mời</strong>
                <p>{inviteResult.message}. Người nhận cần đăng nhập đúng email để chấp nhận.</p>
              </div>
            ) : (
              <>
                <p className="invite-member-modal__intro">Gửi lời mời tham gia <strong>{project.name}</strong> qua email.</p>
                <label>Email người nhận<input autoFocus required type="email" value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} placeholder="email@company.com" /></label>
                <label className="invite-member-role">Vai trò<select value={inviteRole} onChange={(event) => setInviteRole(event.target.value as ProjectRole)}>{currentRole === 'owner' && <option value="manager">Quản lý</option>}<option value="member">Thành viên</option><option value="viewer">Chỉ xem</option></select></label>
                {inviteResult?.kind === 'error' && <div className="invitation-result invitation-result--error">{inviteResult.message}</div>}
              </>
            )}

            <div className="create-modal__actions">
              {inviteResult?.kind === 'success' ? (
                <button className="primary-button" type="button" onClick={() => setInviteOpen(false)}>Đóng</button>
              ) : (
                <><button type="button" className="secondary-button" disabled={inviteSending} onClick={() => setInviteOpen(false)}>Hủy</button><button className="primary-button" disabled={inviteSending} type="submit"><Icon name="mail" size={16} />{inviteSending ? 'Đang gửi...' : 'Gửi lời mời'}</button></>
              )}
            </div>
          </form>
        </div>
      )}
    </>
  )
}

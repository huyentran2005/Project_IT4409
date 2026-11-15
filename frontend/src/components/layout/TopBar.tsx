import { useState } from 'react'
import { Avatar } from '../ui/Avatar'
import { Icon } from '../ui/Icon'
import { getStoredUser } from '../../utils/session'
import { NotificationMenu } from './NotificationMenu'
import type { AppNotification } from '../../services/notificationApi'

interface TopBarProps {
  projectName: string
  query: string
  onQueryChange: (value: string) => void
  onCreate: () => void
  onMenu: () => void
  onToggleTheme: () => void
  onProfile: () => void
  onLogout: () => void
  onOpenNotification: (notification: AppNotification) => Promise<void>
}

export function TopBar({ projectName, query, onQueryChange, onCreate, onMenu, onToggleTheme, onProfile, onLogout, onOpenNotification }: TopBarProps) {
  const [accountOpen, setAccountOpen] = useState(false)
  const displayUser = getStoredUser()
  return (
    <header className="topbar">
      <button className="icon-button menu-button" onClick={onMenu} aria-label="Mở menu"><Icon name="list" /></button>
      <div className="topbar__crumb"><span>Dự án</span><Icon name="chevron" size={13} /><strong>{projectName}</strong></div>
      <label className="global-search">
        <Icon name="search" size={18} />
        <input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="Tìm kiếm công việc..." />
        <kbd>⌘ K</kbd>
      </label>
      <div className="topbar__actions">
        <button className="icon-button" onClick={onToggleTheme} aria-label="Đổi giao diện"><Icon name="sun" /></button>
        <NotificationMenu key={displayUser.id} onOpenTask={onOpenNotification} />
        <button className="create-button" onClick={onCreate}><Icon name="plus" size={17} />Tạo công việc</button>
        <div className="account-menu"><button className="account-trigger" onClick={() => setAccountOpen((value) => !value)}><Avatar user={displayUser} size={34} /><span>{displayUser.name}</span><Icon name="chevron" size={14} /></button>{accountOpen && <div className="account-popover">
          <header><Avatar user={displayUser} size={45} /><div><strong>{displayUser.name}</strong><small>{displayUser.email}</small><i>THÀNH VIÊN</i></div></header>
          <nav><button onClick={() => { setAccountOpen(false); onProfile() }}><Icon name="user" size={18} />Hồ sơ cá nhân<Icon name="chevron" size={14} /></button><button className="account-logout" onClick={onLogout}><Icon name="logout" size={18} />Đăng xuất</button></nav>
        </div>}</div>
      </div>
    </header>
  )
}

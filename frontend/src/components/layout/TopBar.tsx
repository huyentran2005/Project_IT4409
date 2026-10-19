import { useState } from 'react'
import { currentUser } from '../../data/mockData'
import { mockNotifications } from '../../data/mockData'
import { Avatar } from '../ui/Avatar'
import { Icon } from '../ui/Icon'

interface TopBarProps {
  projectName: string
  query: string
  onQueryChange: (value: string) => void
  onCreate: () => void
  onMenu: () => void
  onToggleTheme: () => void
  onProfile: () => void
  onLogout: () => void
}

export function TopBar({ projectName, query, onQueryChange, onCreate, onMenu, onToggleTheme, onProfile, onLogout }: TopBarProps) {
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)
  const displayUser = (() => {
    try { return JSON.parse(localStorage.getItem('taskflow-current-user') ?? 'null') ?? currentUser } catch { return currentUser }
  })()
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
        <div className="notification-menu"><button className="icon-button notification-button" onClick={() => setNotificationsOpen((value) => !value)} aria-label="Thông báo"><Icon name="bell" /><span /></button>{notificationsOpen && <div className="notification-popover"><header><strong>Thông báo</strong><button onClick={() => setNotificationsOpen(false)}><Icon name="close" size={14} /></button></header>{mockNotifications.map((notification) => <button className={notification.unread ? 'unread' : ''} onClick={() => setNotificationsOpen(false)} key={notification.id}><i /><span><strong>{notification.title}</strong><small>{notification.time}</small></span></button>)}</div>}</div>
        <button className="create-button" onClick={onCreate}><Icon name="plus" size={17} />Tạo công việc</button>
        <div className="account-menu"><button className="account-trigger" onClick={() => setAccountOpen((value) => !value)}><Avatar user={displayUser} size={34} /><span>{displayUser.name}</span><Icon name="chevron" size={14} /></button>{accountOpen && <div className="account-popover">
          <header><Avatar user={displayUser} size={45} /><div><strong>{displayUser.name}</strong><small>{displayUser.email}</small><i>THÀNH VIÊN</i></div></header>
          <nav><button onClick={() => { setAccountOpen(false); onProfile() }}><Icon name="user" size={18} />Hồ sơ cá nhân<Icon name="chevron" size={14} /></button><button className="account-logout" onClick={onLogout}><Icon name="logout" size={18} />Đăng xuất</button></nav>
        </div>}</div>
      </div>
    </header>
  )
}

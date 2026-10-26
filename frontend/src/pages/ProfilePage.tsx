import { useState } from 'react'
import { Avatar } from '../components/ui/Avatar'
import { Icon } from '../components/ui/Icon'
import { currentUser } from '../data/mockData'
import { accountApi } from '../services/accountApi'

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false'

type ProfileTab = 'account' | 'security'

export function ProfilePage() {
  const savedUser = (() => {
    try { return JSON.parse(localStorage.getItem('taskflow-current-user') ?? 'null') ?? currentUser } catch { return currentUser }
  })()
  const [tab, setTab] = useState<ProfileTab>('account')
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(savedUser.name)
  const [email, setEmail] = useState(savedUser.email)
  const [phone, setPhone] = useState(savedUser.phone ?? '0357 025 570')
  const [message, setMessage] = useState('')
  const [showPasswords, setShowPasswords] = useState(false)
  const [savingPassword, setSavingPassword] = useState(false)

  const saveProfile = (event: React.FormEvent) => {
    event.preventDefault()
    localStorage.setItem('taskflow-current-user', JSON.stringify({ ...savedUser, name, email, phone }))
    setEditing(false)
    setMessage('Đã cập nhật thông tin tài khoản.')
  }

  const changePassword = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const formElement = event.currentTarget
    const form = new FormData(formElement)
    const currentPassword = String(form.get('currentPassword') ?? '')
    const password = String(form.get('newPassword') ?? '')
    if (password !== String(form.get('confirmPassword') ?? '')) {
      setMessage('Mật khẩu nhập lại chưa khớp.')
      return
    }
    if (!USE_MOCKS) {
      setSavingPassword(true)
      try {
        await accountApi.changePassword({
          currentPassword: currentPassword || undefined,
          newPassword: password,
          refreshToken: localStorage.getItem('taskflow-refresh-token') ?? undefined,
        })
      } catch (error) {
        setMessage(error instanceof Error ? error.message : 'Không thể đổi mật khẩu. Vui lòng thử lại.')
        return
      } finally {
        setSavingPassword(false)
      }
    }
    formElement.reset()
    setMessage('Đã đổi mật khẩu thành công.')
  }

  return <main className="profile-page">
    <header className="profile-page-heading"><h1>Hồ sơ</h1><p>Thông tin tài khoản và thiết lập bảo mật của bạn.</p></header>
    <nav className="profile-tabs" aria-label="Hồ sơ cá nhân"><button className={tab === 'account' ? 'active' : ''} onClick={() => { setTab('account'); setMessage('') }}><Icon name="user" />Tài khoản</button><button className={tab === 'security' ? 'active' : ''} onClick={() => { setTab('security'); setMessage('') }}><Icon name="lock" />Bảo mật</button></nav>
    {message && <div className="profile-message">{message}</div>}
    {tab === 'account' && <section className="profile-page-card">
      <div className="profile-page-summary"><Avatar user={savedUser} size={68} /><div><h2>{name}</h2><p>{email}</p><span className="profile-status">Đang hoạt động</span></div><button className="primary-button" onClick={() => { setEditing((value) => !value); setMessage('') }}><Icon name="user" />{editing ? 'Hủy chỉnh sửa' : 'Chỉnh sửa thông tin'}</button></div>
      <form className="profile-account-form" onSubmit={saveProfile}>
        <label>Họ tên<input disabled={!editing} value={name} onChange={(event) => setName(event.target.value)} /></label>
        <label>Email<input disabled={!editing} type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        <label>Số điện thoại<input disabled={!editing} value={phone} onChange={(event) => setPhone(event.target.value)} /></label>
        <label>Vai trò<input disabled value="Thành viên" /></label>
        <label>Phương thức đăng nhập<input disabled value="Google / mật khẩu" /></label>
        <label>Trạng thái<input disabled value="Tài khoản đang hoạt động" /></label>
        {editing && <button className="primary-button" type="submit">Lưu thay đổi</button>}
      </form>
    </section>}
    {tab === 'security' && <section className="profile-page-card security-card"><header><h2>Đổi mật khẩu</h2><p>Nhập mật khẩu hiện tại, sau đó đặt mật khẩu mới.</p></header><form onSubmit={changePassword}>
      <label>Mật khẩu hiện tại<div><Icon name="lock" /><input name="currentPassword" type={showPasswords ? 'text' : 'password'} placeholder="Nhập mật khẩu hiện tại (bỏ trống nếu chưa có)" autoComplete="current-password" /></div></label>
      <label>Mật khẩu mới<div><Icon name="lock" /><input name="newPassword" required minLength={8} type={showPasswords ? 'text' : 'password'} placeholder="Nhập mật khẩu mới (tối thiểu 8 ký tự)" autoComplete="new-password" /></div></label>
      <label>Nhập lại mật khẩu mới<div><Icon name="lock" /><input name="confirmPassword" required minLength={8} type={showPasswords ? 'text' : 'password'} placeholder="Nhập lại mật khẩu mới" autoComplete="new-password" /></div></label>
      <label className="show-passwords"><input type="checkbox" checked={showPasswords} onChange={(event) => setShowPasswords(event.target.checked)} />Hiện mật khẩu</label>
      <button className="primary-button" type="submit" disabled={savingPassword}>{savingPassword ? 'Đang lưu...' : 'Đổi mật khẩu'}</button>
    </form></section>}
  </main>
}

import { useEffect, useState } from 'react'
import { authApi } from '../services/authApi'
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
  const [phone, setPhone] = useState(savedUser.phone ?? '')
  const [profileReady, setProfileReady] = useState(false)//thêm state profile
  const [saving, setSaving] = useState(false)//thêm state saving
  const [message, setMessage] = useState('')
  const [showPasswords, setShowPasswords] = useState(false)
  const [savingPassword, setSavingPassword] = useState(false)

  // lấy hồ sơ từ backend
  useEffect(() => {
    let ignore = false

    const loadProfile = async () => {
      try {
        const token = localStorage.getItem('taskflow-token')
        if (!token) throw new Error('Bạn cần đăng nhập lại.')

        const user = await authApi.getMe(token)
        if (ignore) return

        localStorage.setItem(
          'taskflow-current-user',
          JSON.stringify(user),
        )

        setName(user.name)
        setEmail(user.email)
        setPhone(user.phone ?? '')
        setProfileReady(true)
      } catch {
        if (!ignore) {
          setMessage('Không tải được hồ sơ. Vui lòng đăng nhập lại.')
        }
      }
    }

    void loadProfile()

    return () => {
      ignore = true
    }
  }, [])
  const saveProfile = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!profileReady || saving) return

    const token = localStorage.getItem('taskflow-token')
    if (!token) {
      setMessage('Bạn cần đăng nhập lại.')
      return
    }

    setSaving(true)
    setMessage('')

    try {
      const user = await authApi.updateMe(token, {
        name: name.trim(),
        phone: phone.trim() || null,
      })

      localStorage.setItem(
        'taskflow-current-user',
        JSON.stringify(user),
      )

      setName(user.name)
      setEmail(user.email)
      setPhone(user.phone ?? '')
      setEditing(false)
      setMessage('Đã cập nhật thông tin tài khoản.')
    } catch {
      setMessage('Không thể lưu hồ sơ. Vui lòng kiểm tra và thử lại.')
    } finally {
      setSaving(false)
    }
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
      <div className="profile-page-summary"><Avatar user={savedUser} size={68} /><div><h2>{name}</h2><p>{email}</p><span className="profile-status">Đang hoạt động</span></div><button className="primary-button" disabled={!profileReady || saving} onClick={() => { setEditing((value) => !value); setMessage('') }}><Icon name="user" />{editing ? 'Hủy chỉnh sửa' : 'Chỉnh sửa thông tin'}</button></div>
      <form className="profile-account-form" onSubmit={saveProfile}>
        <label>Họ tên<input disabled={!editing || saving} value={name} onChange={(event) => setName(event.target.value)} /></label>
        <label>Email<input type="email" value={email} readOnly /></label>
        <label>Số điện thoại<input disabled={!editing || saving} value={phone} onChange={(event) => setPhone(event.target.value)} /></label>
        <label>Vai trò<input disabled value="Thành viên" /></label>
        <label>Phương thức đăng nhập<input disabled value="Google / mật khẩu" /></label>
        <label>Trạng thái<input disabled value="Tài khoản đang hoạt động" /></label>
        {editing && (
          <button
            className="primary-button"
            type="submit"
            disabled={!profileReady || saving}
          >
            {saving ? 'Đang lưu...' : 'Lưu thay đổi'}
          </button>
        )}
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

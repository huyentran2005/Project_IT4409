import { useState } from 'react'
import { Icon } from '../components/ui/Icon'
import type { SsoProvider } from '../services/authApi'

export type AuthMode = 'login' | 'register'

interface AuthPageProps {
  initialMode?: AuthMode
  onAuthenticate: (data: { mode: AuthMode; name?: string; email: string; phone?: string; password: string }) => Promise<void>
  onSso: (provider: SsoProvider) => void
}

function GoogleMark() {
  return <span className="sso-mark" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 24 24"><path fill="#4285F4" d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.9h5.4a4.6 4.6 0 0 1-2 3v2.6h3.3c1.9-1.8 2.9-4.4 2.9-7.5Z"/><path fill="#34A853" d="M12 22c2.7 0 5-.9 6.7-2.3l-3.3-2.6c-.9.6-2.1 1-3.4 1a5.9 5.9 0 0 1-5.5-4.1H3.1v2.7A10 10 0 0 0 12 22Z"/><path fill="#FBBC05" d="M6.5 14a6 6 0 0 1 0-3.9V7.4H3.1a10 10 0 0 0 0 9.3L6.5 14Z"/><path fill="#EA4335" d="M12 6c1.5 0 2.9.5 4 1.6l3-3A10 10 0 0 0 3.1 7.4l3.4 2.7A5.9 5.9 0 0 1 12 6Z"/></svg></span>
}

function GithubMark() {
  return <span className="sso-mark" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .7A11.5 11.5 0 0 0 8.4 23c.6.1.8-.3.8-.6v-2.2c-3.4.7-4.1-1.4-4.1-1.4-.5-1.4-1.3-1.8-1.3-1.8-1.1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.7 1.3 3.4 1 .1-.8.4-1.3.8-1.6-2.7-.3-5.5-1.3-5.5-5.8 0-1.3.5-2.3 1.2-3.1-.1-.3-.5-1.5.1-3.1 0 0 1-.3 3.2 1.2a11 11 0 0 1 5.8-.8c1.9 0 3.9.3 5.8.8 2.2-1.5 3.2-1.2 3.2-1.2.6 1.6.2 2.8.1 3.1.8.8 1.2 1.8 1.2 3.1 0 4.5-2.8 5.5-5.5 5.8.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A11.5 11.5 0 0 0 12 .7Z"/></svg></span>
}

export function AuthPage({ initialMode = 'login', onAuthenticate, onSso }: AuthPageProps) {
  const [mode, setMode] = useState<AuthMode>(initialMode)
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    const form = new FormData(event.currentTarget)
    const password = String(form.get('password') ?? '')
    if (mode === 'register' && password !== String(form.get('confirmPassword') ?? '')) {
      setError('Mật khẩu nhập lại chưa khớp.')
      return
    }
    setSubmitting(true)
    try {
      await onAuthenticate({ mode, name: String(form.get('name') ?? ''), email: String(form.get('email') ?? ''), phone: String(form.get('phone') ?? ''), password })
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể xác thực. Vui lòng thử lại.')
    } finally {
      setSubmitting(false)
    }
  }

  return <main className="auth-page">
    <div className="auth-brand"><span className="brand__mark"><span /><span /><span /></span><strong>TaskFlow</strong></div>
    <section className={`auth-card auth-card--${mode}`}>
      <header><h1>{mode === 'login' ? 'Chào mừng bạn' : 'Tạo tài khoản'}</h1><p>{mode === 'login' ? 'Đăng nhập để tiếp tục quản lý công việc' : 'Đăng ký để bắt đầu quản lý dự án của bạn'}</p></header>
      <form onSubmit={submit}>
        {mode === 'register' && <label>Họ tên<div className="auth-input"><Icon name="user" size={20} /><input name="name" required placeholder="Nguyễn Văn A" autoComplete="name" /></div></label>}
        <label>Email<div className="auth-input"><Icon name="mail" size={20} /><input name="email" required type="email" placeholder="email@example.com" autoComplete="email" /></div></label>
        {mode === 'register' && <label>Số điện thoại <span>(không bắt buộc)</span><div className="auth-input"><Icon name="phone" size={20} /><input name="phone" type="tel" placeholder="0912 345 678" autoComplete="tel" /></div></label>}
        <label>Mật khẩu{mode === 'login' && <button className="forgot-password" type="button" onClick={() => setError('Nhập email và liên hệ quản trị viên để được cấp lại mật khẩu.')}>Quên mật khẩu?</button>}<div className="auth-input"><Icon name="lock" size={20} /><input name="password" required minLength={6} type={showPassword ? 'text' : 'password'} placeholder={mode === 'login' ? 'Nhập mật khẩu' : 'Tạo mật khẩu'} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /><button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}><Icon name="eye" size={19} /></button></div></label>
        {mode === 'register' && <label>Nhập lại mật khẩu<div className="auth-input"><Icon name="lock" size={20} /><input name="confirmPassword" required minLength={6} type={showPassword ? 'text' : 'password'} placeholder="Nhập lại mật khẩu" autoComplete="new-password" /></div></label>}
        {error && <p className="auth-error" role="alert">{error}</p>}
        <button className="auth-submit" disabled={submitting} type="submit">{submitting ? 'Đang xử lý...' : mode === 'login' ? 'Đăng nhập' : 'Đăng ký'}</button>
      </form>
      {mode === 'login' && <div className="login-sso">
        <div className="auth-divider"><span>Hoặc tiếp tục với</span></div>
        <div className="sso-buttons"><button type="button" onClick={() => onSso('google')}><GoogleMark /><span>Google</span></button><button type="button" onClick={() => onSso('github')}><GithubMark /><span>GitHub</span></button></div>
      </div>}
      <footer>{mode === 'login' ? 'Chưa có tài khoản?' : 'Đã có tài khoản?'} <button onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>{mode === 'login' ? 'Đăng ký' : 'Đăng nhập'}</button></footer>
    </section>
  </main>
}

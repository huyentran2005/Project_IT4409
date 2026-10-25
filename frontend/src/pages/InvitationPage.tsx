import { useEffect, useState } from 'react'

import { ApiError } from '../services/apiClient'
import { projectApi } from '../services/projectApi'


interface InvitationPageProps {
  token: string
}


export function InvitationPage({ token }: InvitationPageProps) {
  const [invitation, setInvitation] = useState<Awaited<ReturnType<typeof projectApi.getInvitation>> | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState<'accept' | 'reject' | null>(null)
  const [result, setResult] = useState<{ kind: 'success' | 'error'; message: string } | null>(null)

  useEffect(() => {
    projectApi.getInvitation(token)
      .then((data) => {
        setInvitation(data)
        if (data.status === 'accepted') {
          setResult({ kind: 'success', message: 'Lời mời này đã được chấp nhận.' })
        } else if (data.status === 'expired') {
          setResult({ kind: 'error', message: 'Lời mời này đã hết hạn.' })
        }
      })
      .catch((error) => {
        setResult({
          kind: 'error',
          message: error instanceof ApiError ? error.message : 'Không thể tải thông tin lời mời',
        })
      })
      .finally(() => setLoading(false))
  }, [token])

  const act = async (action: 'accept' | 'reject') => {
    setSubmitting(action)
    setResult(null)
    try {
      const response = action === 'accept'
        ? await projectApi.acceptInvitation(token)
        : await projectApi.rejectInvitation(token)
      setResult({ kind: 'success', message: response.message })
    } catch (error) {
      setResult({
        kind: 'error',
        message: error instanceof ApiError ? error.message : 'Không thể xử lý lời mời',
      })
    } finally {
      setSubmitting(null)
    }
  }

  return (
    <main className="invitation-page">
      <section className="invitation-card">
        <header className="invitation-card__header">
          <span className="invitation-card__brand">TF</span>
          <span>TaskFlow</span>
        </header>

        {loading ? (
          <div className="invitation-loading">Đang tải thông tin lời mời...</div>
        ) : invitation ? (
          <>
            <p className="invitation-card__eyebrow">Lời mời tham gia dự án</p>
            <h1>Bạn được mời cộng tác</h1>
            <p className="invitation-card__intro">
              <strong>{invitation.inviterName}</strong> đã mời bạn tham gia dự án với vai trò <strong>{invitation.roleName}</strong>.
            </p>

            <div className="invitation-project">
              <span className="invitation-project__icon" style={{ background: invitation.projectColor }}>
                {invitation.projectKey.slice(0, 2).toUpperCase()}
              </span>
              <span className="invitation-project__content">
                <small>Dự án</small>
                <strong>{invitation.projectName}</strong>
                <span>{invitation.projectKey} · {invitation.roleName}</span>
              </span>
            </div>

            <dl className="invitation-meta">
              <div><dt>Tài khoản nhận lời mời</dt><dd>{invitation.email}</dd></div>
              <div><dt>Hết hạn</dt><dd>{new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(invitation.expiresAt))}</dd></div>
            </dl>
          </>
        ) : (
          <>
            <p className="invitation-card__eyebrow">Lời mời tham gia dự án</p>
            <h1>Không thể mở lời mời</h1>
          </>
        )}

        {result && <div className={`invitation-result invitation-result--${result.kind}`}>{result.message}</div>}

        {invitation?.status === 'pending' && result?.kind !== 'success' ? (
          <div className="invitation-actions">
            <button className="secondary-button" disabled={submitting !== null} onClick={() => void act('reject')}>
              {submitting === 'reject' ? 'Đang xử lý...' : 'Từ chối'}
            </button>
            <button className="primary-button" disabled={submitting !== null} onClick={() => void act('accept')}>
              {submitting === 'accept' ? 'Đang xử lý...' : 'Chấp nhận'}
            </button>
          </div>
        ) : invitation && result?.kind === 'success' ? (
          <button className="primary-button" onClick={() => window.location.assign('/')}>
            Về trang chính
          </button>
        ) : null}
      </section>
    </main>
  )
}

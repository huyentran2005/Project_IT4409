import { useCallback, useEffect, useRef, useState } from 'react'
import { notificationApi, type AppNotification, type NotificationPage } from '../../services/notificationApi'
import { Icon } from '../ui/Icon'

export function NotificationMenu({ onOpenTask }: { onOpenTask: (notification: AppNotification) => Promise<void> }) {
  const [open, setOpen] = useState(false)
  const [page, setPage] = useState(0)
  const [result, setResult] = useState<{ page: number; data: NotificationPage } | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const requestId = useRef(0)
  const acting = useRef(false)
  const mounted = useRef(false)
  const menu = useRef<HTMLDivElement>(null)
  const current = result?.page === page ? result.data : null
  const unread = result?.data.unreadCount ?? 0

  const load = useCallback(() => {
    if (acting.current) return
    const id = ++requestId.current
    return notificationApi.list(page * 20).then((data) => {
      if (mounted.current && id === requestId.current) {
        setResult({ page, data })
        setError('')
      }
    }).catch(() => {
      if (mounted.current && id === requestId.current) setError('Không tải được thông báo. Vui lòng thử lại.')
    })
  }, [page])

  useEffect(() => {
    mounted.current = true
    void load()
    const refresh = () => { if (!document.hidden) void load() }
    const timer = window.setInterval(refresh, 30000)
    window.addEventListener('focus', refresh)
    return () => {
      mounted.current = false
      requestId.current += 1
      window.clearInterval(timer)
      window.removeEventListener('focus', refresh)
    }
  }, [load])

  useEffect(() => {
    if (!open) return
    const closeOutside = (event: PointerEvent) => {
      if (!menu.current?.contains(event.target as Node)) setOpen(false)
    }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', closeOutside)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  const act = async (notification?: AppNotification) => {
    if (acting.current) return
    acting.current = true
    requestId.current += 1
    setBusy(true)
    setError('')
    setNotice('')
    try {
      if (notification) {
        await notificationApi.read(notification.id)
        if (notification.taskDeleted) setNotice('Công việc này đã bị xóa. Thông báo đã được đánh dấu đã đọc.')
        else if (notification.taskId && notification.projectId) {
          await onOpenTask(notification)
          if (mounted.current) setOpen(false)
        }
      } else await notificationApi.readAll()
    } catch (reason) {
      if (mounted.current) setError(reason instanceof Error ? reason.message : 'Không thể xử lý thông báo.')
    } finally {
      acting.current = false
      if (mounted.current) {
        setBusy(false)
        const id = ++requestId.current
        try {
          const data = await notificationApi.list(page * 20)
          if (mounted.current && id === requestId.current) setResult({ page, data })
        } catch { /* Giữ lỗi thao tác; lần làm mới tiếp theo sẽ thử lại. */ }
      }
    }
  }

  return <div className="notification-menu" ref={menu}>
    <button className="icon-button notification-button" aria-label={unread ? `Thông báo, ${unread} chưa đọc` : 'Thông báo'} aria-expanded={open} aria-controls="notification-panel" onClick={() => {
      setOpen((value) => !value)
      if (!open) { setNotice(''); void load() }
    }}><Icon name="bell" />{unread > 0 && <span className="notification-count">{unread > 99 ? '99+' : unread}</span>}</button>
    {open && <section className="notification-popover notification-panel" id="notification-panel" aria-label="Thông báo">
      <header><strong>Thông báo {unread > 0 && `(${unread} chưa đọc)`}</strong><button aria-label="Đóng thông báo" onClick={() => setOpen(false)}><Icon name="close" size={14} /></button></header>
      <div className="notification-tools"><button disabled={busy} onClick={() => void load()}>Làm mới</button><button disabled={busy || unread === 0} onClick={() => void act()}>Đọc tất cả</button></div>
      {error && <div className="notification-feedback" role="alert">{error}</div>}
      {notice && <div className="notification-feedback" role="status">{notice}</div>}
      {!current && !error && <div className="view-empty" role="status">Đang tải thông báo...</div>}
      {current && <>
        <div className="notification-items" aria-busy={busy}>
          {current.items.map((item) => <button key={item.id} className={`notification-item${item.readAt ? '' : ' unread'}`} disabled={busy} onClick={() => void act(item)}>
            <i aria-hidden="true" /><span><strong>{item.title}</strong><span className="notification-task">{item.taskTitle}</span><small>{item.projectName} · {new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(item.createdAt))}{!item.readAt && ' · Chưa đọc'}</small></span>
          </button>)}
          {!current.items.length && !error && <div className="view-empty">{page ? 'Không còn thông báo ở trang này.' : 'Chưa có thông báo.'}</div>}
        </div>
        {(page > 0 || current.hasMore) && <div className="notification-pagination"><button disabled={busy || page === 0} onClick={() => setPage((value) => value - 1)}>Trước</button><span>Trang {page + 1}</span><button disabled={busy || !current.hasMore} onClick={() => setPage((value) => value + 1)}>Sau</button></div>}
      </>}
    </section>}
  </div>
}

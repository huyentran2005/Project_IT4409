import { useEffect, useRef, useState } from 'react'
import { projectChatApi, type ProjectChatMessage, type ProjectChatSessionSummary } from '../../services/projectChatApi'
import { Icon } from '../ui/Icon'

interface ProjectChatWidgetProps {
  projectId: string
  projectName: string
}

const formatSessionDate = (value: string) => new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
}).format(new Date(value))

export function ProjectChatWidget({ projectId, projectName }: ProjectChatWidgetProps) {
  const [open, setOpen] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [sessions, setSessions] = useState<ProjectChatSessionSummary[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ProjectChatMessage[]>([])
  const [question, setQuestion] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [error, setError] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const selectedSessionIdRef = useRef<string | null>(null)

  useEffect(() => {
    selectedSessionIdRef.current = sessionId
  }, [sessionId])

  useEffect(() => {
    setSessions([])
    setSessionId(null)
    setMessages([])
    setShowHistory(false)
  }, [projectId])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setLoadingHistory(true)
    projectChatApi.listHistory(projectId)
      .then(async (items) => {
        if (cancelled) return
        setSessions(items)
        const preferredId = selectedSessionIdRef.current
        const selectedId = preferredId && items.some((item) => item.id === preferredId)
          ? preferredId
          : items[0]?.id ?? null
        setSessionId(selectedId)
        if (selectedId) {
          const history = await projectChatApi.getHistory(projectId, selectedId)
          if (!cancelled) setMessages(history.messages)
        } else if (!cancelled) {
          setMessages([])
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : 'Không tải được lịch sử chat.')
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false)
      })
    return () => { cancelled = true }
  }, [open, projectId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const selectSession = async (session: ProjectChatSessionSummary) => {
    setLoadingHistory(true)
    setError('')
    try {
      const history = await projectChatApi.getHistory(projectId, session.id)
      setSessionId(session.id)
      setMessages(history.messages)
      setShowHistory(false)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Không mở được cuộc trò chuyện.')
    } finally {
      setLoadingHistory(false)
    }
  }

  const startNewChat = () => {
    setSessionId(null)
    setMessages([])
    setShowHistory(false)
    setError('')
  }

  const resetHistory = async () => {
    setLoadingHistory(true)
    setError('')
    try {
      await projectChatApi.reset(projectId)
      setSessions([])
      setSessionId(null)
      setMessages([])
      setShowHistory(false)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Không xóa được lịch sử chat.')
    } finally {
      setLoadingHistory(false)
    }
  }

  const sendQuestion = async () => {
    const text = question.trim()
    if (!text || sending) return
    setQuestion('')
    setError('')
    setSending(true)
    setMessages((current) => [...current, {
      id: `pending-${Date.now()}`,
      role: 'user',
      content: text,
      sources: [],
      createdAt: new Date().toISOString(),
    }])
    try {
      const result = await projectChatApi.ask(projectId, text, sessionId ?? undefined)
      setSessionId(result.sessionId)
      setMessages((current) => [
        ...current.filter((message) => !message.id.startsWith('pending-')),
        ...result.messages,
      ])
      const history = await projectChatApi.listHistory(projectId)
      setSessions(history)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Chưa gửi được câu hỏi. Vui lòng thử lại.')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="project-chat">
      {open && (
        <section className="project-chat__panel" aria-label={`Chat tài liệu ${projectName}`}>
          <header className="project-chat__header">
            <div className="project-chat__identity">
              <span className="project-chat__avatar">AI</span>
              <span><strong>Trợ lý dự án</strong><small>{projectName}</small></span>
            </div>
            <div className="project-chat__actions">
              <button type="button" title="Lịch sử chat" aria-label="Mở lịch sử chat" onClick={() => setShowHistory((value) => !value)}><Icon name="calendar-clock" size={17} /></button>
              <button type="button" title="Cuộc trò chuyện mới" aria-label="Bắt đầu chat mới" onClick={startNewChat}><Icon name="plus" size={18} /></button>
              <button type="button" className="project-chat__reset" title="Xóa toàn bộ lịch sử của bạn trong dự án này" aria-label="Reset và xóa lịch sử chat" onClick={() => void resetHistory()} disabled={loadingHistory || sending}><Icon name="trash" size={15} /><span>Reset</span></button>
              <button type="button" title="Thu gọn chat" aria-label="Đóng cửa sổ chat" onClick={() => setOpen(false)}><Icon name="close" size={16} /></button>
            </div>
          </header>
          <div className="project-chat__scope">Câu trả lời chỉ dựa trên tài liệu của dự án này</div>

          {showHistory ? (
            <div className="project-chat__history">
              <div className="project-chat__history-title"><strong>Lịch sử trò chuyện</strong><span>{sessions.length}</span></div>
              {sessions.length === 0 && <p className="project-chat__empty">Chưa có cuộc trò chuyện nào.</p>}
              {sessions.map((session) => (
                <button className={`project-chat__history-item ${session.id === sessionId ? 'active' : ''}`} key={session.id} onClick={() => void selectSession(session)}>
                  <span>{session.title}</span><time>{formatSessionDate(session.updatedAt)}</time>
                </button>
              ))}
              <button type="button" className="project-chat__new" onClick={startNewChat}><Icon name="plus" size={15} />Cuộc trò chuyện mới</button>
            </div>
          ) : (
            <div className="project-chat__messages" aria-live="polite">
              {messages.length === 0 && (
                <div className="project-chat__welcome">
                  <span className="project-chat__welcome-mark"><Icon name="comment" size={19} /></span>
                  <strong>Xin chào!</strong>
                  <p>Hãy hỏi về nội dung trong tài liệu của {projectName}.</p>
                  <small>Chỉ thành viên có quyền xem dự án mới dùng được chatbot này.</small>
                </div>
              )}
              {loadingHistory && <p className="project-chat__loading">Đang tải lịch sử...</p>}
              {messages.map((message) => (
                <article className={`project-chat__message project-chat__message--${message.role}`} key={message.id}>
                  <div className="project-chat__bubble">{message.content}</div>
                  {message.role === 'assistant' && message.sources.length > 0 && (
                    <div className="project-chat__sources">
                      <small>Nguồn trong dự án</small>
                      {message.sources.map((source, index) => <span key={`${source.file}-${source.page}-${index}`}>{source.file}{source.page ? ` · trang ${source.page}` : ''}</span>)}
                    </div>
                  )}
                </article>
              ))}
              {sending && <div className="project-chat__typing"><i /><i /><i />Đang tìm trong tài liệu...</div>}
              <div ref={messagesEndRef} />
            </div>
          )}

          {error && <p className="project-chat__error" role="alert">{error}</p>}
          <form className="project-chat__composer" onSubmit={(event) => { event.preventDefault(); void sendQuestion() }}>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void sendQuestion() } }}
              placeholder="Nhập câu hỏi về tài liệu..."
              aria-label="Câu hỏi về tài liệu dự án"
              rows={1}
              disabled={sending}
            />
            <button type="submit" aria-label="Gửi câu hỏi" disabled={!question.trim() || sending}><Icon name="send" size={18} /></button>
          </form>
          <footer className="project-chat__footer">Enter để gửi · Shift + Enter để xuống dòng</footer>
        </section>
      )}
      <button
        type="button"
        className={`project-chat__launcher ${open ? 'is-open' : ''}`}
        aria-label={open ? 'Đóng chatbot dự án' : 'Mở chatbot dự án'}
        onClick={() => setOpen((value) => !value)}
      >
        <Icon name={open ? 'close' : 'comment'} size={23} />
      </button>
    </div>
  )
}

import { apiRequest } from './apiClient'

export interface ProjectChatSource {
  file: string
  page: number | null
  headings?: string[] | null
  score?: number
}

export interface ProjectChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources: ProjectChatSource[]
  createdAt: string
}

export interface ProjectChatSessionSummary {
  id: string
  title: string
  createdAt: string
  updatedAt: string
}

interface AskResponse {
  sessionId: string
  answer: string
  sources: ProjectChatSource[]
  sub_questions: string[]
  messages: ProjectChatMessage[]
}

export const projectChatApi = {
  listHistory(projectId: string) {
    return apiRequest<ProjectChatSessionSummary[]>(`/api/projects/${projectId}/chatbot/history`)
  },
  getHistory(projectId: string, sessionId: string) {
    return apiRequest<{ id: string; title: string; messages: ProjectChatMessage[] }>(
      `/api/projects/${projectId}/chatbot/history/${sessionId}`,
    )
  },
  ask(projectId: string, question: string, sessionId?: string, documentIds: string[] = []) {
    return apiRequest<AskResponse>(`/api/projects/${projectId}/chatbot/ask`, {
      method: 'POST',
      body: JSON.stringify({ question, session_id: sessionId, document_ids: documentIds }),
    })
  },
  reset(projectId: string) {
    return apiRequest<{ deletedSessions: number }>(`/api/projects/${projectId}/chatbot/history`, {
      method: 'DELETE',
    })
  },
}

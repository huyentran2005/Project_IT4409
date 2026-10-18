import type { Meeting, MeetingDraft } from '../types/meeting'
import { apiRequest } from './apiClient'

export const meetingApi = {
  create(projectId: string, payload: MeetingDraft) {
    return apiRequest<Meeting>(`/api/projects/${projectId}/meetings`, {
      method: 'POST', body: JSON.stringify(payload),
    })
  },
  list(projectId: string) {
    return apiRequest<Meeting[]>(`/api/projects/${projectId}/meetings`)
  },
}

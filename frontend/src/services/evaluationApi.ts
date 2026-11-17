import type { MemberEvaluationDetail, ProjectEvaluation } from '../types/evaluation'
import { apiRequest } from './apiClient'

export interface EvaluationRange {
  from?: string
  to?: string
}

const query = ({ from, to }: EvaluationRange) => {
  const params = new URLSearchParams()
  if (from) params.set('from', from)
  if (to) params.set('to', to)
  const text = params.toString()
  return text ? `?${text}` : ''
}

export const evaluationApi = {
  list(projectId: string, range: EvaluationRange = {}) {
    return apiRequest<ProjectEvaluation>(`/api/projects/${projectId}/member-evaluations${query(range)}`)
  },
  detail(projectId: string, userId: string, range: EvaluationRange = {}) {
    return apiRequest<MemberEvaluationDetail>(`/api/projects/${projectId}/member-evaluations/${userId}${query(range)}`)
  },
}

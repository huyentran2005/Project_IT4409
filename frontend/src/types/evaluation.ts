import type { UserSummary } from './task'

export type EvaluationGrade = 'excellent' | 'good' | 'pass' | 'needs_improvement' | 'insufficient'
export type TaskEvaluationResult = 'on_time' | 'late' | 'not_submitted'

export interface EvaluationRules {
  minTasks: number
  returnPenalty: number
  timelinessWeight: number
  qualityWeight: number
  thresholds: Record<string, number>
}

export interface MemberEvaluation {
  user: UserSummary
  evaluatedTasks: number
  submittedTasks: number
  onTimeTasks: number
  lateTasks: number
  returnCount: number
  firstPassRate: number | null
  timelinessScore: number | null
  qualityScore: number | null
  score: number | null
  grade: EvaluationGrade
  gradeLabel: string
}

export interface ProjectEvaluation {
  projectId: string
  dateFrom: string | null
  dateTo: string | null
  canViewAll: boolean
  rules: EvaluationRules
  members: MemberEvaluation[]
}

export interface TaskEvaluationItem {
  id: string
  key: string
  title: string
  deadline: string
  status: string
  statusName: string
  submittedAt: string | null
  completedAt: string | null
  result: TaskEvaluationResult
  returnCount: number
  qualityScore: number | null
}

export interface MemberEvaluationDetail extends MemberEvaluation {
  tasks: TaskEvaluationItem[]
}

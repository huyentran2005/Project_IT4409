import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { projectApi } from '../services/projectApi'
import { taskApi } from '../services/taskApi'
import type { ProjectMember } from '../types/project'
import { getTaskAssignees, type BoardData, type BoardFilter, type CreateProjectInput, type CreateTaskInput, type ProjectSummary, type Task, type TaskComment, type TaskPropertiesUpdate, type TaskStatus, type TimesheetEntry, type UserSummary } from '../types/task'
import { getStoredUser } from '../utils/session'

const emptyBoard: BoardData = {
  project: {
    id: 'p-01',
    key: '',
    name: 'Đang tải...',
    description: '',
    color: '#64748b',
    progress: 0,
    members: [],
  },
  columns: [
    { id: 'backlog', title: 'Cần làm', accent: '#64748b', tasks: [] },
    { id: 'in-progress', title: 'Đang làm', accent: '#2563eb', tasks: [] },
    { id: 'review', title: 'Đang duyệt', accent: '#d97706', tasks: [] },
    { id: 'done', title: 'Hoàn thành', accent: '#0f9f8f', tasks: [] },
  ],
}

function getActiveUser(): UserSummary {
  return getStoredUser()
}

const memberToUserSummary = (member: ProjectMember): UserSummary => ({
  id: member.id,
  name: member.name,
  email: member.email,
  avatarUrl: member.avatarUrl ?? undefined,
  initials: member.initials,
  color: member.color,
})

export function useBoard(projectId = 'p-01', authenticated = true) {
  const [board, setBoard] = useState<BoardData>(emptyBoard)
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const boardCache = useRef<Record<string, BoardData>>({})
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<BoardFilter>('all')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!authenticated || !localStorage.getItem('taskflow-token')) return
    Promise.allSettled([
      taskApi.getBoard(projectId),
      projectApi.getMembers(projectId),
    ])
      .then(([boardResult, membersResult]) => {
        const nextBoard = boardResult.status === 'fulfilled'
          ? boardResult.value
          : emptyBoard
        const members = membersResult.status === 'fulfilled'
          ? membersResult.value.map(memberToUserSummary)
          : nextBoard.project.members
        const columns = nextBoard.columns.length > 0
          ? nextBoard.columns
          : emptyBoard.columns.map((column) => ({ ...column, tasks: [] }))
        const loadedBoard = {
          ...nextBoard,
          project: { ...nextBoard.project, members },
          columns,
        }

        boardCache.current[loadedBoard.project.id] = loadedBoard
        setBoard(loadedBoard)
        setProjects((current) => {
          const withoutCurrent = current.filter((item) => item.id !== loadedBoard.project.id)
          return [loadedBoard.project, ...withoutCurrent]
        })
      })
      .finally(() => setLoading(false))
  }, [projectId, authenticated])

  const moveTask = (taskId: string, nextStatus: TaskStatus, reviewer?: UserSummary, properties?: TaskPropertiesUpdate) => {
    setBoard((current) => {
      const moved = current.columns.flatMap((column) => column.tasks).find((item) => item.id === taskId)
      if (!moved || moved.status === nextStatus) return current
      const assignees = properties
        ? current.project.members.filter((member) => properties.assigneeIds.includes(member.id))
        : moved.assignees
      return {
        ...current,
        columns: current.columns.map((column) => ({
          ...column,
          tasks: column.id === nextStatus
            ? [...column.tasks, {
                ...moved,
                status: nextStatus,
                ...(reviewer ? { reviewer } : {}),
                ...(properties ? {
                  description: properties.description,
                  priority: properties.priority,
                  assignees,
                  startDate: properties.startDate,
                  endDate: properties.endDate,
                  overdueReason: properties.overdueReason || undefined,
                  acceptanceResult: properties.acceptanceResult || undefined,
                } : {}),
              }]
            : column.tasks.filter((item) => item.id !== taskId),
        })),
      }
    })
    void taskApi.moveTask(taskId, nextStatus, 0, reviewer?.id, properties)
  }

  const selectProject = (nextProjectId: string) => {
    if (nextProjectId === board.project.id) return
    boardCache.current[board.project.id] = board
    const cachedBoard = boardCache.current[nextProjectId]
    if (cachedBoard) {
      setBoard(cachedBoard)
      return
    }
    setLoading(true)
    taskApi.getBoard(nextProjectId)
      .then((nextBoard) => {
        boardCache.current[nextProjectId] = nextBoard
        setBoard(nextBoard)
      })
      .finally(() => setLoading(false))
  }

  const createProject = async (input: CreateProjectInput) => {
    const project: ProjectSummary = await projectApi.createProject(input)
    const newBoard: BoardData = {
      project,
      columns: [
        { id: 'backlog', title: 'Cần làm', accent: '#64748b', limit: 8, tasks: [] },
        { id: 'in-progress', title: 'Đang làm', accent: '#2563eb', limit: 4, tasks: [] },
        { id: 'review', title: 'Đang duyệt', accent: '#d97706', limit: 3, tasks: [] },
        { id: 'done', title: 'Hoàn thành', accent: '#0f9f8f', tasks: [] },
      ],
    }
    boardCache.current[board.project.id] = board
    boardCache.current[project.id] = newBoard
    setProjects((current) => [...current, project])
    setBoard(newBoard)
  }

  const addTask = async (input: CreateTaskInput) => {
    const created = await taskApi.createTask(board.project.id, { ...input, status: 'backlog' })
    setBoard((current) => ({
      ...current,
      columns: current.columns.map((column) => column.id === created.status ? { ...column, tasks: [created, ...column.tasks] } : column),
    }))
  }

  const deleteTask = async (taskId: string) => {
    try {
      await taskApi.deleteTask(taskId)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Không thể xóa công việc.')
      return
    }
    setBoard((current) => ({
      ...current,
      columns: current.columns.map((column) => ({
        ...column,
        tasks: column.tasks.filter((task) => task.id !== taskId),
      })),
    }))
  }

  const updateProjectMembers = useCallback((members: UserSummary[]) => {
    setBoard((current) => ({
      ...current,
      project: { ...current.project, members },
    }))
  }, [])

  const updateTask = (taskId: string, updater: (task: Task) => Task) => {
    setBoard((current) => ({ ...current, columns: current.columns.map((column) => ({ ...column, tasks: column.tasks.map((task) => task.id === taskId ? updater(task) : task) })) }))
  }

  const logTime = (taskId: string, entry: TimesheetEntry) => updateTask(taskId, (task) => ({ ...task, timesheets: [...task.timesheets, entry] }))
  const addComment = (taskId: string, comment: TaskComment) => updateTask(taskId, (task) => ({ ...task, comments: task.comments + 1, commentItems: [...task.commentItems, comment] }))
  const updateReviewer = (taskId: string, reviewer: UserSummary) => {
    updateTask(taskId, (task) => ({ ...task, reviewer }))
    void taskApi.setReviewer(taskId, reviewer.id)
  }
  const updateProperties = (taskId: string, properties: TaskPropertiesUpdate) => {
    setBoard((current) => {
      const assignees = current.project.members.filter((member) => properties.assigneeIds.includes(member.id))
      return { ...current, columns: current.columns.map((column) => ({ ...column, tasks: column.tasks.map((task) => task.id === taskId ? {
        ...task,
        description: properties.description,
        priority: properties.priority,
        assignees,
        startDate: properties.startDate,
        endDate: properties.endDate,
        overdueReason: properties.overdueReason || undefined,
        acceptanceResult: properties.acceptanceResult || undefined,
      } : task) })) }
    })
    void taskApi.updateProperties(taskId, properties)
  }

  const activeUserId = getActiveUser().id
  const filteredColumns = useMemo(() => board.columns.map((column) => ({
    ...column,
    tasks: column.tasks.filter((item) => {
      const matchesQuery = `${item.key} ${item.title} ${item.description} ${getTaskAssignees(item).map((member) => member.name).join(' ')}`.toLowerCase().includes(query.toLowerCase())
      const matchesFilter = filter === 'all'
        || (filter === 'mine' && getTaskAssignees(item).some((member) => member.id === activeUserId))
        || (filter === 'priority' && ['urgent', 'high'].includes(item.priority))
        || (filter === 'due-soon' && new Date(item.endDate) <= new Date('2026-10-20'))
      return matchesQuery && matchesFilter
    }),
  })), [activeUserId, board.columns, filter, query])

  return { board, projects, columns: filteredColumns, query, setQuery, filter, setFilter, loading, selectProject, createProject, moveTask, addTask, deleteTask, updateProjectMembers, logTime, addComment, updateReviewer, updateProperties }
}

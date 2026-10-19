import { useEffect, useMemo, useRef, useState } from 'react'
import { currentUser, initialBoard } from '../data/mockData'
import { projectApi } from '../services/projectApi'
import { taskApi } from '../services/taskApi'
import { getTaskAssignees, type BoardData, type BoardFilter, type CreateProjectInput, type CreateTaskInput, type ProjectSummary, type Task, type TaskComment, type TaskPropertiesUpdate, type TaskStatus, type TimesheetEntry, type UserSummary } from '../types/task'

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false'

export function useBoard(projectId = 'p-01') {
  const [board, setBoard] = useState<BoardData>(initialBoard)
  const [projects, setProjects] = useState<ProjectSummary[]>([initialBoard.project])
  const boardCache = useRef<Record<string, BoardData>>({ [initialBoard.project.id]: initialBoard })
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<BoardFilter>('all')
  const [loading, setLoading] = useState(!USE_MOCKS)

  useEffect(() => {
    if (USE_MOCKS) return
    taskApi.getBoard(projectId)
      .then(setBoard)
      .catch(() => setBoard(initialBoard))
      .finally(() => setLoading(false))
  }, [projectId])

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
    if (!USE_MOCKS) void taskApi.moveTask(taskId, nextStatus, 0, reviewer?.id, properties)
  }

  const selectProject = (nextProjectId: string) => {
    if (nextProjectId === board.project.id) return
    boardCache.current[board.project.id] = board
    const cachedBoard = boardCache.current[nextProjectId]
    if (cachedBoard) {
      setBoard(cachedBoard)
      return
    }
    if (!USE_MOCKS) {
      setLoading(true)
      taskApi.getBoard(nextProjectId)
        .then((nextBoard) => {
          boardCache.current[nextProjectId] = nextBoard
          setBoard(nextBoard)
        })
        .finally(() => setLoading(false))
    }
  }

  const createProject = (input: CreateProjectInput) => {
    const project: ProjectSummary = {
      id: `project-${Date.now()}`,
      ...input,
      progress: 0,
      members: [currentUser],
    }
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
    if (!USE_MOCKS) void projectApi.createProject(input)
  }

  const addTask = (input: CreateTaskInput) => {
    const assignees = board.project.members.filter((member) => input.assigneeIds.includes(member.id))
    const newTask: Task = {
      id: `local-${Date.now()}`,
      key: `${board.project.key}-${130 + board.columns.flatMap((column) => column.tasks).length}`,
      title: input.title,
      description: input.description,
      type: input.type, priority: input.priority, status: 'backlog', assignees,
      labels: [], comments: 0, attachments: 0, checklist: { completed: 0, total: 0 },
      startDate: input.startDate, endDate: input.endDate, timesheets: [], commentItems: [],
    }
    setBoard((current) => ({
      ...current,
      columns: current.columns.map((column) => column.id === 'backlog' ? { ...column, tasks: [newTask, ...column.tasks] } : column),
    }))
    if (!USE_MOCKS) void taskApi.createTask(projectId, { ...input, status: 'backlog' })
  }

  const deleteTask = (taskId: string) => {
    setBoard((current) => ({
      ...current,
      columns: current.columns.map((column) => ({
        ...column,
        tasks: column.tasks.filter((task) => task.id !== taskId),
      })),
    }))
    if (!USE_MOCKS) void taskApi.deleteTask(taskId)
  }

  const inviteMember = (member: UserSummary) => {
    setBoard((current) => ({
      ...current,
      project: { ...current.project, members: [...current.project.members, member] },
    }))
  }

  const updateTask = (taskId: string, updater: (task: Task) => Task) => {
    setBoard((current) => ({ ...current, columns: current.columns.map((column) => ({ ...column, tasks: column.tasks.map((task) => task.id === taskId ? updater(task) : task) })) }))
  }

  const logTime = (taskId: string, entry: TimesheetEntry) => updateTask(taskId, (task) => ({ ...task, timesheets: [...task.timesheets, entry] }))
  const addComment = (taskId: string, comment: TaskComment) => updateTask(taskId, (task) => ({ ...task, comments: task.comments + 1, commentItems: [...task.commentItems, comment] }))
  const updateReviewer = (taskId: string, reviewer: UserSummary) => {
    updateTask(taskId, (task) => ({ ...task, reviewer }))
    if (!USE_MOCKS) void taskApi.setReviewer(taskId, reviewer.id)
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
    if (!USE_MOCKS) void taskApi.updateProperties(taskId, properties)
  }

  const filteredColumns = useMemo(() => board.columns.map((column) => ({
    ...column,
    tasks: column.tasks.filter((item) => {
      const matchesQuery = `${item.key} ${item.title} ${item.description} ${getTaskAssignees(item).map((member) => member.name).join(' ')}`.toLowerCase().includes(query.toLowerCase())
      const matchesFilter = filter === 'all'
        || (filter === 'mine' && getTaskAssignees(item).some((member) => member.id === currentUser.id))
        || (filter === 'priority' && ['urgent', 'high'].includes(item.priority))
        || (filter === 'due-soon' && new Date(item.endDate) <= new Date('2026-10-20'))
      return matchesQuery && matchesFilter
    }),
  })), [board.columns, filter, query])

  return { board, projects, columns: filteredColumns, query, setQuery, filter, setFilter, loading, selectProject, createProject, moveTask, addTask, deleteTask, inviteMember, logTime, addComment, updateReviewer, updateProperties }
}

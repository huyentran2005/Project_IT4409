import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { projectApi } from '../services/projectApi'
import { taskApi } from '../services/taskApi'
import type { ProjectMember } from '../types/project'
import { getTaskAssignees, type BoardData, type BoardFilter, type CreateProjectInput, type CreateTaskInput, type ProjectSummary, type Task, type TaskComment, type TaskPropertiesUpdate, type TaskStatus, type TimesheetEntry, type TimesheetInput, type UserSummary } from '../types/task'
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
  const [allTasks, setAllTasks] = useState<Task[]>([])
  const boardCache = useRef<Record<string, BoardData>>({})
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<BoardFilter>('all')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!authenticated || !localStorage.getItem('taskflow-token')) return
    Promise.allSettled([
      projectApi.listProjects(),
      taskApi.getAllTasks(),
      taskApi.getBoard(projectId),
      projectApi.getMembers(projectId),
    ])
      .then(([projectsResult, allTasksResult, boardResult, membersResult]) => {
        const fetchedProjects = projectsResult.status === 'fulfilled'
          ? projectsResult.value
          : []
        if (allTasksResult.status === 'fulfilled') {
          setAllTasks(allTasksResult.value)
        }
        if (boardResult.status !== 'fulfilled') {
          setBoard({
            ...emptyBoard,
            project: { ...emptyBoard.project, id: '', name: 'Chưa có dự án' },
          })
          setProjects(fetchedProjects)
          return
        }
        const nextBoard = boardResult.value
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
        if (fetchedProjects.length > 0) {
          setProjects(fetchedProjects.map((item) => item.id === loadedBoard.project.id ? loadedBoard.project : item))
        } else {
          setProjects((current) => {
            const withoutCurrent = current.filter((item) => item.id !== loadedBoard.project.id)
            return [loadedBoard.project, ...withoutCurrent]
          })
        }
      })
      .finally(() => setLoading(false))
  }, [projectId, authenticated])

  const withCalculatedProgress = (nextBoard: BoardData): BoardData => {
    const total = nextBoard.columns.reduce((sum, col) => sum + col.tasks.length, 0)
    const done = nextBoard.columns.find((col) => col.id === 'done')?.tasks.length ?? 0
    const progress = total > 0 ? Math.round((done / total) * 100) : 0
    const updatedProject: ProjectSummary = {
      ...nextBoard.project,
      progress,
      totalTasks: total,
      doneTasks: done,
    }
    setProjects((current) => current.map((p) => p.id === updatedProject.id ? updatedProject : p))
    return {
      ...nextBoard,
      project: updatedProject,
    }
  }

  const refresh = useCallback(async () => {
    try {
      const latest = await taskApi.getBoard(board.project.id)
      setBoard((current) => ({
        ...current,
        project: { ...current.project, progress: latest.project.progress },
        columns: latest.columns.length > 0 ? latest.columns : current.columns,
      }))
    } catch {
      // Keep the current board if the refresh fails.
    }
  }, [board.project.id])

  const syncWithServer = (request: Promise<unknown>) => {
    request.then(() => refresh()).catch((err) => {
      alert(err instanceof Error ? err.message : 'Không thể lưu thay đổi.')
      void refresh()
    })
  }

  const moveTask = (taskId: string, nextStatus: TaskStatus, reviewer?: UserSummary, properties?: TaskPropertiesUpdate) => {
    const previousBoard = board
    const previousAllTasks = allTasks
    setBoard((current) => {
      const moved = current.columns.flatMap((column) => column.tasks).find((item) => item.id === taskId)
      if (!moved || moved.status === nextStatus) return current
      const assignees = properties
        ? current.project.members.filter((member) => properties.assigneeIds.includes(member.id))
        : moved.assignees
      const completedAt = nextStatus === 'done'
        ? (moved.completedAt ?? new Date().toISOString())
        : undefined
      const updatedTask: Task = {
        ...moved,
        status: nextStatus,
        completedAt,
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
      }
      setAllTasks((items) => items.map((item) => item.id === taskId ? updatedTask : item))
      return withCalculatedProgress({
        ...current,
        columns: current.columns.map((column) => ({
          ...column,
          tasks: column.id === nextStatus
            ? [...column.tasks, updatedTask]
            : column.tasks.filter((item) => item.id !== taskId),
        })),
      })
    })
    return taskApi.moveTask(taskId, nextStatus, 0, reviewer?.id, properties)
      .then((saved) => {
        setBoard((current) => ({
          ...withCalculatedProgress({
            ...current,
            columns: current.columns.map((column) => ({
              ...column,
              tasks: column.id === saved.status
                ? [saved, ...column.tasks.filter((task) => task.id !== taskId)]
                : column.tasks.filter((task) => task.id !== taskId),
            })),
          }),
        }))
        setAllTasks((items) => items.map((task) => task.id === taskId ? saved : task))
        return saved
      })
      .catch((err) => {
        setBoard(previousBoard)
        setAllTasks(previousAllTasks)
        throw err
      })
  }

  const loadProject = async (nextProjectId: string) => {
    const nextBoard = await taskApi.getBoard(nextProjectId)
    boardCache.current[nextProjectId] = nextBoard
    setBoard(nextBoard)
    setProjects((current) => [...current.filter((item) => item.id !== nextProjectId), nextBoard.project])
    return nextBoard
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
        { id: 'backlog', title: 'Cần làm', accent: '#64748b', tasks: [] },
        { id: 'in-progress', title: 'Đang làm', accent: '#2563eb', tasks: [] },
        { id: 'review', title: 'Đang duyệt', accent: '#d97706', tasks: [] },
        { id: 'done', title: 'Hoàn thành', accent: '#0f9f8f', tasks: [] },
      ],
    }
    if (board.project.id) {
      boardCache.current[board.project.id] = board
    }
    boardCache.current[project.id] = newBoard
    setProjects((current) => [...current.filter((item) => item.id !== project.id), project])
    setBoard(newBoard)
  }

  const addTask = async (input: CreateTaskInput) => {
    const created = await taskApi.createTask(board.project.id, { ...input, status: input.status ?? 'backlog' })
    setAllTasks((items) => [created, ...items])
    setBoard((current) => withCalculatedProgress({
      ...current,
      columns: current.columns.map((column) => column.id === created.status ? { ...column, tasks: [created, ...column.tasks] } : column),
    }))
  }

  const deleteTask = async (taskId: string) => {
    try {
      await taskApi.deleteTask(taskId)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Không thể xóa công việc.')
      return false
    }
    setAllTasks((items) => items.filter((task) => task.id !== taskId))
    setBoard((current) => withCalculatedProgress({
      ...current,
      columns: current.columns.map((column) => ({
        ...column,
        tasks: column.tasks.filter((task) => task.id !== taskId),
      })),
    }))
    return true
  }

  const updateProjectMembers = useCallback((members: UserSummary[]) => {
    setBoard((current) => ({
      ...current,
      project: { ...current.project, members },
    }))
  }, [])

  const updateTask = (taskId: string, updater: (task: Task) => Task) => {
    setAllTasks((items) => items.map((task) => task.id === taskId ? updater(task) : task))
    setBoard((current) => ({ ...current, columns: current.columns.map((column) => ({ ...column, tasks: column.tasks.map((task) => task.id === taskId ? updater(task) : task) })) }))
  }

  const logTime = async (taskId: string, input: TimesheetInput): Promise<TimesheetEntry> => {
    const entry = await taskApi.logTime(taskId, input)
    updateTask(taskId, (task) => ({ ...task, timesheets: [entry, ...task.timesheets] }))
    return entry
  }
  const removeTimesheet = async (taskId: string, entryId: string) => {
    await taskApi.deleteTimesheet(entryId)
    updateTask(taskId, (task) => ({ ...task, timesheets: task.timesheets.filter((entry) => entry.id !== entryId) }))
  }
  const addComment = async (taskId: string, body: string): Promise<TaskComment> => {
    const comment = await taskApi.addComment(taskId, body)
    updateTask(taskId, (task) => ({ ...task, comments: task.comments + 1, commentItems: [...task.commentItems, comment] }))
    return comment
  }
  const removeComment = async (taskId: string, commentId: string) => {
    await taskApi.deleteComment(commentId)
    updateTask(taskId, (task) => ({ ...task, comments: Math.max(task.comments - 1, 0), commentItems: task.commentItems.filter((comment) => comment.id !== commentId) }))
  }
  const updateReviewer = async (taskId: string, reviewer: UserSummary) => {
    updateTask(taskId, (task) => ({ ...task, reviewer }))
    const saved = await taskApi.setReviewer(taskId, reviewer.id)
    updateTask(taskId, (task) => task.id === saved.id ? saved : task)
    return saved
  }
  const updateProperties = async (taskId: string, properties: TaskPropertiesUpdate) => {
    setBoard((current) => {
      const assignees = current.project.members.filter((member) => properties.assigneeIds.includes(member.id))
      const applyProps = (task: Task): Task => ({
        ...task,
        description: properties.description,
        priority: properties.priority,
        assignees,
        startDate: properties.startDate,
        endDate: properties.endDate,
        overdueReason: properties.overdueReason || undefined,
        acceptanceResult: properties.acceptanceResult || undefined,
      })
      setAllTasks((items) => items.map((task) => task.id === taskId ? applyProps(task) : task))
      return { ...current, columns: current.columns.map((column) => ({ ...column, tasks: column.tasks.map((task) => task.id === taskId ? applyProps(task) : task) })) }
    })
    const saved = await taskApi.updateProperties(taskId, properties)
    updateTask(taskId, (task) => task.id === saved.id ? saved : task)
    return saved
  }
  const activeUserId = getActiveUser().id
  const filteredColumns = useMemo(() => {
    const dueSoonLimit = new Date()
    dueSoonLimit.setDate(dueSoonLimit.getDate() + 7)
    return board.columns.map((column) => ({
      ...column,
      tasks: column.tasks.filter((item) => {
        const matchesQuery = `${item.key} ${item.title} ${item.description} ${getTaskAssignees(item).map((member) => member.name).join(' ')}`.toLowerCase().includes(query.toLowerCase())
        const matchesFilter = filter === 'all'
          || (filter === 'mine' && getTaskAssignees(item).some((member) => member.id === activeUserId))
          || (filter === 'priority' && ['urgent', 'high'].includes(item.priority))
          || (filter === 'due-soon' && item.status !== 'done' && new Date(`${item.endDate}T23:59:59`) <= dueSoonLimit)
        return matchesQuery && matchesFilter
      }),
    }))
  }, [activeUserId, board.columns, filter, query])

  return { board, projects, allTasks, columns: filteredColumns, query, setQuery, filter, setFilter, loading, selectProject, loadProject, createProject, moveTask, addTask, deleteTask, updateProjectMembers, logTime, removeTimesheet, addComment, removeComment, updateReviewer, updateProperties, refresh }
}

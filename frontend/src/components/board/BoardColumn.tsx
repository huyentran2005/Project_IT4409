import type { BoardColumn as BoardColumnType, Task, TaskStatus } from '../../types/task'
import { Icon } from '../ui/Icon'
import { TaskCard } from './TaskCard'

interface BoardColumnProps {
  column: BoardColumnType
  onOpenTask: (task: Task) => void
  onMoveTask: (taskId: string, status: TaskStatus) => void
  onDeleteTask: (taskId: string) => void
  onQuickAdd: (status: TaskStatus) => void
}

export function BoardColumn({ column, onOpenTask, onMoveTask, onDeleteTask, onQuickAdd }: BoardColumnProps) {
  return (
    <section className="board-column" onDragOver={(event) => event.preventDefault()} onDrop={(event) => onMoveTask(event.dataTransfer.getData('text/task-id'), column.id)}>
      <header className="column-header">
        <div><span className="column-dot" style={{ background: column.accent }} /><h2>{column.title}</h2><span className="column-count">{column.tasks.length}</span></div>
        <div>{column.limit && <span className="column-limit">Tối đa {column.limit}</span>}</div>
      </header>
      <div className="column-tasks">
        {column.tasks.map((task) => <TaskCard task={task} onOpen={onOpenTask} onDelete={onDeleteTask} key={task.id} />)}
        {column.tasks.length === 0 && <div className="empty-column">Thả công việc vào đây</div>}
      </div>
      <button className="quick-add" onClick={() => onQuickAdd(column.id)}><Icon name="plus" size={16} />Thêm công việc</button>
    </section>
  )
}

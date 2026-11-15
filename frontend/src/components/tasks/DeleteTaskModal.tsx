import type { Task } from '../../types/task'
import { Icon } from '../ui/Icon'

interface DeleteTaskModalProps {
  task: Task
  onClose: () => void
  onConfirm: () => void
}

export function DeleteTaskModal({ task, onClose, onConfirm }: DeleteTaskModalProps) {
  return (
    <div className="modal-layer" role="dialog" aria-modal="true" aria-label="Xác nhận xóa công việc">
      <button className="modal-scrim" onClick={onClose} aria-label="Đóng" />
      <div className="create-modal delete-task-modal">
        <div className="create-modal__header">
          <div className="delete-task-modal__heading">
            <span className="delete-task-modal__icon" aria-hidden="true">
              <Icon name="trash" size={20} />
            </span>
            <div>
              <span>XÁC NHẬN XÓA</span>
              <h2>Xóa công việc này?</h2>
            </div>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Đóng">
            <Icon name="close" />
          </button>
        </div>

        <p className="delete-task-modal__body">
          Bạn có chắc chắn muốn xóa công việc <strong>“{task.title}”</strong> ({task.key}) không? Hành động này không thể hoàn tác.
        </p>

        <div className="create-modal__actions">
          <button type="button" className="secondary-button" onClick={onClose}>
            Hủy
          </button>
          <button type="button" className="danger-button" onClick={onConfirm}>
            <Icon name="trash" size={16} />
            Xóa công việc
          </button>
        </div>
      </div>
    </div>
  )
}

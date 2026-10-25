# Hướng dẫn & Báo cáo tiến độ: API Quản lý Công việc (Tạo, Hiển thị & Xóa Task)

> **Nhánh thực hiện:** `feature/task`  
> **Người phụ trách:** Nguyễn Thu Trang  
> **Đồng bộ với:** `docs/database-design.md` và hợp đồng dữ liệu tại `frontend/src/services/taskApi.ts`.

---

## 1. Khớp với thiết kế cơ sở dữ liệu (Database Mapping)

Module sử dụng trực tiếp các bảng đã có trong `database/accounts_and_projects.sql`, `database/workflow_sprints_and_tasks.sql` và `database/notifications_and_audit_logs.sql` (**không cần sửa đổi cấu trúc database**):

| Bảng / Cột | Vai trò trong luồng Tạo, Hiển thị & Xóa Task |
| :--- | :--- |
| `projects.id`, `key`, `task_sequence`, `is_archived`, `deleted_at` | Kiểm tra dự án đang hoạt động; tăng nguyên tử `task_sequence` bằng `UPDATE ... RETURNING` để sinh số thứ tự `tasks.number` và mã công việc dạng `UPPER(key)-number` (ví dụ: `TF-1`). |
| `project_members`, `project_roles`, `project_role_permissions`, `permissions` | Kiểm tra người dùng hiện tại có thuộc dự án và vai trò có quyền `task.manage` (mặc định: `owner`, `manager`, `member` được phép; `viewer` bị chặn `403`). |
| `statuses` (`code`, `name`, `category`, `color`, `position`, `wip_limit`) | Xác định cột trạng thái của task (`backlog`, `in-progress`, `review`, `done`), kiểm tra giới hạn số lượng công việc tối đa (`wip_limit`) và gán `completed_at` nếu `category = 'done'`. |
| `tasks` (`id`, `project_id`, `number`, `status_id`, `reporter_id`, `type`, `priority`, `title`, `description`, `position`, `start_date`, `end_date`, `completed_at`, `deleted_at`) | Lưu thông tin chính của công việc. Khi xóa chỉ gán `deleted_at = now()` (xóa mềm), các truy vấn đọc đều lọc `deleted_at IS NULL`. |
| `task_assignees` (`task_id`, `project_id`, `user_id`) | Lưu quan hệ nhiều-nhiều giữa công việc và danh sách người thực hiện (`assignees[]`). |
| `activity_logs` (`project_id`, `actor_id`, `entity_type`, `entity_id`, `action`, `description`, `changes`, `ip_address`) | Ghi nhận nhật ký kiểm toán bất biến cho thao tác tạo (`action = 'created'`) và xóa (`action = 'deleted'`) công việc. |

---

## 2. Các API đã xây dựng (`/api`)

| Method | Endpoint | Quyền yêu cầu | Request Body | Kết quả trả về |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/projects/{project_id}/board` | Thành viên dự án | — | `200 OK` (`BoardDataResponse`: thông tin dự án, thành viên, tiến độ `%` và 4 cột trạng thái kèm các task chưa xóa). |
| `GET` | `/api/projects/{project_id}/tasks` | Thành viên dự án | — | `200 OK` (`list[TaskResponse]`: danh sách phẳng tất cả các task chưa xóa của dự án). |
| `POST` | `/api/projects/{project_id}/tasks` | `task.manage` | `{ title, description, type, priority, startDate, endDate, assigneeIds[], status }` | `201 Created` (`TaskResponse`); `400` sai trạng thái / vượt WIP / assignee ngoài dự án; `403` không đủ quyền; `404` không thấy dự án; `422` dữ liệu không hợp lệ. |
| `DELETE` | `/api/tasks/{task_id}` | `task.manage` | — | `204 No Content` (xóa mềm thành công); `403` không có quyền; `404` task không tồn tại hoặc đã bị xóa trước đó. |

---

## 3. Các phần ĐÃ HOÀN THÀNH trong nhánh `feature/task`

### 3.1. Phía Backend (`backend/`)
1. **Định nghĩa SQLAlchemy ORM Models:**
   - `backend/app/models/project.py`: `Project`, `Permission`, `ProjectRole`, `ProjectRolePermission`, `ProjectMember`, `Status`.
   - `backend/app/models/task.py`: `Task`, `TaskAssignee`, `ActivityLog`.
2. **Định nghĩa Pydantic Schemas (`backend/app/schemas/task.py`):**
   - `CreateTaskRequest`: Cắt khoảng trắng `title` (1..300 ký tự) và `description`, kiểm tra `endDate >= startDate`, loại bỏ ID trùng trong `assigneeIds`.
   - `TaskResponse`, `BoardColumnResponse`, `ProjectSummaryResponse`, `BoardDataResponse`: Chuẩn hóa dữ liệu đầu ra dạng `camelCase` khớp 100% với kiểu `Task` và `BoardData` của Frontend.
3. **Logic nghiệp vụ & Bảo mật (`backend/app/services/task_service.py`):**
   - **Kiểm tra phân quyền (`check_task_manage_permission`):** Xác thực người gọi là thành viên dự án và có quyền `task.manage`. Chặn thao tác nếu dự án đã bị xóa hoặc lưu trữ (`is_archived = true`).
   - **Kiểm tra thành viên được giao việc (`assigneeIds`):** Chỉ cho phép gán task cho các user đang là thành viên hợp lệ của cùng dự án.
   - **Kiểm tra giới hạn cột (`wip_limit`):** Từ chối tạo mới nếu cột trạng thái đích đã đạt giới hạn WIP.
   - **Sinh mã công việc an toàn đồng thời:** Dùng `UPDATE projects SET task_sequence = task_sequence + 1 ... RETURNING task_sequence` để tránh trùng số thứ tự khi có nhiều request cùng lúc.
   - **Tính toán vị trí (`position`):** Tự động đặt công việc mới lên đầu cột trạng thái.
   - **Xóa mềm (`Soft Delete`):** Khi gọi `DELETE /api/tasks/{task_id}`, hệ thống cập nhật `deleted_at = now()`, giữ nguyên toàn vẹn lịch sử trong DB nhưng ẩn khỏi bảng Kanban.
   - **Ghi nhận Audit Log (`activity_logs`):** Tự động ghi log kèm thông tin thay đổi (`changes`) và địa chỉ IP khi tạo hoặc xóa task.
   - **Tự động khởi tạo dự án mặc định (`ensure_default_project_for_user`):** Khi người dùng mới đăng nhập trên Frontend (mặc định gọi `/api/projects/p-01/board` khi chưa có dự án), hệ thống tự động khởi tạo dự án mặc định kèm đủ 4 vai trò, 5 quyền và 4 cột trạng thái để thao tác ngay trên giao diện mà không bị phụ thuộc vào tiến độ của API Tạo dự án.

### 3.2. Phía Frontend (`frontend/`)
1. **Kết nối `CreateTaskModal.tsx`:**
   - Gửi dữ liệu thật qua `POST /api/projects/{project_id}/tasks`, có trạng thái `Đang tạo...` (`submitting`) và hiển thị thông báo lỗi trực tiếp trên modal nếu API trả về lỗi.
2. **Kết nối `useBoard.ts`, `App.tsx`, `MyTasksPage.tsx`:**
   - Tự động tải bảng công việc thật từ PostgreSQL (`GET /api/projects/{project_id}/board`) ngay sau khi đăng nhập.
   - Khi tạo công việc mới hoặc xóa công việc (`DELETE /api/tasks/{task_id}`), cập nhật trực tiếp lên giao diện Kanban và đồng bộ với Database (bấm F5 tải lại trang dữ liệu vẫn giữ nguyên).
   - Đồng bộ bộ lọc **"Của tôi"** và trang **"Công việc của tôi"** theo ID người dùng thật đang đăng nhập.

### 3.3. Kiểm thử tự động (`backend/tests/test_tasks.py`)
- Xây dựng bộ 6 unit/integration tests bằng `unittest` kiểm tra:
  1. Tạo task thành công (`201 Created`, sinh mã `TF-1`, gán nhiều assignees, ghi `activity_logs`).
  2. Tạo task với `endDate < startDate` (`422 Unprocessable Entity`).
  3. Chặn tạo task đối với `viewer` và người ngoài dự án (`403 Forbidden`).
  4. Chặn gán `assigneeIds` không thuộc dự án (`400 Bad Request`).
  5. Xóa mềm task (`204 No Content`, kiểm tra `deleted_at IS NOT NULL`, xóa lại lần 2 trả về `404 Not Found`).
  6. Tải Board và tự động khởi tạo dự án mặc định cho luồng Frontend (`GET /api/projects/p-01/board`).

---

## 4. Các phần CHƯA LÀM (Không thuộc phạm vi tạo/xóa task hiện tại)

Các tính năng mở rộng khác liên quan đến vòng đời của Task (đã có giao diện mock ở Frontend nhưng chưa viết API Backend trong nhánh này):

1. **Di chuyển / Cập nhật trạng thái công việc (`PATCH /api/tasks/{task_id}/move`):**
   - Kéo-thả thẻ công việc sang cột khác (`backlog` ↔ `in-progress` ↔ `review` ↔ `done`), cập nhật lại `status_id`, `position`, kiểm tra điều kiện bắt buộc có `reviewer_id` khi vào cột `review` và kiểm tra `overdue_reason` khi task quá hạn.
2. **Gán người duyệt công việc (`PATCH /api/tasks/{task_id}/reviewer`):**
   - Cập nhật cột `tasks.reviewer_id` trong Drawer chi tiết công việc.
3. **Cập nhật thuộc tính chi tiết công việc (`PATCH /api/tasks/{task_id}/properties`):**
   - Chỉnh sửa `description`, `priority`, `assigneeIds`, `startDate`, `endDate`, `overdueReason`, `acceptanceResult` sau khi task đã được tạo.
4. **Bình luận trên công việc (`GET / POST /api/tasks/{task_id}/comments`):**
   - Lưu và truy vấn bảng `comments` trong Drawer chi tiết công việc.
5. **Ghi nhận thời gian làm việc (`GET / POST /api/tasks/{task_id}/timesheets`):**
   - Lưu và truy vấn bảng `time_entries` để tính số giờ làm việc thực tế trên từng task.
6. **Checklist con & Nhãn công việc (`checklist_items`, `labels`, `task_labels`):**
   - Hiện tại khi trả về `TaskResponse`, trường `labels` trả mảng rỗng `[]` và `checklist` trả `{ completed: 0, total: 0 }`.

---

## 5. Danh sách file thay đổi trong nhánh

* **Backend:**
  * `backend/app/models/project.py` *(mới)*
  * `backend/app/models/task.py` *(mới)*
  * `backend/app/models/__init__.py` *(cập nhật)*
  * `backend/app/schemas/task.py` *(mới)*
  * `backend/app/services/task_service.py` *(mới)*
  * `backend/app/api/tasks.py` *(mới)*
  * `backend/app/main.py` *(cập nhật)*
  * `backend/tests/test_tasks.py` *(mới)*
* **Frontend:**
  * `frontend/src/hooks/useBoard.ts` *(cập nhật)*
  * `frontend/src/components/tasks/CreateTaskModal.tsx` *(cập nhật)*
  * `frontend/src/pages/MyTasksPage.tsx` *(cập nhật)*
  * `frontend/src/App.tsx` *(cập nhật)*

---

## 6. Hướng dẫn chạy thử & kiểm tra

### 6.1. Chạy bộ test tự động
```bash
docker compose up -d
docker compose exec backend pip install -r requirements.txt
docker compose exec backend python -m unittest tests/test_tasks.py -v
```

### 6.2. Thao tác trực tiếp trên giao diện Frontend
1. Mở trình duyệt tại `http://localhost:5173`, đăng ký hoặc đăng nhập tài khoản.
2. Nhấn nút **"+ Tạo công việc"** trên thanh công cụ → điền tiêu đề, mô tả, chọn người thực hiện → bấm **"Tạo công việc"**.
3. Nhấn **F5 (tải lại trang)** để kiểm chứng công việc đã được lưu vào PostgreSQL và hiển thị lại từ API `GET /api/projects/{project_id}/board`.
4. Nhấn vào biểu tượng **`...`** trên thẻ công việc (hoặc mở Drawer chi tiết) → bấm **"Xóa công việc"** → xác nhận xóa và kiểm tra thẻ biến mất khỏi bảng.


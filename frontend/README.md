# TaskFlow Frontend

Frontend quản lý dự án và công việc viết bằng React, TypeScript và Vite. Phiên bản này không có khái niệm Workspace; toàn bộ board, thành viên và phân quyền thuộc trực tiếp về Project.

## Chạy local

```bash
npm install
npm run dev
```

Mặc định giao diện dùng dữ liệu mẫu. Sao chép `.env.example` thành `.env` và đặt `VITE_USE_MOCKS=false` để gọi FastAPI thật tại `VITE_API_URL`.

## Cấu trúc

```text
src/
├── components/       # Component layout, board, task và UI dùng lại
├── data/mockData.ts  # Nguồn duy nhất chứa toàn bộ dữ liệu giả lập
├── hooks/            # State và nghiệp vụ giao diện
├── pages/            # Thành phần cấp trang
├── services/         # Toàn bộ lời gọi HTTP tới backend
├── types/            # TypeScript domain models
├── App.tsx
└── App.css
```

Các endpoint frontend đang chuẩn bị để sử dụng:

- `POST /api/auth/login`
- `POST /api/auth/register`
- `GET /api/auth/sso/google`
- `GET /api/auth/sso/github`
- `POST /api/auth/logout`
- `GET /api/projects/:projectId/board`
- `POST /api/projects/:projectId/tasks`
- `PATCH /api/tasks/:taskId`
- `PATCH /api/tasks/:taskId/move`
- `GET /api/tasks/:taskId/timesheets`
- `POST /api/tasks/:taskId/timesheets`
- `GET /api/projects/:projectId/members`
- `GET /api/projects/:projectId/documents`
- `GET /api/projects/:projectId/meetings`
- `POST /api/projects/:projectId/meetings`
- `GET /api/projects/:projectId/activity-logs`
- `GET /api/tasks/:taskId/comments`
- `POST /api/tasks/:taskId/comments`
- `PUT /api/projects/:projectId/role-permissions`
- `PATCH /api/projects/:projectId/members/:userId/role`

## Kiểm tra

```bash
npm run lint
npm run build
```

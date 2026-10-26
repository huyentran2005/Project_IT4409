# TaskFlow Frontend



## Chạy local

```bash
npm install
npm run dev
```

Giao diện gọi FastAPI tại địa chỉ được cấu hình bởi `VITE_API_URL`.

## Cấu trúc

```text
src/
├── components/       # Component layout, board, task và UI dùng lại
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

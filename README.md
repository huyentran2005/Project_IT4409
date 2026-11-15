# Project IT4409

Ứng dụng quản lý công việc gồm:

- **Frontend:** React, TypeScript và Vite
- **Backend:** FastAPI
- **Database:** PostgreSQL 16
- **Object storage:** MinIO


## Lựa chọn 1: Chạy toàn bộ dự án bằng Docker (khuyến nghị)

Thực hiện lần lượt các bước dưới đây. Đây là cách chạy được khuyến nghị vì
frontend, backend, PostgreSQL và MinIO đều được cấu hình sẵn trong Docker
Compose. Với cách này, **không cần tạo môi trường ảo Python `.venv`** và cũng
không cần cài Node.js hoặc Python trực tiếp trên máy.

### Bước 1: Cài công cụ cần thiết

Cài đặt trước:

- [Git](https://git-scm.com/downloads)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

Sau khi cài đặt, mở Docker Desktop và đợi Docker Engine khởi động hoàn tất.

### Bước 2: Tải mã nguồn

```bash
git clone https://github.com/huyentran2005/Project_IT4409.git
cd Project_IT4409
```

Nếu đã có mã nguồn trên máy, chỉ cần mở terminal tại thư mục gốc
`Project_IT4409`.

### Bước 3: Tạo file cấu hình môi trường

PowerShell:

```powershell
Copy-Item .env.example .env
```

Git Bash, macOS hoặc Linux:

```bash
cp .env.example .env
```

Các giá trị mặc định trong `.env.example` dùng được cho môi trường
development. Có thể đổi tài khoản hoặc mật khẩu trong `.env`, nhưng không
commit file này lên Git.

### Bước 4: Build và khởi động hệ thống

```bash
docker compose up -d --build
```

Lần build MinIO đầu tiên có thể mất vài phút vì image được build từ mã nguồn.
Các lần sau Docker sẽ sử dụng cache nên nhanh hơn.

### Bước 5: Kiểm tra trạng thái

```bash
docker compose ps
```

Các service `db`, `minio`, `qdrant`, `redis`, `document-worker`, `backend` và
`frontend` phải ở trạng thái `Up`. PostgreSQL, MinIO và Redis sẽ hiển thị thêm
trạng thái `healthy`.

Sau lần chạy đầu tiên hoặc sau khi xóa volume database, khởi tạo schema trực tiếp:

```powershell
docker compose exec -T db sh -lc 'until pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do sleep 2; done; psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/schema.sql'
```

Nếu service không khởi động, xem log bằng:

```bash
docker compose logs -f
```

### Bước 6: Tạo bucket trên MinIO

1. Mở http://localhost:9001.
2. Đăng nhập bằng `MINIO_ROOT_USER` và `MINIO_ROOT_PASSWORD` trong `.env`.
3. Tạo bucket có tên trùng với `MINIO_BUCKET` trong `.env`.

Với cấu hình mặc định, thông tin đăng nhập là `minioadmin` /
`minioadmin_password` và tên bucket là `task-files`.

### Bước 7: Truy cập các dịch vụ

| Dịch vụ | Địa chỉ |
| --- | --- |
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |
| MinIO Console | http://localhost:9001 |
| PostgreSQL | `localhost:5433` |

Backend và frontend tự động reload khi sửa source code. Nếu thay đổi dependency
trong `requirements.txt` hoặc `package.json`, build lại image bằng:

```bash
docker compose up -d --build
```

### Bước 8: Dừng hệ thống

```bash
docker compose down
```

Lệnh trên giữ lại dữ liệu PostgreSQL và MinIO. Chỉ khi muốn xóa toàn bộ dữ liệu development, dùng:

```bash
docker compose down -v
```

> Cảnh báo: tùy chọn `-v` xóa các Docker volume và dữ liệu trong database/MinIO.

## Các lệnh Docker thường dùng

```bash
# Chạy ở chế độ nền
docker compose up -d --build

# Xem trạng thái service
docker compose ps

# Theo dõi log toàn hệ thống
docker compose logs -f

# Chỉ xem log backend
docker compose logs -f backend

# Khởi động lại một service
docker compose restart backend
```

## Sau khi pull code mới

Mỗi thành viên có thể tự chọn chạy theo Lựa chọn 1 hoặc Lựa chọn 2. Các file và
thư mục chỉ dùng trên máy cá nhân như `.env`, `.venv/` và `node_modules/` đã
được khai báo trong `.gitignore`, nên không bị ghi đè khi pull code.

Nếu chạy toàn bộ bằng Docker (Lựa chọn 1):

```bash
git pull
docker compose up -d --build --remove-orphans
```

Tùy chọn `--remove-orphans` sẽ dọn container của service đã bị xóa khỏi
`compose.yaml`, chẳng hạn container Adminer cũ. Lệnh này không xóa volume dữ
liệu PostgreSQL hoặc MinIO.

Nếu chạy frontend/backend trực tiếp trên máy (Lựa chọn 2), sau khi pull nên cập
nhật dependency:

```powershell
# Backend: chạy sau khi kích hoạt .venv
pip install -r backend\requirements.txt

# Frontend
npm --prefix frontend ci

# PostgreSQL, MinIO, Qdrant, Redis và Celery worker
docker compose up -d --build db minio qdrant redis document-worker
```

File `.env` trên máy không tự cập nhật theo `.env.example`. Khi `.env.example`
có biến mới, cần bổ sung biến đó vào `.env` thủ công. Không dùng
`docker compose down -v` sau khi pull nếu muốn giữ dữ liệu local.

## Truy cập và xem PostgreSQL

### Cách 1: PostgreSQL CLI

Không cần cài `psql` trên máy; chạy client có sẵn trong container:

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Một số lệnh hữu ích bên trong `psql`:

```text
\dt                  -- Liệt kê bảng
\d ten_bang          -- Xem cấu trúc một bảng
SELECT * FROM ten_bang LIMIT 20;
\q                   -- Thoát
```

### Cách 2: DBeaver hoặc pgAdmin trên máy

Tạo kết nối PostgreSQL với các thông tin:

| Trường | Giá trị |
| --- | --- |
| Host | `localhost` |
| Port | `5433` |
| Database | Giá trị `POSTGRES_DB` trong `.env` |
| Username | Giá trị `POSTGRES_USER` trong `.env` |
| Password | Giá trị `POSTGRES_PASSWORD` trong `.env` |

Ứng dụng cài trên máy phải dùng host `localhost`.

## Lựa chọn 2: Chạy frontend và backend trực tiếp trên máy

Chạy frontend/backend ngoài Docker; PostgreSQL, MinIO, Qdrant, Redis và Celery
worker vẫn chạy trong Docker. Không khởi động service `backend`/`frontend` của
Compose trong option này.

### Bước 1: Tạo môi trường ảo cho backend

Yêu cầu Python 3.12. Từ thư mục gốc của dự án:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
```

Nếu PowerShell chặn script kích hoạt, chỉ thay đổi policy cho terminal hiện tại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Trên Git Bash, macOS hoặc Linux, lệnh kích hoạt tương ứng là:

```bash
source .venv/Scripts/activate  # Git Bash trên Windows
# source .venv/bin/activate    # macOS/Linux
```

### Bước 2: Khởi động PostgreSQL và MinIO

```bash
docker compose up -d --build db minio qdrant redis document-worker
```

### Bước 3: Khởi động backend

Khi backend chạy trực tiếp trên máy, hostname phải là `localhost` thay vì tên
service Docker `db` và `minio`.

Mở PowerShell tại thư mục gốc `Project_IT4409`, kích hoạt `.venv`, rồi chạy các
lệnh dưới đây trong **cùng một cửa sổ terminal**:

```powershell
.\.venv\Scripts\Activate.ps1
$env:DATABASE_URL="postgresql+psycopg://task_user:task_password@localhost:5433/task_db"
$env:MINIO_ENDPOINT="localhost:9000"
$env:QDRANT_URL="http://localhost:6333"
$env:CELERY_BROKER_URL="redis://localhost:6379/0"
uvicorn app.main:app --app-dir backend --reload --port 8000
```

Hai lệnh `$env:...` chỉ thiết lập biến môi trường tạm thời cho cửa sổ
PowerShell hiện tại; chúng không sửa file `.env`. Có thể xem lại giá trị bằng:

```powershell
$env:DATABASE_URL
$env:MINIO_ENDPOINT
$env:QDRANT_URL
$env:CELERY_BROKER_URL
```

Giữ terminal này mở trong lúc backend chạy. Sau đó truy cập:

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Bước 4: Xem dữ liệu PostgreSQL và file MinIO

Backend và frontend chạy local; PostgreSQL, MinIO, Qdrant, Redis và Celery worker
vẫn chạy trong Docker.

Để xem chi tiết database bằng dòng lệnh:

```powershell
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Trong `psql`, có thể dùng:

```text
\dt
\d ten_bang
SELECT * FROM ten_bang LIMIT 20;
\q
```

Nếu muốn giao diện trực quan, dùng DBeaver hoặc pgAdmin với cấu hình:

| Trường | Giá trị mặc định |
| --- | --- |
| Host | `localhost` |
| Port | `5433` |
| Database | `task_db` |
| Username | `task_user` |
| Password | `task_password` |

Để xem file trên MinIO:

1. Mở MinIO Console tại http://localhost:9001.
2. Đăng nhập bằng `MINIO_ROOT_USER` và `MINIO_ROOT_PASSWORD` trong `.env`.
3. Mở bucket `task-files`, hoặc bucket có tên được đặt trong `MINIO_BUCKET`.

`localhost:9000` là cổng S3 API để backend kết nối; giao diện xem và quản lý
file nằm tại `localhost:9001`.

### Bước 5: Khởi động frontend

Yêu cầu Node.js 22. Mở terminal khác:

```powershell
cd frontend
npm ci
npm run dev
```

## Kiểm tra trước khi tạo commit

```powershell
# Frontend
cd frontend
npm run lint
npm run build

# Kiểm tra backend khởi động được (từ thư mục gốc)
uvicorn app.main:app --app-dir backend --port 8000
```

Không commit các file/thư mục sau:

- `.env`
- `.venv/`
- `node_modules/`
- file log, cache hoặc dữ liệu local

## Quy trình Git để hạn chế xung đột

Không push trực tiếp lên nhánh `main`. Mỗi chức năng hoặc lỗi cần được thực hiện
trên một nhánh riêng và đưa vào `main` thông qua Pull Request.

### 1. Tạo nhánh mới từ `main`

Trước khi bắt đầu công việc, cập nhật phiên bản mới nhất của `main`:

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/ten-chuc-nang
```

Tên nhánh nên thể hiện rõ mục đích:

- `feature/ten-chuc-nang`: thêm chức năng mới
- `fix/ten-loi`: sửa lỗi
- `docs/noi-dung`: cập nhật tài liệu
- `chore/noi-dung`: thay đổi cấu hình hoặc công cụ phát triển

### 2. Commit thay đổi

Kiểm tra kỹ các file trước khi commit:

```bash
git status
git diff
git add <cac-file-can-commit>
git commit -m "feat: mo ta ngan gon thay doi"
```

Không dùng `git add .` một cách máy móc. Luôn kiểm tra để chắc chắn `.env`, dữ
liệu local và file sinh tự động không được đưa vào commit.

### 3. Đồng bộ với `main` trước khi push

```bash
git fetch origin
git rebase origin/main
```

Nếu có xung đột, mở từng file được Git thông báo, giữ lại nội dung đúng rồi chạy:

```bash
git add <file-da-xu-ly>
git rebase --continue
```

Sau khi đồng bộ, chạy lại các kiểm tra:

```powershell
npm --prefix frontend run lint
npm --prefix frontend run build
```

### 4. Push và tạo Pull Request

```bash
git push -u origin feature/ten-chuc-nang
```

Tạo Pull Request từ nhánh vừa push vào `main`. Chỉ merge khi:

- Các bước lint, build và test đều thành công.
- Ít nhất một thành viên khác đã review.
- Pull Request không còn xung đột với `main`.

### Quy ước chung cho cả nhóm

- Một nhánh chỉ giải quyết một chức năng hoặc một lỗi.
- Chia thay đổi thành các commit nhỏ, dễ đọc và dễ hoàn tác.
- Không dùng `git push --force` trên `main` hoặc nhánh dùng chung.
- Không sửa thủ công `package-lock.json`; dùng `npm install` khi đổi dependency.
- Trao đổi trước nếu nhiều người cần sửa cùng một file hoặc cùng một module.
- Sau khi Pull Request được merge, cập nhật lại `main` trước khi tạo nhánh mới.
- Nên bật Branch Protection trên GitHub cho `main`: bắt buộc Pull Request,
  review, status checks và chặn force push.

## Cấu trúc thư mục

```text
Project_IT4409/
├── backend/              # FastAPI API
│   ├── app/
│   │   └── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/             # React + TypeScript + Vite
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── docker/
│   └── minio/            # Image MinIO được build từ mã nguồn
├── .env.example          # Mẫu biến môi trường được commit
├── compose.yaml          # Chạy toàn bộ development stack
└── README.md
```

## Xử lý lỗi thường gặp

### PowerShell không nhận lệnh `source`

`source` là lệnh của Bash. Trong PowerShell, dùng:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Port đã được sử dụng

Kiểm tra các port `5173`, `8000`, `5433`, `6379`, `6333`, `9000` và `9001`, sau đó dừng chương trình/container đang chiếm port hoặc đổi port phía bên trái trong `compose.yaml`.

### Container không nhận cấu hình `.env` mới

```bash
docker compose down
docker compose up -d --build --force-recreate
```

### Frontend thiếu package sau khi đổi dependency

```bash
docker compose build --no-cache frontend
docker compose up -d frontend
```

# Chatbot hỏi đáp tài liệu

Chatbot đọc PDF, DOCX và DOC; chunk theo Heading 1/2/3; dùng LLM đang cấu hình để tách câu hỏi nhiều ý thành các truy vấn nhỏ; tìm kiếm hybrid dense + BM25 trên Qdrant cho từng truy vấn rồi tổng hợp câu trả lời bằng Gemini hoặc OpenRouter.

## Upload dự án và xử lý nền

Upload tài liệu dự án sẽ lưu file gốc vào MinIO, ghi metadata/trạng thái vào PostgreSQL rồi gửi job vào Redis/Celery. Worker đọc file từ MinIO, trích xuất và chunk PDF/DOCX/DOC, index vào Qdrant theo collection riêng của dự án, đồng thời lưu nội dung chunks dạng JSON vào MinIO. Trạng thái (`queued`, `processing`, `completed`, `failed`, `unsupported`) hiển thị trong danh sách tài liệu.

```powershell
# Option 1: chạy toàn bộ hệ thống trong Docker
docker compose up -d --build --remove-orphans

# Khởi tạo schema trực tiếp trên database mới/rỗng
docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/schema.sql'
```

`database/schema.sql` tạo trực tiếp toàn bộ schema. Chỉ chạy trên database mới/rỗng.

Chỉ PDF, DOCX và DOC được lập chỉ mục. Worker cần LibreOffice trong `PATH` để xử lý DOC cũ; nếu không có, trạng thái sẽ là `unsupported`. Các định dạng khác vẫn lưu được trên MinIO nhưng chưa trích xuất nội dung.

Tài liệu đã index có thể hỏi qua `POST /api/projects/{project_id}/chatbot/ask` với body `{"question":"...","top_k":6}`. Endpoint yêu cầu quyền `project.view` và chỉ tìm trong collection của dự án đó. Tài liệu dự án không xuất hiện trong chatbot tổng quát.

Trên trang từng dự án có nút chat nổi. Lịch sử hội thoại được lưu riêng theo user đăng nhập và project, nên user khác không xem được. Nút thùng rác **Reset** xóa tất cả phiên và tin nhắn của user hiện tại trong project đang mở; thao tác này không ảnh hưởng user hoặc project khác.

## Chạy trên PowerShell

```powershell
cd D:\Project_IT4409

# Cài dependency chung của backend và chatbot
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt

# Bổ sung nhóm biến Document Q&A từ .env.example vào .env và điền API key

# Option 2: backend/frontend local; các dịch vụ còn lại và worker trong Docker
docker compose up -d --build db minio qdrant redis document-worker

# Nếu database còn mới/rỗng, khởi tạo schema một lần
docker compose exec -T db sh -lc 'until pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do sleep 2; done; psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /database/schema.sql'

# Chạy backend local từ project root để .env được nạp
$env:PYTHONPATH = (Get-Location).Path
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir .\backend --reload --port 8000
```

Mở terminal khác để chạy frontend local:

```powershell
cd frontend
npm ci
npm run dev
```

Mở `http://127.0.0.1:8000/docs` và gọi:

1. `POST /api/chatbot/ingest` với `{}` để nạp toàn bộ tài liệu trong `docs` hoặc `{"path":"abc.pdf"}` để nạp một file.
2. `POST /api/chatbot/ask` với `{"question":"Nội dung chính là gì?","top_k":6}`.

## Lưu ý

- DOCX nhận heading từ style `Heading 1`, `Heading 2`, `Heading 3`.
- PDF không có heading semantic nên cấp heading được suy luận theo cỡ font.
- DOC cũ cần LibreOffice và lệnh `soffice` trong `PATH`.
- Dense embedding gọi OpenRouter với `nvidia/nemotron-3.5-embed-8b:free`; cần `OPENROUTER_API_KEY` kể cả khi LLM dùng Gemini.
- BM25 chạy trực tiếp trên full-text index của Qdrant 1.20; không tải model và không dùng FastEmbed.
- Collection mặc định là `documents_native_bm25` để không xung đột schema sparse-vector cũ.
- Chọn `LLM_PROVIDER=gemini` hoặc `LLM_PROVIDER=openrouter` trong `.env` chung.

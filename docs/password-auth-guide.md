# Hướng dẫn: Đăng nhập truyền thống (Email + Mật khẩu)

Bổ sung cho `docs/sso-guide.md`. Dùng **chung** bảng `users`, `auth_sessions` với SSO — **không cần sửa database**.

> Lưu ý: trang https://project.aiservice.vn/ là ứng dụng JS cần render/đăng nhập nên chưa đọc được giao diện thật. Logic dưới đây bám theo SRS TaskFlow (mục đăng ký/đăng nhập, JWT + refresh token, argon2) và luồng chuẩn của một web quản lý dự án. Nếu bạn gửi ảnh chụp màn hình trang đó, mình sẽ đối chiếu thêm.

## 1. Khớp với database

| Cột / bảng | Dùng cho đăng nhập mật khẩu |
|---|---|
| `users.email` (unique `lower(email)` khi `deleted_at IS NULL`) | định danh đăng nhập, luôn lưu chữ thường |
| `users.password_hash` | băm **Argon2id**; `NULL` = tài khoản chỉ có SSO |
| `users.full_name`, `phone` | điền từ form đăng ký |
| `users.email_verified_at` | `NULL` khi đăng ký bằng mật khẩu (chưa xác minh); SSO tự gán |
| `users.is_active`, `deleted_at` | khóa / xóa mềm → không đăng nhập được |
| `users.last_login_at` | cập nhật mỗi lần đăng nhập |
| `auth_sessions` | mỗi lần login/register tạo 1 dòng: `refresh_token_hash` (SHA-256), `expires_at` (7 ngày), `revoked_at` |

## 2. API mới (`/api/auth`)

| Method | Path | Body | Kết quả |
|---|---|---|---|
| POST | `/register` | `{name, email, phone?, password≥8}` | 201 `{accessToken, refreshToken, user}`; 409 email đã tồn tại; 422 dữ liệu sai |
| POST | `/login` | `{email, password}` | 200 như trên; 401 sai thông tin; 403 tài khoản bị khóa |
| POST | `/refresh` | `{refreshToken}` | 200 cặp token mới (rotation); 401 nếu sai/hết hạn/đã thu hồi |
| POST | `/logout` | `{refreshToken?}` | 200; thu hồi phiên tương ứng |
| GET | `/me` | Header `Bearer` | (đã có) |

## 3. Logic & bảo mật đã làm

1. **Argon2id** (`pwdlib`) – đúng yêu cầu SRS (bcrypt/argon2).
2. **Thông báo lỗi chung** "Email hoặc mật khẩu không đúng" + luôn verify hash giả khi email không tồn tại hoặc là tài khoản chỉ SSO → không lộ email nào đã đăng ký (user enumeration/timing).
3. **Đăng ký trùng email** (kể cả email đã có từ SSO) → 409, *không* tự gắn mật khẩu vào tài khoản SSO vì email chưa được xác minh.
4. **Chống pre-hijack**: nếu ai đó đăng ký mật khẩu bằng email của bạn, sau đó bạn đăng nhập Google/GitHub cùng email, hệ thống liên kết SSO nhưng **xóa `password_hash` cũ** và đặt `email_verified_at`. Kẻ tạo trước không còn vào được.
5. **Refresh token rotation**: mỗi lần `/refresh` thu hồi token cũ, cấp token mới. Nếu token đã thu hồi bị dùng lại → thu hồi **toàn bộ** phiên của user.
6. Tài khoản bị khóa (`is_active=false`) hoặc xóa mềm không đăng nhập/refresh được.

## 4. File thay đổi

Backend: `core/security.py` (hash/verify mật khẩu), `schemas/auth.py` (mới), `services/auth_service.py` (register/login/refresh/revoke + chống pre-hijack), `api/auth.py` (4 endpoint).
Frontend: `services/apiClient.ts` (đọc thông báo lỗi từ `detail`), `services/authApi.ts`, `App.tsx` (lưu/thu hồi refresh token), `pages/AuthPage.tsx` (mật khẩu tối thiểu 8 ký tự khi đăng ký).

`AuthPage` và các lời gọi `authApi.login/register` đã có sẵn trong project, backend chỉ thiếu endpoint nên không cần đổi giao diện.

## 5. Chạy thử

```bash
cp .env.example .env
# BẮT BUỘC đổi JWT_SECRET_KEY:  python -c "import secrets;print(secrets.token_urlsafe(48))"
docker compose up --build
# frontend/.env:  VITE_USE_MOCKS=false   (mặc định true = dữ liệu giả, không gọi backend)
```

Kiểm tra bằng curl:

```bash
curl -X POST localhost:8000/api/auth/register -H 'Content-Type: application/json' \
  -d '{"name":"Nguyễn Văn A","email":"a@example.com","password":"matkhau123"}'
curl -X POST localhost:8000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"a@example.com","password":"matkhau123"}'
curl localhost:8000/api/auth/me -H "Authorization: Bearer <accessToken>"
curl -X POST localhost:8000/api/auth/refresh -H 'Content-Type: application/json' -d '{"refreshToken":"<refreshToken>"}'
```

Kiểm tra DB: `SELECT email, password_hash IS NOT NULL AS has_pw, email_verified_at FROM users;` và `SELECT user_id, expires_at, revoked_at FROM auth_sessions;`.

Checklist thử tay: đăng ký → vào dashboard · đăng ký lại cùng email → báo trùng · sai mật khẩu → báo chung · đăng xuất → `revoked_at` có giá trị · tài khoản chỉ SSO đăng nhập mật khẩu → báo chung · đăng nhập Google cùng email với tài khoản mật khẩu → vẫn vào được, `password_hash` thành NULL.

## 6. Chưa làm (SRS có nêu) – bước tiếp theo

- **Quên/đặt lại mật khẩu qua email** và **xác minh email**: cần bảng token (vd `password_reset_tokens`) + dịch vụ gửi mail; schema hiện chưa có nên chưa thêm.
- **Chống dò mật khẩu** (rate limit theo IP/email, khóa tạm): nên thêm `slowapi` hoặc Redis.
- Refresh tự động ở frontend khi access token hết hạn (60 phút) – hiện `apiClient` chưa tự gọi `/refresh`.
- Đổi mật khẩu trong trang Hồ sơ.

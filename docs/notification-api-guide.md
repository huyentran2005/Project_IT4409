# Thông báo trong ứng dụng

Chuông trên thanh đầu trang tải thông báo của tài khoản đăng nhập, hiển thị số chưa đọc,
phân trang 20 thông báo/trang, mở công việc và đánh dấu đã đọc. Có nút làm mới và
đọc tất cả. Tải lại mỗi 30 giây khi trang hiển thị, khi quay lại cửa sổ và khi mở chuông.
Đây là thông báo trong ứng dụng; chưa gửi email, push trình duyệt hay dùng WebSocket.

## Khi nào tạo thông báo?

- Tạo task có người được giao: gửi cho người được giao (trừ chính người tạo).
- Cập nhật task, đổi trạng thái/người duyệt/người thực hiện, thêm bình luận, ghi giờ
  hoặc xóa task: gửi cho người tạo, người thực hiện và người duyệt liên quan.
- Khi đổi người thực hiện/người duyệt, người cũ cũng nhận thông báo nếu còn quyền xem.
- Không gửi cho chính người thao tác, không gửi trùng cho người có nhiều vai trò và
  không gửi khi cập nhật không làm thay đổi dữ liệu.
- Chỉ gửi cho tài khoản đang hoạt động, chưa xóa, có quyền `project.view` trong dự án.
  Tôn trọng `notification_settings.in_app_enabled`; chưa có bản ghi settings thì mặc định bật.

Task, nhật ký và thông báo được lưu trong cùng giao dịch. Không tạo bù thông báo cho
thao tác đã xảy ra trước khi triển khai chức năng này. Tính năng hiện áp dụng cho task,
chưa tạo thông báo cho meeting, tài liệu hay lời mời dự án.

## API

Tất cả endpoint yêu cầu `Authorization: Bearer <token>`.

| Method | Endpoint | Kết quả |
| --- | --- | --- |
| GET | `/api/notifications?limit=20&offset=0` | `{items, unreadCount, hasMore}`; mới nhất trước, `limit` 1–100 |
| PATCH | `/api/notifications/{id}/read` | Thông báo với `readAt`; gọi lại không đổi thời điểm đọc đầu tiên |
| PATCH | `/api/notifications/read-all` | 204; đánh dấu tất cả thông báo đang có quyền xem của tài khoản hiện tại |
| GET | `/api/tasks/{id}` | Task hiện tại, kiểm tra quyền `project.view`; phục vụ mở task từ thông báo |

Thông báo gồm `id`, `projectId`, `taskId`, `taskKey`, `taskTitle`, `projectName`,
`taskDeleted`, `type`, `title`, `readAt`, `createdAt`. Không cho truyền `user_id` để
đọc hộp thư của người khác. Thông báo dự án không còn quyền truy cập được loại khỏi
danh sách và số chưa đọc; đánh dấu đọc thông báo của người khác trả 404.

Trạng thái đã đọc lưu trong database và tồn tại sau khi tải lại/đăng nhập lại. Bấm
thông báo của task đã xóa sẽ báo rõ; task đã mất quyền truy cập không thể mở.

Dùng bảng `notifications` và `notification_settings` đã có trong schema, không cần
migration nếu database đã được khởi tạo đầy đủ theo dự án.

## Kiểm tra thủ công

1. Đăng nhập tài khoản A và giao task cho tài khoản B cùng dự án.
2. Đăng nhập B ở trình duyệt khác, mở chuông hoặc đợi tối đa 30 giây khi trang hiển thị.
3. Bấm thông báo: mở đúng task/dự án, số chưa đọc giảm; tải lại vẫn giữ đã đọc.
4. A cập nhật task hoặc thêm bình luận: B nhận thông báo mới; A không nhận từ thao tác của mình.
5. Dùng đọc tất cả, chuyển trang và kiểm tra task đã xóa/thu hồi quyền truy cập.


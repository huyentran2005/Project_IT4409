import html
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import settings


class EmailDeliveryError(Exception):
    """Lỗi nghiệp vụ được phát sinh khi không thể gửi email."""

    pass


def smtp_is_configured() -> bool:
    """Mục đích:
        Kiểm tra các cấu hình SMTP tối thiểu đã được khai báo.

    Đầu vào:
        Không có; hàm đọc cấu hình SMTP từ biến môi trường của ứng dụng.
    Đầu ra:
        ``True`` nếu có SMTP host và email người gửi, ngược lại là ``False``.
    """
    return bool(settings.SMTP_HOST and settings.SMTP_FROM_EMAIL)


def send_project_invitation_email(
    *,
    recipient: str,
    project_name: str,
    inviter_name: str,
    invite_url: str,
    expires_in_days: int = 7,
) -> None:
    """Mục đích:
        Tạo và gửi email mời người dùng tham gia dự án.

    Đầu vào:
        recipient: Địa chỉ email của người nhận lời mời.
        project_name: Tên dự án được mời tham gia.
        inviter_name: Tên người gửi lời mời.
        invite_url: Đường dẫn để người nhận mở và xử lý lời mời.
        expires_in_days: Số ngày lời mời còn hiệu lực, mặc định là 7 ngày.
    Đầu ra:
        Không trả về dữ liệu khi gửi thành công; phát sinh EmailDeliveryError
        nếu SMTP chưa được cấu hình hoặc quá trình gửi thư thất bại.
    """
    if not smtp_is_configured():
        raise EmailDeliveryError("SMTP chưa được cấu hình")

    safe_project = html.escape(project_name)
    safe_inviter = html.escape(inviter_name)
    safe_url = html.escape(invite_url, quote=True)

    message = EmailMessage()
    message["Subject"] = f"{inviter_name} mời bạn tham gia {project_name}"
    message["From"] = formataddr(
        (settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL)
    )
    message["To"] = recipient
    message.set_content(
        f"{inviter_name} đã mời bạn tham gia dự án {project_name}.\n\n"
        f"Mở lời mời: {invite_url}\n\n"
        f"Lời mời hết hạn sau {expires_in_days} ngày."
    )
    message.add_alternative(
        f"""
        <!doctype html>
        <html lang="vi">
          <body style="font-family:Arial,sans-serif;color:#1f2937;line-height:1.6">
            <div style="max-width:560px;margin:32px auto;padding:28px;border:1px solid #e5e7eb;border-radius:16px">
              <h2 style="margin-top:0">Lời mời tham gia dự án</h2>
              <p><strong>{safe_inviter}</strong> đã mời bạn tham gia dự án <strong>{safe_project}</strong>.</p>
              <p style="margin:28px 0">
                <a href="{safe_url}" style="display:inline-block;padding:12px 20px;color:#fff;background:#5b5ce2;text-decoration:none;border-radius:8px">
                  Xem lời mời
                </a>
              </p>
              <p style="font-size:13px;color:#6b7280">Lời mời hết hạn sau {expires_in_days} ngày. Bạn cần đăng nhập bằng đúng email nhận thư để chấp nhận hoặc từ chối.</p>
            </div>
          </body>
        </html>
        """,
        subtype="html",
    )

    try:
        if settings.SMTP_USE_SSL:
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=settings.SMTP_TIMEOUT_SECONDS,
            )
        else:
            smtp = smtplib.SMTP(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=settings.SMTP_TIMEOUT_SECONDS,
            )

        with smtp:
            smtp.ehlo()
            if settings.SMTP_USE_TLS and not settings.SMTP_USE_SSL:
                smtp.starttls()
                smtp.ehlo()
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("Không thể gửi email lời mời") from exc


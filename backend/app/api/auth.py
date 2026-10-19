import secrets
import urllib.parse
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserSummary, user_to_summary
from app.services.google_oauth import (
    get_google_auth_url,
    exchange_google_code,
    get_google_user_info,
)
from app.services.auth_service import handle_google_login

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/sso/google")
def sso_google_redirect(response: Response):
    """
    Khởi tạo phiên đăng nhập Google SSO và chuyển hướng người dùng sang Google.

    Input (Đầu vào):
        - Không yêu cầu tham số truyền vào từ client.

    Output (Đầu ra):
        - 302 Found (Redirect): Chuyển hướng trình duyệt tới màn hình đăng nhập Google (accounts.google.com).
        - Set-Cookie: `oauth_state` lưu mã ngẫu nhiên (max-age 10 phút, HttpOnly, SameSite=Lax) để phòng chống tấn công CSRF.
    """
    state = secrets.token_urlsafe(32)
    redirect_url = get_google_auth_url(state)

    res = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    res.set_cookie(
        key="oauth_state",
        value=state,
        max_age=600,
        httponly=True,
        samesite="lax",
    )
    return res


@router.get("/sso/google/callback")
async def sso_google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Tiếp nhận mã authorization code từ Google sau khi người dùng xác thực và cấp quyền.

    Input (Đầu vào):
        - code (str, query param): Mã ủy quyền do Google trả về để đổi lấy Access Token.
        - state (str, query param): Chuỗi bảo mật ngẫu nhiên để xác thực phiên chống CSRF.
        - error (str, optional query param): Thông báo lỗi nếu người dùng hủy cấp quyền hoặc Google từ chối.
        - Cookie: `oauth_state` chứa mã state đã lưu ở bước khởi tạo.
        - Database Session: Kết nối PostgreSQL để tra cứu và lưu trữ tài khoản.

    Output (Đầu ra):
        - 302 Found (Redirect):
            + Thành công: Điều hướng về Frontend kèm token xác thực:
              `${FRONTEND_URL}/auth/callback?token={access_token}&refresh_token={refresh_token}`
            + Thất bại: Điều hướng về Frontend kèm thông tin lỗi:
              `${FRONTEND_URL}?error={error_message}`
        - Xóa Cookie: `oauth_state` sau khi hoàn tất xác thực.
    """
    # 1. Người dùng bấm Cancel hoặc Google báo lỗi
    if error:
        error_url = f"{settings.FRONTEND_URL}?error={urllib.parse.quote(error)}"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)

    if not code:
        error_url = f"{settings.FRONTEND_URL}?error=missing_code"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)

    # 2. Kiểm tra mã state chống tấn công CSRF (nếu có cookie lưu)
    saved_state = request.cookies.get("oauth_state")
    if saved_state and state and saved_state != state:
        error_url = f"{settings.FRONTEND_URL}?error=invalid_state"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)

    try:
        # 3. Đổi authorization code lấy access token của Google
        token_data = await exchange_google_code(code)
        google_access_token = token_data.get("access_token")
        if not google_access_token:
            error_url = f"{settings.FRONTEND_URL}?error=failed_to_retrieve_google_token"
            return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)

        # 4. Lấy thông tin người dùng từ Google
        google_user_info = await get_google_user_info(google_access_token)

        # 5. Xử lý lưu / liên kết tài khoản trong Database
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        access_token, refresh_token, user = handle_google_login(
            db=db,
            google_user_info=google_user_info,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        # 6. Điều hướng về Frontend kèm Access Token
        redirect_url = (
            f"{settings.FRONTEND_URL}/auth/callback"
            f"?token={urllib.parse.quote(access_token)}"
            f"&refresh_token={urllib.parse.quote(refresh_token)}"
        )
        res = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
        res.delete_cookie(key="oauth_state")
        return res

    except Exception as exc:
        error_msg = urllib.parse.quote(str(exc))
        error_url = f"{settings.FRONTEND_URL}?error={error_msg}"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)


@router.get("/me", response_model=UserSummary)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Lấy thông tin hồ sơ của người dùng hiện tại đang đăng nhập.

    Input (Đầu vào):
        - Header: Authorization: Bearer <access_token> (JWT token hợp lệ sinh ra khi đăng nhập).

    Output (Đầu ra):
        - Status 200 OK: Trả về đối tượng JSON UserSummary gồm:
            + id (str): Định danh UUID của người dùng.
            + name (str): Họ và tên hiển thị.
            + email (str): Địa chỉ email.
            + avatarUrl (str | None): Đường dẫn ảnh đại diện.
            + initials (str): Hai chữ cái viết tắt tên hiển thị.
            + color (str): Mã màu đại diện (#RRGGBB).
        - Status 401 Unauthorized: Nếu thiếu token, token không hợp lệ hoặc tài khoản bị khóa.
    """
    return user_to_summary(current_user)


@router.post("/logout")
def logout():
    """
    Đăng xuất người dùng khỏi hệ thống.

    Input (Đầu vào):
        - Không bắt buộc tham số.

    Output (Đầu ra):
        - Status 200 OK: Trả về đối tượng {"status": "ok"}.
    """
    return {"status": "ok"}

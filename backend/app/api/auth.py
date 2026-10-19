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
    """Khởi tạo phiên đăng nhập Google SSO và chuyển hướng người dùng."""
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
    """Tiếp nhận callback từ Google sau khi người dùng xác thực và cấp quyền."""
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
    """Lấy thông tin tài khoản hiện tại đang đăng nhập."""
    return user_to_summary(current_user)


@router.post("/logout")
def logout():
    """Đăng xuất người dùng."""
    return {"status": "ok"}


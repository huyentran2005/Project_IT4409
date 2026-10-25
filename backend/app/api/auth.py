import secrets
import urllib.parse
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import hash_token
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.auth_session import AuthSession
from app.models.user import User
from app.schemas.user import UserSummary, user_to_summary
from pydantic import BaseModel, Field
from app.schemas.user import ProfileUpdate, ProfileResponse
from app.services.google_oauth import (
    get_google_auth_url,
    exchange_google_code,
    get_google_user_info,
)
from app.services.github_oauth import (
    get_github_auth_url,
    exchange_github_code,
    get_github_user_info,
)
from app.services.auth_service import handle_google_login, handle_github_login

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


@router.get("/sso/github")
def sso_github_redirect(response: Response):
    """
    Khởi tạo phiên đăng nhập GitHub SSO và chuyển hướng người dùng sang GitHub.

    Input (Đầu vào):
        - Không yêu cầu tham số truyền vào từ client.

    Output (Đầu ra):
        - 302 Found (Redirect): Chuyển hướng trình duyệt tới màn hình ủy quyền GitHub (github.com/login/oauth/authorize).
        - Set-Cookie: `oauth_state` lưu mã ngẫu nhiên (max-age 10 phút, HttpOnly, SameSite=Lax) để phòng chống CSRF.
    """
    state = secrets.token_urlsafe(32)
    redirect_url = get_github_auth_url(state)

    res = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    res.set_cookie(
        key="oauth_state",
        value=state,
        max_age=600,
        httponly=True,
        samesite="lax",
    )
    return res


@router.get("/sso/github/callback")
async def sso_github_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Tiếp nhận mã authorization code từ GitHub sau khi người dùng xác thực và ủy quyền.

    Input (Đầu vào):
        - code (str, query param): Mã ủy quyền do GitHub trả về để đổi lấy Access Token.
        - state (str, query param): Chuỗi bảo mật ngẫu nhiên để xác thực phiên chống CSRF.
        - error (str, optional query param): Thông báo lỗi nếu người dùng hủy hoặc GitHub từ chối (vd: access_denied).
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
    # 1. Người dùng bấm Cancel hoặc GitHub báo lỗi
    if error:
        err_detail = error_description or error
        error_url = f"{settings.FRONTEND_URL}?error={urllib.parse.quote(err_detail)}"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)

    if not code:
        error_url = f"{settings.FRONTEND_URL}?error=missing_code"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)

    # 2. Kiểm tra mã state chống tấn công CSRF
    saved_state = request.cookies.get("oauth_state")
    if saved_state and state and saved_state != state:
        error_url = f"{settings.FRONTEND_URL}?error=invalid_state"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)

    try:
        # 3. Đổi authorization code lấy access token của GitHub
        token_data = await exchange_github_code(code)
        github_access_token = token_data.get("access_token")
        if not github_access_token:
            err_msg = token_data.get("error_description") or token_data.get("error") or "failed_to_retrieve_github_token"
            error_url = f"{settings.FRONTEND_URL}?error={urllib.parse.quote(err_msg)}"
            return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)

        # 4. Lấy thông tin người dùng từ GitHub (đã xử lý bóc tách email private)
        github_user_info = await get_github_user_info(github_access_token)

        # 5. Xử lý lưu / liên kết tài khoản trong Database
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        access_token, refresh_token, user = handle_github_login(
            db=db,
            github_user_info=github_user_info,
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


@router.get("/me", response_model=ProfileResponse)
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
    #cho api lấy hồ sơ trả cả số điện thoại
    return ProfileResponse(
        **user_to_summary(current_user).model_dump(),
        phone=current_user.phone,
    )

#endpoint cập nhật hồ sơ user đang đăng nhập
@router.patch("/me", response_model=ProfileResponse)
def update_current_user_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cập nhật hồ sơ của tài khoản đang đăng nhập."""
    changes = payload.model_dump(exclude_unset=True)

    if "name" in changes:
        current_user.full_name = changes["name"]

    if "phone" in changes:
        current_user.phone = changes["phone"] or None

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(current_user)

    return ProfileResponse(
        **user_to_summary(current_user).model_dump(),
        phone=current_user.phone,
    )

#đăng xuất
class LogOutRequest(BaseModel):
    refresh_token: str = Field(min_length = 1, max_length = 512)
@router.post("/logout", status_code = status.HTTP_204_NO_CONTENT)
def logout(logout_request: LogOutRequest,
           db: Session = Depends(get_db),):
    revoke_session(db, logout_request.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

#thu hoi phien dang nhap dua tren refresh token
def revoke_session(db: Session, refresh_token: str) -> None:
    token_hash = hash_token(refresh_token)
    (
        db.query(AuthSession)
        .filter(AuthSession.refresh_token_hash == token_hash,
                AuthSession.revoked_at.is_(None),
                )
        .update(
            {"revoked_at": datetime.now(timezone.utc)},
            synchronize_session=False,
        )
    )
    db.commit()
    """
    Database lưu hash, nên phải hash token nhận được để tìm phiên.
    revoked_at khác NULL nghĩa là phiên đã bị thu hồi.
    Chỉ thu hồi phiên có token tương ứng; các thiết bị khác vẫn giữ phiên của chúng.
    Gọi lại với cùng token vẫn thành công và không thay đổi thời điểm thu hồi cũ.
    """

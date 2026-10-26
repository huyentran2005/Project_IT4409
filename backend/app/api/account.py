from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.core.security import hash_password, hash_token, verify_password
from app.db.session import get_db
from app.models.auth_session import AuthSession
from app.models.user import User
from app.schemas.account import ChangePasswordRequest

router = APIRouter(prefix="/auth", tags=["account"])


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Đổi mật khẩu của người dùng đang đăng nhập.

    Input: Header Authorization Bearer; JSON {currentPassword?, newPassword (>= 8 ký tự), refreshToken?}.
        Tài khoản chỉ đăng nhập SSO (chưa có mật khẩu) được bỏ currentPassword để đặt mật khẩu lần đầu.
    Output: 200 {"status": "ok"}; 400 sai mật khẩu hiện tại; 422 dữ liệu sai; 401 chưa đăng nhập.
    Sau khi đổi, các phiên khác (refresh token) bị thu hồi; phiên của refreshToken gửi kèm được giữ lại.
    """
    if current_user.password_hash:
        if not payload.currentPassword or not verify_password(
            payload.currentPassword, current_user.password_hash
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mật khẩu hiện tại không đúng.",
            )

    current_user.password_hash = hash_password(payload.newPassword)

    sessions = db.query(AuthSession).filter(
        AuthSession.user_id == current_user.id, AuthSession.revoked_at.is_(None)
    )
    if payload.refreshToken:
        sessions = sessions.filter(
            AuthSession.refresh_token_hash != hash_token(payload.refreshToken)
        )
    sessions.update({AuthSession.revoked_at: datetime.now(timezone.utc)})
    db.commit()
    return {"status": "ok"}

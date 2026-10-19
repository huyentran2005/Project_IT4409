import ipaddress
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.config import settings
from app.core.security import create_access_token, generate_refresh_token
from app.models.user import User
from app.models.oauth_account import OAuthAccount
from app.models.auth_session import AuthSession


def sanitize_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    try:
        ipaddress.ip_address(ip)
        return ip
    except ValueError:
        return None


def handle_google_login(
    db: Session,
    google_user_info: dict,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, str, User]:
    """
    Xử lý thông tin người dùng từ Google:
    1. Kiểm tra tài khoản trong oauth_accounts
    2. Nếu chưa có, kiểm tra email trong bảng users để liên kết (Account Linking)
    3. Nếu hoàn toàn mới, tự động tạo mới User và OAuthAccount
    4. Ghi nhận phiên đăng nhập trong auth_sessions
    5. Trả về access_token, refresh_token và User
    """
    google_id = str(google_user_info.get("sub"))
    email = str(google_user_info.get("email", "")).strip().lower()
    name = (
        google_user_info.get("name")
        or google_user_info.get("given_name")
        or email.split("@")[0]
    )
    picture = google_user_info.get("picture")

    # 1. Kiểm tra trong oauth_accounts
    oauth_account = (
        db.query(OAuthAccount)
        .filter(
            OAuthAccount.provider == "google",
            OAuthAccount.provider_user_id == google_id,
        )
        .first()
    )

    now = datetime.now(timezone.utc)

    if oauth_account:
        user = oauth_account.user
    else:
        # 2. Kiểm tra email đã có trong users chưa
        user = (
            db.query(User)
            .filter(
                func.lower(User.email) == email,
                User.deleted_at.is_(None)
            )
            .first()
        )

        if user:
            # Liên kết tài khoản Google với User hiện tại
            new_oauth = OAuthAccount(
                user_id=user.id,
                provider="google",
                provider_user_id=google_id,
                provider_email=email,
            )
            db.add(new_oauth)
        else:
            # 3. Tạo User mới
            user = User(
                email=email,
                full_name=name,
                avatar_url=picture,
                avatar_color="#5B5CE2",
                email_verified_at=now,
                is_active=True,
            )
            db.add(user)
            db.flush()  # Sinh user.id

            new_oauth = OAuthAccount(
                user_id=user.id,
                provider="google",
                provider_user_id=google_id,
                provider_email=email,
            )
            db.add(new_oauth)

    # Cập nhật thời điểm đăng nhập gần nhất
    user.last_login_at = now
    if not user.avatar_url and picture:
        user.avatar_url = picture

    # 4. Tạo phiên đăng nhập AuthSession
    raw_refresh_token, refresh_token_hash = generate_refresh_token()
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash=refresh_token_hash,
        user_agent=user_agent[:500] if user_agent else None,
        ip_address=sanitize_ip(client_ip),
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)
    db.commit()
    db.refresh(user)

    # 5. Ký Access Token
    access_token = create_access_token(subject=str(user.id))

    return access_token, raw_refresh_token, user


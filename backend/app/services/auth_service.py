import ipaddress
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.config import settings
from sqlalchemy.exc import IntegrityError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_token,
    hash_password,
    verify_password,
)
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


def handle_oauth_login(
    db: Session,
    provider: str,
    provider_user_id: str,
    email: str,
    name: str,
    picture: str | None = None,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, str, User]:
    """
    Xử lý chung cho các nhà cung cấp OAuth (Google, GitHub,...):
    1. Kiểm tra tài khoản trong oauth_accounts
    2. Nếu chưa có, kiểm tra email trong bảng users để liên kết (Account Linking)
    3. Nếu hoàn toàn mới, tự động tạo mới User và OAuthAccount
    4. Ghi nhận phiên đăng nhập trong auth_sessions
    5. Trả về access_token, refresh_token và User
    """
    # 1. Kiểm tra trong oauth_accounts
    oauth_account = (
        db.query(OAuthAccount)
        .filter(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        )
        .first()
    )

    now = datetime.now(timezone.utc)

    if oauth_account:
        user = oauth_account.user
    else:
        # 2. Kiểm tra email đã có trong users chưa (Account Linking)
        user = (
            db.query(User)
            .filter(
                func.lower(User.email) == email,
                User.deleted_at.is_(None)
            )
            .first()
        )

        if user:
            # Chống "pre-hijack": tài khoản đăng ký bằng mật khẩu nhưng email chưa xác minh
            # có thể do kẻ khác tạo trước bằng email của nạn nhân. Provider đã xác minh email,
            # nên khi liên kết ta xoá mật khẩu cũ và đánh dấu email đã xác minh.
            if user.email_verified_at is None:
                user.password_hash = None
                user.email_verified_at = now
            # Liên kết tài khoản OAuth mới với User hiện tại
            existing_link = (
                db.query(OAuthAccount)
                .filter(
                    OAuthAccount.user_id == user.id,
                    OAuthAccount.provider == provider,
                )
                .first()
            )
            if not existing_link:
                new_oauth = OAuthAccount(
                    user_id=user.id,
                    provider=provider,
                    provider_user_id=provider_user_id,
                    provider_email=email,
                )
                db.add(new_oauth)
        else:
            # 3. Tạo User mới hoàn toàn
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
                provider=provider,
                provider_user_id=provider_user_id,
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


def handle_google_login(
    db: Session,
    google_user_info: dict,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, str, User]:
    """Xử lý đăng nhập bằng Google OAuth 2.0."""
    google_id = str(google_user_info.get("sub"))
    email = str(google_user_info.get("email", "")).strip().lower()
    name = (
        google_user_info.get("name")
        or google_user_info.get("given_name")
        or email.split("@")[0]
    )
    picture = google_user_info.get("picture")

    return handle_oauth_login(
        db=db,
        provider="google",
        provider_user_id=google_id,
        email=email,
        name=name,
        picture=picture,
        client_ip=client_ip,
        user_agent=user_agent,
    )


def handle_github_login(
    db: Session,
    github_user_info: dict,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, str, User]:
    """Xử lý đăng nhập bằng GitHub OAuth 2.0."""
    github_id = str(github_user_info.get("id"))
    email = str(github_user_info.get("email", "")).strip().lower()
    name = (
        github_user_info.get("name")
        or github_user_info.get("login")
        or email.split("@")[0]
    )
    picture = github_user_info.get("avatar_url")

    return handle_oauth_login(
        db=db,
        provider="github",
        provider_user_id=github_id,
        email=email,
        name=name,
        picture=picture,
        client_ip=client_ip,
        user_agent=user_agent,
    )

# Đăng nhập truyền thống
class AuthError(Exception):
    """Lỗi nghiệp vụ xác thực; code dùng để API map sang HTTP status."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _issue_tokens(
    db: Session,
    user: User,
    client_ip: str | None,
    user_agent: str | None,
) -> tuple[str, str]:
    """Tạo auth_sessions mới + access token. Chưa commit."""
    now = datetime.now(timezone.utc)
    raw_refresh, refresh_hash = generate_refresh_token()
    db.add(
        AuthSession(
            user_id=user.id,
            refresh_token_hash=refresh_hash,
            user_agent=user_agent[:500] if user_agent else None,
            ip_address=sanitize_ip(client_ip),
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    return create_access_token(subject=str(user.id)), raw_refresh


def register_with_password(
    db: Session,
    *,
    name: str,
    email: str,
    password: str,
    phone: str | None,
    client_ip: str | None,
    user_agent: str | None,
) -> tuple[str, str, User]:
    existing = (
        db.query(User)
        .filter(func.lower(User.email) == email, User.deleted_at.is_(None))
        .first()
    )
    if existing:
        # Không tự "gắn" mật khẩu vào tài khoản SSO: email chưa được xác minh ở bước đăng ký.
        raise AuthError("email_taken", "Email này đã được đăng ký. Hãy đăng nhập (hoặc dùng Google/GitHub).")

    user = User(
        email=email,
        full_name=name,
        phone=phone,
        password_hash=hash_password(password),
        avatar_color="#5B5CE2",
        email_verified_at=None,  # chưa xác minh; xác minh qua email là bước mở rộng
        is_active=True,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:  # race: uq_users_email_active
        db.rollback()
        raise AuthError("email_taken", "Email này đã được đăng ký.")

    access, refresh = _issue_tokens(db, user, client_ip, user_agent)
    db.commit()
    db.refresh(user)
    return access, refresh, user


def login_with_password(
    db: Session,
    *,
    email: str,
    password: str,
    client_ip: str | None,
    user_agent: str | None,
) -> tuple[str, str, User]:
    user = (
        db.query(User)
        .filter(func.lower(User.email) == email, User.deleted_at.is_(None))
        .first()
    )
    # Luôn verify (kể cả khi không có user / chỉ SSO) và dùng thông báo chung
    ok = verify_password(password, user.password_hash if user else None)
    if not user or not ok:
        raise AuthError("invalid_credentials", "Email hoặc mật khẩu không đúng.")
    if not user.is_active:
        raise AuthError("inactive", "Tài khoản đã bị khóa. Vui lòng liên hệ quản trị viên.")

    user.last_login_at = datetime.now(timezone.utc)
    access, refresh = _issue_tokens(db, user, client_ip, user_agent)
    db.commit()
    db.refresh(user)
    return access, refresh, user


def refresh_session(
    db: Session,
    *,
    refresh_token: str,
    client_ip: str | None,
    user_agent: str | None,
) -> tuple[str, str, User]:
    """Rotation: thu hồi refresh token cũ, cấp cặp token mới."""
    now = datetime.now(timezone.utc)
    session = (
        db.query(AuthSession)
        .filter(AuthSession.refresh_token_hash == hash_token(refresh_token))
        .first()
    )
    if not session:
        raise AuthError("invalid_token", "Phiên đăng nhập không hợp lệ.")
    if session.revoked_at is not None:
        # Token đã dùng rồi bị dùng lại -> nghi bị đánh cắp: thu hồi mọi phiên của user
        db.query(AuthSession).filter(
            AuthSession.user_id == session.user_id, AuthSession.revoked_at.is_(None)
        ).update({AuthSession.revoked_at: now})
        db.commit()
        raise AuthError("invalid_token", "Phiên đăng nhập đã bị thu hồi. Vui lòng đăng nhập lại.")
    if session.expires_at <= now:
        raise AuthError("expired", "Phiên đăng nhập đã hết hạn.")

    user = session.user
    if user.deleted_at is not None or not user.is_active:
        raise AuthError("inactive", "Tài khoản không khả dụng.")

    session.revoked_at = now
    access, refresh = _issue_tokens(db, user, client_ip, user_agent)
    db.commit()
    return access, refresh, user


def revoke_session(db: Session, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    session = (
        db.query(AuthSession)
        .filter(
            AuthSession.refresh_token_hash == hash_token(refresh_token),
            AuthSession.revoked_at.is_(None),
        )
        .first()
    )
    if session:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()

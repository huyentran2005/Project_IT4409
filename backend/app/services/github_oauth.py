import urllib.parse
import httpx
from app.core.config import settings

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


def get_github_auth_url(state: str) -> str:
    """Tạo đường dẫn chuyển hướng sang màn hình đăng nhập và ủy quyền của GitHub."""
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": settings.GITHUB_REDIRECT_URI,
        "scope": "read:user user:email",
        "state": state,
    }
    return f"{GITHUB_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def exchange_github_code(code: str) -> dict:
    """
    Gửi authorization code lên GitHub để đổi lấy access token.
    Bắt buộc phải kèm header Accept: application/json.
    """
    data = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "client_secret": settings.GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.GITHUB_REDIRECT_URI,
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "TaskFlow-App",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(GITHUB_TOKEN_URL, data=data, headers=headers)
        response.raise_for_status()
        return response.json()


async def get_github_user_info(access_token: str) -> dict:
    """
    Gọi GitHub API lấy thông tin người dùng.
    Nếu email là None/Private, gọi tiếp /user/emails để bóc tách email chính (primary).
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "TaskFlow-App",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Lấy thông tin cơ bản
        res = await client.get(GITHUB_USER_URL, headers=headers)
        res.raise_for_status()
        user_data = res.json()

        email = user_data.get("email")

        # 2. Nếu email là private (None), gọi endpoint /user/emails
        if not email:
            emails_res = await client.get(GITHUB_EMAILS_URL, headers=headers)
            if emails_res.status_code == 200:
                emails_list = emails_res.json()
                # Tìm email chính và đã được xác thực
                primary_verified = next(
                    (item["email"] for item in emails_list if item.get("primary") and item.get("verified")),
                    None,
                )
                if not primary_verified:
                    primary_verified = next(
                        (item["email"] for item in emails_list if item.get("primary")),
                        None,
                    )
                if not primary_verified and emails_list:
                    primary_verified = emails_list[0].get("email")

                email = primary_verified

        # 3. Fallback nếu người dùng hoàn toàn không có email
        if not email:
            login = user_data.get("login", "unknown")
            email = f"{login}@users.noreply.github.com"

        name = user_data.get("name") or user_data.get("login") or email.split("@")[0]

        return {
            "id": str(user_data.get("id")),
            "login": user_data.get("login"),
            "email": email.strip().lower(),
            "name": name,
            "avatar_url": user_data.get("avatar_url"),
        }


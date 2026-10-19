from pydantic import BaseModel, ConfigDict
from app.models.user import User


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    avatarUrl: str | None = None
    initials: str
    color: str


def get_user_initials(name: str) -> str:
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "U"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def user_to_summary(user: User) -> UserSummary:
    return UserSummary(
        id=str(user.id),
        name=user.full_name,
        email=user.email,
        avatarUrl=user.avatar_url,
        initials=get_user_initials(user.full_name),
        color=user.avatar_color or "#5B5CE2",
    )


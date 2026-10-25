from pydantic import BaseModel, ConfigDict
from app.models.user import User
from pydantic import Field, field_validator

class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    avatarUrl: str | None = None
    initials: str
    color: str
#dữ liệu client gửi lên để sửa hồ sơ
class ProfileUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    name: str | None = Field(
        default=None, min_length=1, max_length=120
    )
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Họ tên không được để null")
        return value

#dữ liệu server trả về
class ProfileResponse(UserSummary):
    phone: str | None = None

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


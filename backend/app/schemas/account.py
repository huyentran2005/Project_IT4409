from pydantic import BaseModel, Field, model_validator


class ChangePasswordRequest(BaseModel):
    # Tài khoản chỉ đăng nhập SSO (chưa có mật khẩu) có thể bỏ trống để đặt mật khẩu lần đầu
    currentPassword: str | None = Field(default=None, max_length=128)
    newPassword: str = Field(min_length=8, max_length=128)
    # Refresh token của thiết bị đang dùng: giữ phiên này, thu hồi các phiên còn lại
    refreshToken: str | None = None

    @model_validator(mode="after")
    def _different(self):
        if self.currentPassword is not None and self.currentPassword == self.newPassword:
            raise ValueError("Mật khẩu mới phải khác mật khẩu hiện tại")
        return self

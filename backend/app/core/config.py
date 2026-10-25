from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    PROJECT_NAME: str = "Task Management API"

    # Database
    DATABASE_URL: str = "postgresql+psycopg://task_user:task_password@db:5432/task_db"

    # Google SSO OAuth 2.0
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/sso/google/callback"
    FRONTEND_URL: str = "http://localhost:5173"

    # GitHub SSO OAuth 2.0
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_REDIRECT_URI: str = "http://localhost:8000/api/auth/sso/github/callback"

    # MinIO (lưu tài liệu)
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "minioadmin_password"
    MINIO_BUCKET: str = "task-files"
    MINIO_SECURE: bool = False
    MAX_UPLOAD_MB: int = 25

    # JWT Security
    JWT_SECRET_KEY: str = "taskflow_super_secret_jwt_key_it4409_2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7


settings = Settings()


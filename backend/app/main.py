from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.auth import router as auth_router
from app.api.project_content import router as project_content_router
from app.api.tasks import router as tasks_router
from app.api.project_invitations import (
    invitation_router,
    router as project_invitation_router,
)
from app.api.project_permissions import router as project_permission_router

app = FastAPI(title=settings.PROJECT_NAME)

# Cấu hình CORS để Frontend (React/Vite) có thể gọi API
origins = [
    settings.FRONTEND_URL,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các router
app.include_router(auth_router, prefix="/api")
app.include_router(project_permission_router, prefix="/api")
app.include_router(project_invitation_router, prefix="/api")
app.include_router(invitation_router, prefix="/api")
app.include_router(project_content_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok"}

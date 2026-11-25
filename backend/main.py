"""Cadence NCC Operations Management Platform - Backend API Main Application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.database import Base, engine
from core.security import InvalidTokenError, TokenExpiredError
from modules.attendance.router import router as attendance_router
from modules.auth.router import router as auth_router
from modules.leave.router import router as leave_router
from modules.notices.router import router as notices_router
from modules.reports.router import router as reports_router
from modules.tasks.router import router as tasks_router
from realtime.websocket import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle events: ensure database schema initialized."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=f"{settings.app_name} NCC Platform",
    description="Unit-level NCC Operations Management Platform Backend",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(TokenExpiredError)
async def token_expired_handler(request: Request, exc: TokenExpiredError):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Token has expired. Please refresh your session."},
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(InvalidTokenError)
async def invalid_token_handler(request: Request, exc: InvalidTokenError):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": f"Invalid authentication token: {exc}"},
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint for container and operational monitors."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.app_env,
    }


# Include Routers
app.include_router(auth_router)
app.include_router(attendance_router)
app.include_router(leave_router)
app.include_router(notices_router)
app.include_router(tasks_router)
app.include_router(reports_router)
app.include_router(ws_router)

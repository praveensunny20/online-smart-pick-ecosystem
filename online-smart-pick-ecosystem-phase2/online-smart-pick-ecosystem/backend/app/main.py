"""
Online Smart Pick Ecosystem — Main FastAPI application.

Run locally:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Run in Docker:
    docker compose up
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import api_router
from app.core.config import settings
from app.main_limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown hooks.
    Put any one-time setup (like warming caches) here.
    """
    # Startup
    print(f"🚀 Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
    print(f"   API prefix: {settings.API_V1_PREFIX}")
    print(f"   Database:   {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    print(f"   Redis:      {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    print(f"   Data src:   {settings.DATA_PROVIDER}")
    print(f"   Email:      {'Resend' if settings.RESEND_API_KEY else 'console (set RESEND_API_KEY to enable)'}")
    yield
    # Shutdown
    print(f"👋 Shutting down {settings.APP_NAME}")


# Create the FastAPI instance
app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Multi-tenant SaaS marketing intelligence platform. "
        "Agencies manage multiple clients, each with multiple marketing platform "
        "connections. AI-powered Smart Picks, unified metrics, and automated reports."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# --- Rate limiting (slowapi) ---
# The Limiter instance itself lives in app.main_limiter so that app.api.auth
# (which needs to decorate individual routes) can import it without creating
# a circular import back to app.main.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# --- CORS middleware ---
# Allows the frontend (http://localhost:3000) to call the API.
# In production, set CORS_ORIGINS env var to only your real frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# --- Global exception handler ---
# Catches any unhandled exception and returns a clean JSON error.
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Fallback for anything not caught by FastAPI's built-in handlers."""
    # Re-raise HTTPException and RateLimitExceeded so their own handlers run
    # (FastAPI dispatches more specific handlers first, so we only hit this
    # path for truly unexpected errors).
    import traceback
    traceback.print_exc()

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.DEBUG else "Something went wrong",
        },
    )


# --- Mount API routers ---
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# --- Root route ---
@app.get("/", tags=["root"])
async def root():
    """Welcome page — also confirms the API is running."""
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs",
        "health": f"{settings.API_V1_PREFIX}/health",
        "status": "online",
    }

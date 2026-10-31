import logging
import os
import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Ensure backend root is always on sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

# Load environment variables from .env if present
load_dotenv(os.path.join(_current_dir, ".env"))

from core.config import settings
import rubric_config
from core.llm import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMMissingApiKeyError,
    LLMRateLimitError,
)
from core.database import init_db
from core.seb import SEBMiddleware
from routers.interview import router as interview_router
from routers.admin import router as admin_router
from routers.auth import router as auth_router, limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 0. Initialize database tables if they do not exist
    await init_db()

    # 1. Log SEB enforcement status on startup (key value never logged)
    _seb_log = logging.getLogger("seb")
    _key_set = bool(settings.SEB_CONFIG_KEY and settings.SEB_CONFIG_KEY.strip())
    if settings.DEV_SKIP_SEB:
        _seb_log.warning(
            "⚠️  SEB check DISABLED (DEV_SKIP_SEB=true) — Safe Exam Browser is NOT enforced. "
            "SEB_CONFIG_KEY set: %s",
            _key_set,
        )
    else:
        _seb_log.info("SEB check ENABLED | SEB_CONFIG_KEY set: %s", _key_set)

    # 2. Startup rubric config load validation
    rubric_config.validate_rubric_config()

    # 2. Loud startup validation for GROQ_API_KEY unless running in test mode
    is_testing = os.environ.get("TESTING", "").lower() == "true"
    api_key = os.environ.get("GROQ_API_KEY")

    if not is_testing and not api_key:
        raise RuntimeError(
            "GROQ_API_KEY environment variable is missing or empty. "
            "Please create a .env file at the project root containing GROQ_API_KEY=<your_groq_api_key> "
            "before starting the Conlatus backend."
        )

    yield


app = FastAPI(
    title="Conlatus AI Interview Platform — API",
    description="FastAPI stateless JWT authentication, audio interview loops, and admin suite",
    version="0.2.0",
    lifespan=lifespan,
)

# Rate Limiter setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Safe Exam Browser (SEB) verification middleware
app.add_middleware(SEBMiddleware)

# CORS middleware configuration (added after SEBMiddleware so it is outermost and 403s still carry CORS headers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self' ws: wss: http: https:;"
    )
    return response


# LLM Exception Handlers
@app.exception_handler(LLMAuthenticationError)
async def auth_error_handler(request: Request, exc: LLMAuthenticationError):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc)},
    )


@app.exception_handler(LLMRateLimitError)
async def rate_limit_error_handler(request: Request, exc: LLMRateLimitError):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": str(exc)},
    )


@app.exception_handler(LLMMissingApiKeyError)
async def missing_key_error_handler(request: Request, exc: LLMMissingApiKeyError):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )


@app.exception_handler(LLMAPIError)
async def api_error_handler(request: Request, exc: LLMAPIError):
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": str(exc)},
    )


from routers.admin_questions import router as admin_questions_router
from routers.reports import router as reports_router

# Include API Routers
app.include_router(auth_router)
app.include_router(interview_router)
app.include_router(admin_router)
app.include_router(admin_questions_router)
app.include_router(reports_router)


@app.get("/")
def root():
    return {
        "status": "ok",
        "app": "Conlatus API",
        "role": rubric_config.ROLE_TITLE,
    }


@app.get("/dev/dashboard", response_class=HTMLResponse)
def dev_dashboard():
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    with open(dashboard_path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/seb/config.seb")
def get_seb_config():
    """
    Serves ./seb/conlatus.seb with Content-Type application/octet-stream
    and Content-Disposition attachment.
    """
    search_paths = [
        os.path.abspath(os.path.join(os.getcwd(), "seb", "conlatus.seb")),
        os.path.abspath(os.path.join(_current_dir, "seb", "conlatus.seb")),
        os.path.abspath(os.path.join(os.path.dirname(_current_dir), "seb", "conlatus.seb")),
    ]

    target_path = None
    for p in search_paths:
        if os.path.isfile(p):
            target_path = p
            break

    if not target_path or not os.path.exists(target_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SEB configuration file './seb/conlatus.seb' not found on server.",
        )

    return FileResponse(
        path=target_path,
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="conlatus.seb"'},
        filename="conlatus.seb",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

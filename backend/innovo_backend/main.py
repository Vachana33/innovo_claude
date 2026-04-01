"""
innovo_backend — FastAPI application entry point.

Usage:
    uvicorn innovo_backend.main:app --reload          (dev)
    uvicorn innovo_backend.main:app --host 0.0.0.0   (prod)
"""
import os
import time
import uuid
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)

logger = logging.getLogger(__name__)

if os.getenv("DEBUG_ENV_LOG", "").lower() == "true":
    logger.info("ENV FILE USED: %s", ENV_PATH if ENV_PATH.exists() else "None (using system env)")
    logger.info("OPENAI KEY FOUND: %s", bool(os.getenv("OPENAI_API_KEY")))
    logger.info("JWT SECRET KEY FOUND: %s", bool(os.getenv("JWT_SECRET_KEY")))

if not os.getenv("JWT_SECRET_KEY"):
    raise RuntimeError("JWT_SECRET_KEY is required. Set it via environment variables.")

if not os.getenv("OPENAI_API_KEY"):
    logger.warning("OPENAI_API_KEY is not set. OpenAI features may not work.")

from fastapi import FastAPI, Request, status  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse, FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

from innovo_backend.shared.database import engine, Base  # noqa: E402
from innovo_backend.shared.posthog_client import init_posthog, shutdown_posthog, capture_event  # noqa: E402
from innovo_backend.shared.observability import set_request_id, reset_request_id, get_request_id  # noqa: E402

from innovo_backend.services.auth.router import router as auth_router  # noqa: E402
from innovo_backend.services.funding_programs.router import router as funding_programs_router  # noqa: E402
from innovo_backend.services.companies.router import router as companies_router  # noqa: E402
from innovo_backend.services.documents.router import router as documents_router  # noqa: E402
from innovo_backend.services.templates.router import router as templates_router  # noqa: E402
from innovo_backend.services.alte_vorhabensbeschreibung.router import router as alte_router  # noqa: E402
from innovo_backend.services.projects.router import router as projects_router  # noqa: E402
from innovo_backend.services.projects.chat_router import router as project_chat_router  # noqa: E402
from innovo_backend.services.knowledge_base.router import router as knowledge_base_router  # noqa: E402

from apscheduler.schedulers.background import BackgroundScheduler  # noqa: E402

# Create tables in SQLite dev mode only
parsed_url = urlparse(os.getenv("DATABASE_URL", "sqlite:///./innovo.db"))
is_sqlite = parsed_url.scheme == "sqlite" or "sqlite" in os.getenv("DATABASE_URL", "").lower()
if is_sqlite:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created (SQLite development mode)")
else:
    logger.info("Skipping automatic table creation (PostgreSQL - use Alembic migrations)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_posthog()

    from innovo_backend.services.knowledge_base.scraper import scrape_all_sources_task  # noqa: PLC0415

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        scrape_all_sources_task,
        trigger="cron",
        day_of_week="mon",
        hour=2,
        minute=0,
        id="weekly_funding_source_scrape",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("APScheduler started — weekly funding source scrape scheduled (Mon 02:00)")

    yield

    scheduler.shutdown(wait=False)
    shutdown_posthog()


app = FastAPI(title="Innovo Agent API", version="1.0.0", lifespan=lifespan)

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN")
cors_origins = (
    [FRONTEND_ORIGIN]
    if FRONTEND_ORIGIN
    else [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = uuid.uuid4().hex[:12]
    token = set_request_id(request_id)
    request.state.request_id = request_id

    start = time.monotonic()
    try:
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "request | request_id=%s method=%s path=%s status=%d duration_ms=%d",
            request_id, request.method, request.url.path, response.status_code, duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        capture_event(
            distinct_id="backend",
            event="request_completed",
            properties={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "request_error | request_id=%s method=%s path=%s duration_ms=%d error=%s",
            request_id, request.method, request.url.path, duration_ms, str(exc), exc_info=True,
        )
        raise
    finally:
        reset_request_id(token)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None) or get_request_id() or "none"
    logger.error(
        "unhandled_exception | request_id=%s path=%s error=%s",
        request_id, request.url.path, str(exc), exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


# Include all routers
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(funding_programs_router, tags=["funding-programs"])
app.include_router(companies_router, tags=["companies"])
app.include_router(documents_router, tags=["documents"])
app.include_router(templates_router, tags=["templates"])
app.include_router(alte_router, tags=["alte-vorhabensbeschreibung"])
app.include_router(projects_router)
app.include_router(project_chat_router)
app.include_router(knowledge_base_router, tags=["knowledge-base"])

# Static frontend serving (production)
STATIC_DIR = BASE_DIR / "static"

if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    if (STATIC_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    @app.get("/vite.svg")
    async def vite_svg():
        svg_path = STATIC_DIR / "vite.svg"
        if svg_path.exists():
            return FileResponse(svg_path)
        raise StarletteHTTPException(status_code=404)

    logger.info("Serving frontend static files from %s", STATIC_DIR)
else:
    logger.info("Frontend static files not found - running in API-only mode")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root(request: Request):
    if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
        return FileResponse(STATIC_DIR / "index.html")
    return {"message": "Innovo Agent API"}


@app.get("/{full_path:path}")
async def serve_spa(full_path: str, request: Request):
    if not (STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists()):
        raise StarletteHTTPException(status_code=404, detail="Not found")
    if full_path.startswith((
        "auth/", "funding-programs", "companies", "documents",
        "templates", "health", "assets/", "projects",
    )):
        raise StarletteHTTPException(status_code=404, detail="Not found")
    return FileResponse(STATIC_DIR / "index.html")

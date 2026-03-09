# Standard library imports
import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

# Third-party imports
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

# Conditionally load .env file if it exists (dev only)
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)

# Environment validation - fail early with clear errors
logger = logging.getLogger(__name__)

# Optional debug logging (only if DEBUG_ENV_LOG=true)
if os.getenv("DEBUG_ENV_LOG", "").lower() == "true":
    logger.info(f"ENV FILE USED: {ENV_PATH if ENV_PATH.exists() else 'None (using system env)'}")
    logger.info(f"OPENAI KEY FOUND: {bool(os.getenv('OPENAI_API_KEY'))}")
    logger.info(f"JWT SECRET KEY FOUND: {bool(os.getenv('JWT_SECRET_KEY'))}")

# JWT_SECRET_KEY is required (no fallback for security)
if not os.getenv("JWT_SECRET_KEY"):
    raise RuntimeError("JWT_SECRET_KEY is required. Set it via environment variables.")

# OPENAI_API_KEY is optional but recommended (warn only)
if not os.getenv("OPENAI_API_KEY"):
    logger.warning("OPENAI_API_KEY is not set. OpenAI features may not work.")

# DATABASE_URL is optional (SQLite fallback handled in database.py)
# Production (Render): DATABASE_URL must be set to PostgreSQL connection string
# Local development: Falls back to SQLite if DATABASE_URL is not set
# No validation needed here - database.py already handles SQLite fallback

# FastAPI and application imports
# Note: These imports are after environment setup to ensure .env is loaded first
from fastapi import FastAPI, Request, status  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse, FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402
from app.database import engine, Base  # noqa: E402
from app.routers import auth, funding_programs, companies, documents, templates, alte_vorhabensbeschreibung  # noqa: E402
from app.posthog_client import init_posthog, shutdown_posthog  # noqa: E402

# Create database tables
# Note: In production (PostgreSQL on Render), use Alembic migrations instead
# This create_all() is kept for local development convenience only
# For production: run "alembic upgrade head" after setting DATABASE_URL
# Only run create_all() in development (when DATABASE_URL is not set or is SQLite)
parsed_url = urlparse(os.getenv("DATABASE_URL", "sqlite:///./innovo.db"))
is_sqlite = parsed_url.scheme == "sqlite" or "sqlite" in os.getenv("DATABASE_URL", "").lower()
if is_sqlite:
    # Only create tables automatically in SQLite (local dev)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created (SQLite development mode)")
else:
    # In production (PostgreSQL), rely on Alembic migrations only
    logger.info("Skipping automatic table creation (PostgreSQL - use Alembic migrations)")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize and cleanly shut down PostHog."""
    init_posthog()
    yield
    shutdown_posthog()


app = FastAPI(title="Innovo Agent API", version="1.0.0", lifespan=lifespan)

# CORS configuration - environment-driven
# Production: Set FRONTEND_ORIGIN environment variable to your frontend URL (e.g., https://demo-innovo-frontend.onrender.com)
# Development: If FRONTEND_ORIGIN is not set, falls back to localhost origins for local development
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN")
if FRONTEND_ORIGIN:
    # Production: use single origin from environment variable
    cors_origins = [FRONTEND_ORIGIN]
else:
    # Development: default localhost origins for local development
    cors_origins = [
        "http://localhost:3000",
        "http://localhost:5173",  # Vite default port
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]

# Optional debug logging
if os.getenv("DEBUG_ENV_LOG", "").lower() == "true":
    logger.info(f"CORS ALLOWED ORIGINS: {cors_origins}")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers to ensure CORS headers are always present
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Ensure CORS headers are present on HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Ensure CORS headers are present on validation errors"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Ensure CORS headers are present on all exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(funding_programs.router, tags=["funding-programs"])
app.include_router(companies.router, tags=["companies"])
app.include_router(documents.router, tags=["documents"])
app.include_router(templates.router, tags=["templates"])
app.include_router(alte_vorhabensbeschreibung.router, tags=["alte-vorhabensbeschreibung"])

# Serve frontend static files if dist directory exists (for production deployment)
# Frontend dist directory should be copied to backend/static during Docker build
STATIC_DIR = BASE_DIR / "static"

# Check if static directory exists (copied from frontend/dist during Docker build)
if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    # Mount static files (JS, CSS, images, etc.) - must be before catch-all route
    if (STATIC_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")
    
    # Serve other static files (favicon, etc.)
    @app.get("/vite.svg")
    async def vite_svg():
        svg_path = STATIC_DIR / "vite.svg"
        if svg_path.exists():
            return FileResponse(svg_path)
        raise StarletteHTTPException(status_code=404)
    
    logger.info(f"Serving frontend static files from {STATIC_DIR}")
else:
    # Frontend not available - API-only mode
    logger.info("Frontend static files not found - running in API-only mode")

# Health check endpoint - must be before catch-all route
@app.get("/health")
async def health():
    """Simple health check endpoint for Render and monitoring services."""
    return {"status": "ok"}

# Root route - serve API info or frontend index.html
@app.get("/")
async def root(request: Request):
    # If frontend exists, serve it; otherwise return API info
    if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
        return FileResponse(STATIC_DIR / "index.html")
    return {"message": "Innovo Agent API"}

# Catch-all route for SPA: serve index.html for all non-API routes
# This must be LAST to avoid intercepting API routes
@app.get("/{full_path:path}")
async def serve_spa(full_path: str, request: Request):
    # Skip if frontend not available
    if not (STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists()):
        raise StarletteHTTPException(status_code=404, detail="Not found")
    
    # Don't serve index.html for API routes (these should have been handled by routers above)
    if full_path.startswith(("auth/", "funding-programs", "companies", "documents", "templates", "health", "assets/")):
        raise StarletteHTTPException(status_code=404, detail="Not found")
    
    # Serve index.html for all other routes (SPA routing)
    return FileResponse(STATIC_DIR / "index.html")


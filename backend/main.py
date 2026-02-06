"""Main FastAPI application for Program Mill."""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Create FastAPI app
app = FastAPI(
    title="Program Mill",
    description="Rigorous program verification through externalized formal reasoning",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize application on startup."""
    logger.info(
        "program_mill_starting",
        version="0.1.0",
        log_level=settings.log_level,
        database_path=settings.database_path,
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Clean up on shutdown."""
    logger.info("program_mill_shutting_down")


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": "Program Mill",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


# Future route imports will go here
# from backend.api import routes_analysis
# app.include_router(routes_analysis.router, prefix="/api/v1", tags=["analysis"])

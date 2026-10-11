"""
Main FastAPI entry point for the Telesales Intelligence System.
Headless operational and ingestion API with zero frontend or HTML templates.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict
from fastapi import FastAPI, status
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from app.config import settings
from app.db.session import engine
from app.db.repository import DatabaseRepository
from app.api.calls import router as calls_router, ops_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager: ensures database schema, lookup codes, and reporting views are initialized.
    """
    try:
        DatabaseRepository.initialize_schema_and_views(engine)
    except Exception as exc:
        print(f"Warning: Database initialization encountered an issue on startup: {exc}")
    yield


app = FastAPI(
    title="Telesales Intelligence System API",
    description="Headless ingestion, analysis, and validation pipeline for Jordanian Arabic telesales calls.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None
)

# Register headless routers
app.include_router(calls_router)
app.include_router(ops_router)


@app.get(
    "/",
    response_class=HTMLResponse,
    include_in_schema=False
)
@app.get(
    "/dashboard",
    tags=["Reporting"],
    response_class=HTMLResponse,
    summary="Interactive Power BI Dashboard Viewer"
)
def get_powerbi_dashboard_view():
    """Serves the interactive Power BI two-page report viewer."""
    html_path = Path(__file__).resolve().parent.parent / "powerbi" / "dashboard.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Dashboard HTML not found</h1>", status_code=404)


@app.get(
    "/health",
    tags=["System"],
    status_code=status.HTTP_200_OK,
    summary="Health check and database connectivity verification"
)
def health_check() -> Dict:
    db_healthy = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            db_healthy = True
    except Exception:
        db_healthy = False

    return {
        "status": "online" if db_healthy else "degraded",
        "database_connected": db_healthy,
        "cohere_model": settings.COHERE_MODEL,
        "is_mock_llm": settings.is_mock_llm,
        "coaching_language": settings.COACHING_LANGUAGE,
        "powerbi_refresh_enabled": settings.POWERBI_REFRESH_ENABLED
    }

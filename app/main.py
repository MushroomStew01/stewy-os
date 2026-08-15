from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import __version__
from .config import get_settings
from .database import init_db
from .security import require_access
from .services.activity import recent_activity
from .services.dashboard import DashboardService

BASE_DIR = Path(__file__).resolve().parent
settings = get_settings()
dashboard_service = DashboardService(settings)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/api/dashboard", dependencies=[Depends(require_access)])
async def api_dashboard(force: Annotated[bool, Query()] = False) -> dict[str, object]:
    return await dashboard_service.get_dashboard(force=force)


@app.get("/api/activity", dependencies=[Depends(require_access)])
def api_activity(limit: Annotated[int, Query(ge=1, le=100)] = 20) -> list[dict[str, object]]:
    return recent_activity(limit=limit)


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_access)])
async def dashboard(request: Request) -> HTMLResponse:
    payload = await dashboard_service.get_dashboard()
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "app_name": settings.app_name,
            "payload": payload,
            "refresh_seconds": settings.app_refresh_seconds,
        },
    )

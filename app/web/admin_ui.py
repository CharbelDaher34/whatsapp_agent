"""Admin HTML panel.

A tiny static-render shell that reuses the existing JSON ``/admin/*``
endpoints. The HTML is templated, the live data is fetched client-side with
the admin key the operator pastes in once and we cache in localStorage.

Auth model (intentionally minimal): the panel is a single page; the operator
is responsible for keeping ADMIN_API_KEY secret. For tighter setups, put this
behind an SSO reverse-proxy.
"""
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings


router = APIRouter(tags=["admin-ui"])
_THIS_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(_THIS_DIR / "templates"))


@router.get("/admin-ui", response_class=HTMLResponse)
async def admin_ui(request: Request):
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "app_name": settings.APP_NAME,
            "user": None,
            "active": "admin",
            "billing_mode": settings.billing_mode,
        },
    )

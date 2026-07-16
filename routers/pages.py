"""Routes HTML (Jinja2) — interface web FastAPI."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["Pages"])


def _render(request: Request, name: str) -> HTMLResponse:
    return templates.TemplateResponse(request, name)


@router.get("/", response_class=HTMLResponse)
async def page_login(request: Request):
    return _render(request, "login.html")


@router.get("/register", response_class=HTMLResponse)
async def page_register(request: Request):
    return _render(request, "register.html")


@router.get("/forgot-password", response_class=HTMLResponse)
async def page_forgot_password(request: Request):
    return _render(request, "forgot_password.html")


@router.get("/reset-password", response_class=HTMLResponse)
async def page_reset_password(request: Request):
    return _render(request, "reset_password.html")


@router.get("/dashboard", response_class=HTMLResponse)
async def page_dashboard(request: Request):
    return _render(request, "dashboard.html")


@router.get("/transactions", response_class=HTMLResponse)
async def page_transactions(request: Request):
    return _render(request, "transactions.html")


@router.get("/fraudes", response_class=HTMLResponse)
async def page_fraudes(request: Request):
    return _render(request, "fraudes.html")


@router.get("/token", response_class=HTMLResponse)
async def page_token(request: Request):
    return _render(request, "token.html")


@router.get("/optimisation", response_class=HTMLResponse)
async def page_optimisation(request: Request):
    return _render(request, "optimisation.html")


@router.get("/superadmin", response_class=HTMLResponse)
async def page_superadmin(request: Request):
    return _render(request, "superadmin.html")

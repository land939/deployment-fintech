"""Routes HTML (Jinja2) — interface web FastAPI."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter(tags=["Pages"])

_PAGES = (
    ("/", "login.html"),
    ("/register", "register.html"),
    ("/forgot-password", "forgot_password.html"),
    ("/reset-password", "reset_password.html"),
    ("/dashboard", "dashboard.html"),
    ("/transactions", "transactions.html"),
    ("/fraudes", "fraudes.html"),
    ("/token", "token.html"),
    ("/optimisation", "optimisation.html"),
    ("/superadmin", "superadmin.html"),
)


def _make_page(name: str):
    async def handler(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, name)

    handler.__name__ = f"page_{name.removesuffix('.html')}"
    return handler


for _path, _tpl in _PAGES:
    router.add_api_route(_path, _make_page(_tpl), methods=["GET"], response_class=HTMLResponse)

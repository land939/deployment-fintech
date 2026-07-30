"""Routes HTML (Jinja2) — interface web FastAPI."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter(tags=["Pages"])

# L'interface utilisateur tient sur une seule page (app.html) — les
# anciennes routes /transactions, /fraudes… continuent de la servir pour
# ne casser aucun lien ou favori.
_PAGES = (
    ("/", "login.html"),
    ("/register", "register.html"),
    ("/forgot-password", "forgot_password.html"),
    ("/reset-password", "reset_password.html"),
    ("/dashboard", "app.html"),
    ("/transactions", "app.html"),
    ("/fraudes", "app.html"),
    ("/token", "app.html"),
    ("/optimisation", "app.html"),
    ("/superadmin", "superadmin.html"),
)


def _make_page(path: str, name: str):
    async def handler(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, name)

    # Nom dérivé du chemin (unique) : plusieurs routes servent app.html
    handler.__name__ = f"page_{path.strip('/').replace('-', '_') or 'login'}"
    return handler


for _path, _tpl in _PAGES:
    router.add_api_route(
        _path, _make_page(_path, _tpl), methods=["GET"], response_class=HTMLResponse
    )

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"


def _asset_version() -> str:
    """Newest change of any static file: appended to CSS/JS links, so after a
    deploy browsers (and Cloudflare) fetch the new files instead of cached ones."""
    newest = max(
        (p.stat().st_mtime for p in STATIC_DIR.rglob("*") if p.is_file()), default=0
    )
    return str(int(newest))


templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))
templates.env.globals["asset_version"] = _asset_version()

# HTML shells only: the data comes from the API with the user's token, which
# also enforces who may see what.
router = APIRouter(include_in_schema=False)


@router.get("/")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.get("/app/haslo")
async def password_page(request: Request):
    return templates.TemplateResponse(request, "password.html")


@router.get("/app/pulpit")
async def dashboard_page(request: Request):
    return templates.TemplateResponse(request, "pulpit.html")


@router.get("/app/ruchy")
async def movements_page(request: Request):
    return templates.TemplateResponse(request, "ruchy.html")


@router.get("/app/nowa-operacja")
async def new_movement_page(request: Request):
    return templates.TemplateResponse(request, "nowa_operacja.html")


@router.get("/app/import")
async def import_page(request: Request):
    return templates.TemplateResponse(request, "import.html")


@router.get("/app/inwentaryzacja")
async def inventory_page(request: Request):
    return templates.TemplateResponse(request, "inwentaryzacja.html")


@router.get("/app/ustawienia")
async def settings_page(request: Request):
    return templates.TemplateResponse(request, "ustawienia.html")


@router.get("/app/audyt")
async def audit_page(request: Request):
    return templates.TemplateResponse(request, "audyt.html")


@router.get("/app/bilans")
async def daily_balance_page(request: Request):
    return templates.TemplateResponse(request, "bilans.html")

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.templating import _TemplateResponse
from jinja2 import Environment, FileSystemLoader

router = APIRouter(tags=["pages"])

_env = Environment(
    loader=FileSystemLoader("app/web/templates"),
    autoescape=True,
)


def render_template(name: str, request: Request, **kwargs) -> _TemplateResponse:
    template = _env.get_template(name)
    return _TemplateResponse(
        template,
        {"request": request, **kwargs},
    )


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return render_template("index.html", request)


@router.get("/documents", response_class=HTMLResponse)
async def documents_page(request: Request):
    return render_template("documents.html", request)


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return render_template("admin.html", request)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return render_template("login.html", request, error=error)

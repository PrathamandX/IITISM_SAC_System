from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parents[2] / "frontend" / "templates")

router = APIRouter(include_in_schema=False)


@router.get("/")
def login_page(request: Request):
    return TEMPLATES.TemplateResponse(request, "login.html")


@router.get("/dashboard")
def dashboard(request: Request):
    # Data is loaded client-side with the JWT; the page itself holds nothing sensitive.
    return TEMPLATES.TemplateResponse(request, "dashboard.html")

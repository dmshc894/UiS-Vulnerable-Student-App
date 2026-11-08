import traceback
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.auth import get_user_from_session
from app.config import APP_ENV
from .safe_fetch import fetch_public_resource, RessourceFetchError

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/status", response_class=HTMLResponse)
def status(request: Request):
    user = get_user_from_session(request)
    return templates.TemplateResponse(
        "status.html",
        {"request": request, "user": user, "env": APP_ENV, "python": "3.11", "service": "backend"},
    )


@router.get("/resources/import", response_class=HTMLResponse)
def import_resource_get(request: Request, url: str = ""):
    user = get_user_from_session(request)
    body = ""
    error = ""
    status_code = 200
    if url:
        try:
            body = fetch_public_resource(url)
        except RessourceFetchError as exc:
            error = str(exc)
            status_code = 400
    return templates.TemplateResponse(
        "resource_import.html",
        {"request": request, "user": user, "body": body, "url": url, "error": error},
        status_code = status_code,
    )


@router.post("/resources/import", response_class=HTMLResponse)
def import_resource_post(request: Request, url: str = Form(...)):
    return import_resource_get(request, url)


@router.get("/error", response_class=HTMLResponse)
def trigger_error(request: Request):
    try:
        x = 1 / 0
        return {"x": x}
    except Exception:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "details": traceback.format_exc()},
            status_code=500,
        )

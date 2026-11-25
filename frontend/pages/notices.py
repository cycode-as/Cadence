"""Thin FastAPI router for notices."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from frontend.pages.common import render_page

router = APIRouter()

@router.get("/notices", response_class=HTMLResponse)
def notices_inbox(request: Request) -> HTMLResponse:
    return render_page(request, "notices/inbox.html", "notices/inbox.json")

@router.get("/notices/new", response_class=HTMLResponse)
def notices_create(request: Request) -> HTMLResponse:
    return render_page(request, "notices/create.html", "notices/create.json")

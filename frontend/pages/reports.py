"""Thin FastAPI router for reports."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from frontend.pages.common import render_page

router = APIRouter()

@router.get("/reports", response_class=HTMLResponse)
def reports_index(request: Request) -> HTMLResponse:
    return render_page(request, "reports/index.html", "reports/index.json")

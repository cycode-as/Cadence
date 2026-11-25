"""Thin FastAPI router for roster, audit, and admin pages."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from frontend.pages.common import render_page

router = APIRouter()

@router.get("/admin/roster", response_class=HTMLResponse)
def roster(request: Request) -> HTMLResponse:
    return render_page(request, "admin/roster.html", "admin/roster.json")

@router.get("/admin/import", response_class=HTMLResponse)
def csv_upload(request: Request) -> HTMLResponse:
    return render_page(request, "admin/csv_upload.html", "admin/csv_upload.json")

@router.get("/admin/squads", response_class=HTMLResponse)
def squad_board(request: Request) -> HTMLResponse:
    return render_page(request, "admin/squad_board.html", "admin/squad_board.json")

@router.get("/admin/audit", response_class=HTMLResponse)
def audit_log(request: Request) -> HTMLResponse:
    return render_page(request, "admin/audit_log.html", "admin/audit_log.json")

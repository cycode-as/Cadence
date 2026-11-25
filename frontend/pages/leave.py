"""Thin FastAPI router for leave pages."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from frontend.pages.common import render_page

router = APIRouter()

@router.get("/leave/apply", response_class=HTMLResponse)
def leave_apply(request: Request) -> HTMLResponse:
    return render_page(request, "leave/apply.html", "leave/apply.json")

@router.get("/leave", response_class=HTMLResponse)
def leave_queue(request: Request) -> HTMLResponse:
    return render_page(request, "leave/queue.html", "leave/queue.json")

@router.get("/leave/{leave_id}", response_class=HTMLResponse)
def leave_detail(request: Request, leave_id: str) -> HTMLResponse:
    return render_page(request, "leave/detail.html", "leave/detail.json")

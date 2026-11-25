"""Thin FastAPI router for exam resources and guest home."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from frontend.pages.common import render_page

router = APIRouter()

@router.get("/exam-resources", response_class=HTMLResponse)
def exam_resources(request: Request) -> HTMLResponse:
    return render_page(request, "exam_resources/list.html", "exam_resources/list.json")

@router.get("/guest", response_class=HTMLResponse)
def guest_home(request: Request) -> HTMLResponse:
    return render_page(request, "guest/home.html", "guest/home.json")

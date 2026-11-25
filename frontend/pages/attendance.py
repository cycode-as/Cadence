"""Thin FastAPI router for attendance pages."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from frontend.pages.common import render_page

router = APIRouter()

@router.get("/attendance/sheet/{sheet_id}", response_class=HTMLResponse)
def attendance_sheet(request: Request, sheet_id: str, view: str = "marking") -> HTMLResponse:
    if view == "approval":
        return render_page(request, "attendance/approval.html", "attendance/approval.json")
    return render_page(request, "attendance/marking_sheet.html", "attendance/marking_sheet.json")

@router.get("/attendance/review", response_class=HTMLResponse)
def attendance_review(request: Request) -> HTMLResponse:
    return render_page(request, "attendance/review_list.html", "attendance/review_list.json")

@router.get("/attendance/history", response_class=HTMLResponse)
def attendance_history(request: Request) -> HTMLResponse:
    return render_page(request, "attendance/history.html", "attendance/history.json")

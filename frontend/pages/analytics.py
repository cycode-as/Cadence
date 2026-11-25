"""Analytics drill-down endpoints."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from frontend.pages.common import render_page

router = APIRouter()

@router.get("/api/analytics/attendance", response_class=JSONResponse)
def analytics_attendance(request: Request, level: str = "battalion", scope_id: str = None) -> JSONResponse:
    # Mock drill-down data
    return JSONResponse({
        "labels": ["Alpha", "Bravo", "Charlie"],
        "datasets": [{"label": "Attendance %", "data": [92, 88, 95]}],
        "drill": {"level": level, "next_level": "contingent", "ids": ["cont-1", "cont-2", "cont-3"]}
    })

@router.get("/api/analytics/drill-table", response_class=HTMLResponse)
def analytics_drill_table(request: Request, level: str = "battalion", scope_id: str = None) -> HTMLResponse:
    return render_page(request, "fragments/analytics/drill_table.html", extra={"level": level, "scope_id": scope_id})

"""Thin FastAPI router for CADENCE role dashboards (no DB access)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from frontend.pages.common import (
    ROLE_DASHBOARD_MAP,
    build_base_context,
    render_page,
)

router = APIRouter()

ROLE_FIXTURE_MAP = {
    "CADET": "dashboards/cadet.json",
    "CADET_LEADER": "dashboards/cadet_leader.json",
    "JUO": "dashboards/juo.json",
    "ANO": "dashboards/ano.json",
    "CO": "dashboards/co.json",
}


@router.get("/dashboard")
def dashboard_redirect(request: Request) -> RedirectResponse:
    """Redirect authenticated users to their role-specific dashboard."""
    ctx, role, should_persist = build_base_context(request)
    user_role = (ctx.get("user") or {}).get("role", role)
    target = ROLE_DASHBOARD_MAP.get(user_role, "/login")
    response = RedirectResponse(url=target, status_code=302)
    if should_persist:
        response.set_cookie("dev_role", role, httponly=False, samesite="lax")
    return response


@router.get("/dashboard/cadet", response_class=HTMLResponse)
def dashboard_cadet(request: Request) -> HTMLResponse:
    return render_page(request, "dashboards/cadet.html", "dashboards/cadet.json")


@router.get("/dashboard/leader", response_class=HTMLResponse)
def dashboard_leader(request: Request) -> HTMLResponse:
    return render_page(request, "dashboards/cadet_leader.html", "dashboards/cadet_leader.json")


@router.get("/dashboard/juo", response_class=HTMLResponse)
def dashboard_juo(request: Request) -> HTMLResponse:
    return render_page(request, "dashboards/juo.html", "dashboards/juo.json")


@router.get("/dashboard/ano", response_class=HTMLResponse)
def dashboard_ano(request: Request) -> HTMLResponse:
    return render_page(request, "dashboards/ano.html", "dashboards/ano.json")


@router.get("/dashboard/co", response_class=HTMLResponse)
def dashboard_co(request: Request) -> HTMLResponse:
    return render_page(request, "dashboards/co.html", "dashboards/co.json")


@router.get("/fragments/dashboard/cards", response_class=HTMLResponse)
def fragment_dashboard_cards(request: Request) -> HTMLResponse:
    """HTMX fragment returning the stat-cards grid for the active role."""
    ctx, role, _ = build_base_context(request)
    user_role = (ctx.get("user") or {}).get("role", role)
    fixture = ROLE_FIXTURE_MAP.get(user_role, "dashboards/cadet_leader.json")
    return render_page(request, "fragments/dashboard_cards.html", fixture)

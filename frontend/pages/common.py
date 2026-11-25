"""Shared template, formatting, and fixture helpers for frontend routers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

FRONTEND_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"
FIXTURES_DIR = FRONTEND_DIR / "fixtures" / "mock_context"

VALID_ROLES = {"CADET", "CADET_LEADER", "JUO", "ANO", "CO", "GUEST"}
ROLE_DASHBOARD_MAP = {
    "CADET": "/dashboard/cadet",
    "CADET_LEADER": "/dashboard/leader",
    "JUO": "/dashboard/juo",
    "ANO": "/dashboard/ano",
    "CO": "/dashboard/co",
    "GUEST": "/",
}
IST_ZONE = ZoneInfo("Asia/Kolkata")


def format_ist(value: str | None) -> str:
    """Convert an ISO-8601 UTC timestamp string to IST display format."""
    if not value:
        return "—"
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ist_dt = dt.astimezone(IST_ZONE)
        return ist_dt.strftime("%d %b %Y, %I:%M %p IST")
    except ValueError:
        return value


templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["format_ist"] = format_ist

# Shared mutable dev state for live WS simulation delta
dev_bell_delta = {"unread_notices": 0, "pending_actions": 0}


def load_fixture(relative_path: str) -> dict[str, Any]:
    """Load a mock JSON context fixture from fixtures/mock_context/."""
    target = FIXTURES_DIR / relative_path
    with target.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def resolve_dev_role(request: Request) -> tuple[str, bool]:
    """Determine active dev role from ?role= query param or dev_role cookie."""
    q_role = request.query_params.get("role", "").upper()
    if q_role in VALID_ROLES:
        return q_role, True
    c_role = request.cookies.get("dev_role", "CADET_LEADER").upper()
    if c_role in VALID_ROLES:
        return c_role, False
    return "CADET_LEADER", False


def build_base_context(request: Request) -> tuple[dict[str, Any], str, bool]:
    """Build base template context using injected provider or mock fixtures."""
    provider = getattr(request.app.state, "context_provider", None)
    if callable(provider):
        ctx = provider(request)
        role = (ctx.get("user") or {}).get("role", "GUEST")
        return ctx, role, False

    shared = load_fixture("_shared.json")
    role, should_persist = resolve_dev_role(request)
    role_data = shared["roles"][role]
    bell = {
        "unread_notices": role_data["bell"]["unread_notices"] + dev_bell_delta["unread_notices"],
        "pending_actions": role_data["bell"]["pending_actions"] + dev_bell_delta["pending_actions"],
    }
    ctx = {
        "request": request,
        "user": role_data["user"],
        "nav_items": role_data["nav_items"],
        "bell": bell,
        "csrf_token": shared["csrf_token"],
        "current_path": request.url.path,
        "dev_mode": True,
        "current_dev_role": role,
    }
    return ctx, role, should_persist


def render_page(
    request: Request,
    template_name: str,
    fixture_name: str | None = None,
    extra: dict[str, Any] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Render a Jinja2 template with shared context and optional fixture/extras."""
    ctx, role, should_persist = build_base_context(request)
    if fixture_name:
        ctx.update(load_fixture(fixture_name))
    if extra:
        ctx.update(extra)
    response = templates.TemplateResponse(template_name, ctx, status_code=status_code)
    if should_persist:
        response.set_cookie("dev_role", role, httponly=False, samesite="lax")
    return response

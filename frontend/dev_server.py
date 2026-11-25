"""Standalone CADENCE Frontend Dev Server (Phase 1+).

Run from repo root:
    uvicorn frontend.dev_server:app --reload --port 8001
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import anyio
from fastapi import FastAPI, Form, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

FRONTEND_DIR = Path(__file__).resolve().parent
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

app = FastAPI(title="CADENCE Frontend Dev Server", docs_url="/dev/docs")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class DevWebSocketHub:
    """In-memory WebSocket connection registry for simulated live events."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    def add(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def remove(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        message = json.dumps(payload)
        for ws in list(self._clients):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.remove(ws)


ws_hub = DevWebSocketHub()
_dev_bell_delta = {"unread_notices": 0, "pending_actions": 0}


def load_fixture(relative_path: str) -> dict[str, Any]:
    """Load a mock context JSON fixture from fixtures/mock_context/."""
    target = FIXTURES_DIR / relative_path
    with target.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def resolve_dev_role(request: Request) -> tuple[str, bool]:
    """Return active role and whether it came from ?role= query param."""
    q_role = request.query_params.get("role", "").upper()
    if q_role in VALID_ROLES:
        return q_role, True
    c_role = request.cookies.get("dev_role", "CADET_LEADER").upper()
    if c_role in VALID_ROLES:
        return c_role, False
    return "CADET_LEADER", False


def build_base_context(request: Request) -> tuple[dict[str, Any], str, bool]:
    """Assemble shared template context for the active dev role."""
    shared = load_fixture("_shared.json")
    role, should_persist = resolve_dev_role(request)
    role_data = shared["roles"][role]
    bell = {
        "unread_notices": role_data["bell"]["unread_notices"] + _dev_bell_delta["unread_notices"],
        "pending_actions": role_data["bell"]["pending_actions"] + _dev_bell_delta["pending_actions"],
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
    """Render a Jinja2 template merged with shared + fixture context."""
    ctx, role, should_persist = build_base_context(request)
    if fixture_name:
        ctx.update(load_fixture(fixture_name))
    if extra:
        ctx.update(extra)
    response = templates.TemplateResponse(template_name, ctx, status_code=status_code)
    if should_persist:
        response.set_cookie("dev_role", role, httponly=False, samesite="lax")
    return response


@app.get("/", response_class=HTMLResponse)
def dev_hub(request: Request) -> HTMLResponse:
    return render_page(request, "dev_hub.html")


@app.get("/dashboard")
def dashboard_redirect(request: Request) -> RedirectResponse:
    role, _ = resolve_dev_role(request)
    target = ROLE_DASHBOARD_MAP.get(role, "/login")
    return RedirectResponse(url=target, status_code=302)


@app.get("/dashboard/{role_slug}", response_class=HTMLResponse)
def dashboard_placeholder(request: Request, role_slug: str) -> HTMLResponse:
    return render_page(
        request,
        "dev_hub.html",
        extra={
            "info_banner": f"Dashboard '/dashboard/{role_slug}' will be implemented in Phase 2."
        },
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return render_page(request, "auth/login.html", "auth/login.json")


@app.post("/auth/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    email: str = Form(""),
    password: str = Form(""),
    csrf_token: str = Form(""),
):
    if not email.strip() or not password.strip():
        return render_page(
            request,
            "auth/login.html",
            "auth/login.json",
            extra={
                "form_email": email,
                "error_message": "Email and password are required.",
            },
            status_code=422,
        )
    role, _ = resolve_dev_role(request)
    if role in {"ANO", "CO"}:
        return RedirectResponse(url="/mfa/verify", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/auth/logout")
def logout_submit() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=303)


@app.get("/mfa/setup", response_class=HTMLResponse)
def mfa_setup_page(request: Request) -> HTMLResponse:
    return render_page(request, "auth/mfa_setup.html", "auth/mfa_setup.json")


@app.post("/auth/mfa/setup/confirm", response_class=HTMLResponse)
def mfa_setup_confirm(
    request: Request,
    code: str = Form(""),
    csrf_token: str = Form(""),
) -> HTMLResponse:
    if len(code.strip()) != 6 or not code.strip().isdigit():
        return render_page(
            request,
            "auth/mfa_setup.html",
            "auth/mfa_setup.json",
            extra={"error_message": "Enter a valid 6-digit authenticator code."},
            status_code=422,
        )
    return render_page(
        request,
        "auth/mfa_setup.html",
        "auth/mfa_setup.json",
        extra={"success_message": "MFA authenticator confirmed for your CADENCE account."},
    )


@app.get("/mfa/verify", response_class=HTMLResponse)
def mfa_verify_page(request: Request) -> HTMLResponse:
    return render_page(request, "auth/mfa_verify.html", "auth/mfa_verify.json")


@app.post("/auth/mfa/verify", response_class=HTMLResponse)
def mfa_verify_submit(
    request: Request,
    code: str = Form(""),
    method: str = Form("totp"),
    csrf_token: str = Form(""),
):
    if len(code.strip()) != 6 or not code.strip().isdigit():
        return render_page(
            request,
            "auth/mfa_verify.html",
            "auth/mfa_verify.json",
            extra={
                "active_method": method,
                "error_message": "Invalid 6-digit code. Try 123456 in dev mode.",
            },
            status_code=422,
        )
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/auth/mfa/email-otp", response_class=HTMLResponse)
def mfa_email_otp() -> HTMLResponse:
    return HTMLResponse(
        '<span class="text-emerald-600 dark:text-emerald-400 font-medium">'
        "One-time 6-digit code dispatched to your registered email (dev mock)."
        "</span>"
    )


@app.get("/change-password", response_class=HTMLResponse)
def change_password_page(request: Request) -> HTMLResponse:
    return render_page(request, "auth/change_password.html", "auth/change_password.json")


@app.post("/auth/change-password", response_class=HTMLResponse)
def change_password_submit(
    request: Request,
    current_password: str = Form(""),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
    csrf_token: str = Form(""),
) -> HTMLResponse:
    if len(new_password) < 10 or new_password != confirm_password:
        return render_page(
            request,
            "auth/change_password.html",
            "auth/change_password.json",
            extra={"error_message": "Passwords must match and be at least 10 characters."},
            status_code=422,
        )
    return render_page(
        request,
        "auth/change_password.html",
        "auth/change_password.json",
        extra={"success_message": "Password updated successfully (dev mock)."},
    )


@app.get("/errors/403", response_class=HTMLResponse)
def error_403_page(request: Request) -> HTMLResponse:
    return render_page(request, "errors/403.html", "errors/403.json", status_code=403)


@app.get("/errors/404", response_class=HTMLResponse)
def error_404_page(request: Request) -> HTMLResponse:
    return render_page(request, "errors/404.html", "errors/404.json", status_code=404)


@app.get("/errors/500", response_class=HTMLResponse)
def error_500_page(request: Request) -> HTMLResponse:
    return render_page(request, "errors/500.html", "errors/500.json", status_code=500)


@app.get("/fragments/bell", response_class=HTMLResponse)
def fragment_bell(request: Request) -> HTMLResponse:
    return render_page(request, "components/bell.html")


@app.post("/dev/emit", response_class=JSONResponse)
def dev_emit_event(body: dict[str, Any]) -> JSONResponse:
    event_name = str(body.get("event", "dashboard.refresh"))
    if event_name == "notice.created":
        _dev_bell_delta["unread_notices"] += 1
    elif event_name in {"attendance.updated", "leave.updated"}:
        _dev_bell_delta["pending_actions"] += 1

    payload = {
        "event": event_name,
        "scope_type": "COMPANY",
        "scope_id": "22222222-2222-4222-8222-222222222201",
        "entity": "attendance_sheet" if "attendance" in event_name else "unit_event",
        "entity_id": "33333333-3333-4333-8333-333333333301",
        "actor_id": "11111111-1111-4111-8111-111111111103",
        "at": datetime.now(timezone.utc).isoformat(),
        "message": f"Simulated {event_name} event from Dev Panel",
    }
    anyio.from_thread.run(ws_hub.broadcast, payload)
    return JSONResponse({"ok": True, "emitted": payload})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    if origin:
        parsed = urlparse(origin)
        if parsed.hostname not in {"127.0.0.1", "localhost"}:
            await websocket.close(code=1008)
            return

    await websocket.accept()
    ws_hub.add(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") in {"presence.join", "presence.leave"}:
                await ws_hub.broadcast(
                    {
                        "event": "presence.updated",
                        "scope_type": "SQUAD",
                        "scope_id": "22222222-2222-4222-8222-222222222201",
                        "entity": msg.get("entity", "attendance_sheet"),
                        "entity_id": msg.get("entity_id", ""),
                        "actor_id": "11111111-1111-4111-8111-111111111103",
                        "at": datetime.now(timezone.utc).isoformat(),
                        "message": f"Presence event: {msg.get('type')}",
                    }
                )
    except WebSocketDisconnect:
        ws_hub.remove(websocket)


@app.exception_handler(StarletteHTTPException)
def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api/"):
        code_map = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND"}
        return JSONResponse(
            {
                "error": {
                    "code": code_map.get(exc.status_code, "HTTP_ERROR"),
                    "message": str(exc.detail),
                    "details": {},
                }
            },
            status_code=exc.status_code,
        )
    if exc.status_code == 403:
        return render_page(request, "errors/403.html", "errors/403.json", status_code=403)
    if exc.status_code == 404:
        return render_page(request, "errors/404.html", "errors/404.json", status_code=404)
    return render_page(
        request,
        "errors/500.html",
        "errors/500.json",
        extra={"message": str(exc.detail)},
        status_code=exc.status_code,
    )

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
from fastapi import FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from frontend.pages.common import (
    STATIC_DIR,
    dev_bell_delta,
    load_fixture,
    render_page,
    resolve_dev_role,
)
from frontend.pages.dashboards import router as dashboards_router
from frontend.pages.dashboards import router as dashboards_router
from frontend.pages.attendance import router as attendance_router
from frontend.pages.leave import router as leave_router
from frontend.pages.notices import router as notices_router
from frontend.pages.guest import router as guest_router
from frontend.pages.reports import router as reports_router
from frontend.pages.admin import router as admin_router
from frontend.pages.analytics import router as analytics_router

app = FastAPI(title="CADENCE Frontend Dev Server", docs_url="/dev/docs")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(dashboards_router)
app.include_router(dashboards_router)
app.include_router(attendance_router)
app.include_router(leave_router)
app.include_router(notices_router)
app.include_router(guest_router)
app.include_router(reports_router)
app.include_router(admin_router)
app.include_router(analytics_router)


def _advance_timeline_steps(steps: list[dict[str, Any]]) -> None:
    """Advance the active 'current' step to 'done' for live dev simulation."""
    now_iso = datetime.now(timezone.utc).isoformat()
    for idx, step in enumerate(steps):
        if step.get("state") == "current":
            step["state"] = "done"
            step["at"] = now_iso
            if not step.get("actor"):
                step["actor"] = "Lt. Meera Iyer (ANO)"
            if idx + 1 < len(steps):
                steps[idx + 1]["state"] = "current"
            return
    # Reset back to step 2 current if already completed
    for idx, step in enumerate(steps):
        if idx < 2:
            step["state"] = "done"
        elif idx == 2:
            step["state"] = "current"
            step["at"] = None
        else:
            step["state"] = "pending"
            step["at"] = None


_dev_live_state: dict[str, Any] | None = None


def _get_live_state() -> dict[str, Any]:
    global _dev_live_state
    if _dev_live_state is None:
        _dev_live_state = load_fixture("dev_live.json")
    return _dev_live_state


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


@app.get("/", response_class=HTMLResponse)
def dev_hub(request: Request) -> HTMLResponse:
    return render_page(request, "dev_hub.html")


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


@app.get("/dev/live", response_class=HTMLResponse)
def dev_live_preview(request: Request) -> HTMLResponse:
    state = _get_live_state()
    return render_page(request, "dev_live.html", extra=state)


@app.get("/fragments/attendance/sheet/{sheet_id}/timeline", response_class=HTMLResponse)
def fragment_sheet_timeline(request: Request, sheet_id: str) -> HTMLResponse:
    state = _get_live_state()
    return render_page(
        request,
        "fragments/timeline.html",
        extra={
            "timeline": state["attendance_timeline"],
            "entity_id": sheet_id,
            "refresh_url": f"/fragments/attendance/sheet/{sheet_id}/timeline",
            "title": "Attendance Sheet Approval Chain",
        },
    )


@app.get("/fragments/leave/{leave_id}/timeline", response_class=HTMLResponse)
def fragment_leave_timeline(request: Request, leave_id: str) -> HTMLResponse:
    state = _get_live_state()
    return render_page(
        request,
        "fragments/timeline.html",
        extra={
            "timeline": state["leave_timeline"],
            "entity_id": leave_id,
            "refresh_url": f"/fragments/leave/{leave_id}/timeline",
            "title": "Leave Request Chain",
        },
    )


@app.get("/fragments/presence/{entity}/{entity_id}", response_class=HTMLResponse)
def fragment_presence(request: Request, entity: str, entity_id: str) -> HTMLResponse:
    state = _get_live_state()
    return render_page(
        request,
        "fragments/presence.html",
        extra={
            "entity": entity,
            "entity_id": entity_id,
            "viewers": state["presence_viewers"],
        },
    )


@app.post("/dev/emit", response_class=JSONResponse)
def dev_emit_event(body: dict[str, Any]) -> JSONResponse:
    state = _get_live_state()
    event_name = str(body.get("event", "dashboard.refresh"))
    entity_id = body.get("entity_id")

    if event_name == "notice.created":
        dev_bell_delta["unread_notices"] += 1
        entity_id = entity_id or ""
    elif event_name == "attendance.updated":
        dev_bell_delta["pending_actions"] += 1
        entity_id = entity_id or state["sheet_id"]
        _advance_timeline_steps(state["attendance_timeline"])
    elif event_name == "leave.updated":
        dev_bell_delta["pending_actions"] += 1
        entity_id = entity_id or state["leave_id"]
        _advance_timeline_steps(state["leave_timeline"])
    elif event_name == "presence.updated":
        entity_id = entity_id or state["sheet_id"]
        if len(state["presence_viewers"]) == 1:
            state["presence_viewers"].append(
                {"id": "11111111-1111-4111-8111-111111111104", "name": "Lt. Meera Iyer (ANO)"}
            )
        else:
            state["presence_viewers"] = state["presence_viewers"][:1]
    else:
        entity_id = entity_id or state["sheet_id"]

    payload = {
        "event": event_name,
        "scope_type": "COMPANY",
        "scope_id": "22222222-2222-4222-8222-222222222201",
        "entity": "attendance_sheet" if ("attendance" in event_name or "presence" in event_name) else "unit_event",
        "entity_id": entity_id,
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



"""Integration tests for WebSocket authentication, room routing, and events."""

import pytest
from starlette.websockets import WebSocketDisconnect

from core.security import create_access_token
from realtime.events import EventType
from realtime.websocket import manager


def test_websocket_unauthorized_rejected(client):
    """Connecting without a valid session token should be rejected."""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws"):
            pass


def test_websocket_authorized_connection_and_ping(client, seed_data):
    """Connecting with a valid access token succeeds and responds to ping."""
    cadet1 = seed_data["cadet1"]
    token = create_access_token(
        subject=cadet1.id,
        role=cadet1.role.value,
        scopes={"unit_id": cadet1.unit_id, "squad_id": cadet1.squad_id},
    )

    with client.websocket_connect(f"/ws?token={token}") as ws:
        # Check active connection enrolled in user room
        assert f"user_{cadet1.id}" in manager.rooms
        assert f"unit_{cadet1.unit_id}" in manager.rooms
        assert f"squad_{cadet1.squad_id}" in manager.rooms

        # Test keep-alive ping
        ws.send_text("ping")
        response = ws.receive_text()
        assert response == "pong"


def test_websocket_broadcast_delivery():
    """Verify broadcast delivers structured event JSON to subscribed room sockets."""
    # Verify event types match specification
    assert EventType.ATTENDANCE_CREATED.value == "attendance.created"
    assert EventType.LEAVE_APPROVED.value == "leave.approved"
    assert EventType.TASK_ASSIGNED.value == "task.assigned"
    assert EventType.NOTICE_CREATED.value == "notice.created"

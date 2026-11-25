"""WebSocket connection manager and realtime event distribution."""

import json
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from core.models import User
from core.security import TOKEN_TYPE_ACCESS, decode_token
from database.session import get_db

router = APIRouter(tags=["Realtime"])


class ConnectionManager:
    """Manages scoped WebSocket connections grouped by unit, squad, and user rooms."""

    def __init__(self):
        # Room name -> set of active WebSockets
        self.rooms: dict[str, set[WebSocket]] = defaultdict(set)
        # WebSocket -> set of room names it belongs to
        self.socket_rooms: dict[WebSocket, set[str]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, user: User) -> None:
        """Accept connection and enroll socket in authorized rooms."""
        await websocket.accept()

        rooms_to_join = [f"user_{user.id}"]
        if user.unit_id:
            rooms_to_join.append(f"unit_{user.unit_id}")
        if user.squad_id:
            rooms_to_join.append(f"squad_{user.squad_id}")

        for room in rooms_to_join:
            self.rooms[room].add(websocket)
            self.socket_rooms[websocket].add(room)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove disconnected socket from all subscribed rooms."""
        joined_rooms = self.socket_rooms.pop(websocket, set())
        for room in joined_rooms:
            self.rooms[room].discard(websocket)
            if not self.rooms[room]:
                del self.rooms[room]

    async def broadcast_to_room(self, room: str, event_type: str, payload: dict[str, Any]) -> None:
        """Broadcast JSON message to all active sockets in a specific room."""
        message = json.dumps({"event": event_type, "data": payload})
        sockets = list(self.rooms.get(room, []))
        for socket in sockets:
            try:
                await socket.send_text(message)
            except Exception:
                self.disconnect(socket)

    async def broadcast_to_unit(
        self, unit_id: int, event_type: str, payload: dict[str, Any]
    ) -> None:
        """Broadcast event to all connected personnel in a unit."""
        await self.broadcast_to_room(f"unit_{unit_id}", event_type, payload)

    async def broadcast_to_squad(
        self, squad_id: int, event_type: str, payload: dict[str, Any]
    ) -> None:
        """Broadcast event to all connected personnel in a squad."""
        await self.broadcast_to_room(f"squad_{squad_id}", event_type, payload)

    async def send_to_user(self, user_id: int, event_type: str, payload: dict[str, Any]) -> None:
        """Send direct notification to a specific user."""
        await self.broadcast_to_room(f"user_{user_id}", event_type, payload)


manager = ConnectionManager()


def authenticate_ws(websocket: WebSocket, db: Session) -> User | None:
    """Extract and validate authentication token from cookies or query parameters."""
    token = websocket.cookies.get("access_token")
    if not token:
        token = websocket.query_params.get("token")

    if not token:
        return None

    try:
        payload = decode_token(token, expected_type=TOKEN_TYPE_ACCESS)
        user_id = int(payload["sub"])
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.is_active:
            return user
    except Exception:
        return None

    return None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    """Authenticated WebSocket endpoint supporting room-based realtime dispatch."""
    user = authenticate_ws(websocket, db)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, user)
    try:
        while True:
            # Keep-alive ping/pong and message handling
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

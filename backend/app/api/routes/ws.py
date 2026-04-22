"""WebSocket endpoint for real-time job progress updates."""
import asyncio
import json
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.auth import decode_access_token

router = APIRouter()

# Active WebSocket connections: job_id -> set of websockets
active_connections: Dict[str, Set[WebSocket]] = {}
# Dashboard connections (receive all updates)
dashboard_connections: Set[WebSocket] = set()


async def broadcast_job_update(job_id: int, data: dict):
    """Broadcast progress update to all clients watching a specific job."""
    key = str(job_id)
    message = json.dumps({"type": "job_update", "job_id": job_id, **data})

    # Job-specific watchers
    if key in active_connections:
        dead = set()
        for ws in active_connections[key]:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        active_connections[key] -= dead
        if not active_connections[key]:
            del active_connections[key]

    # Dashboard watchers
    dead = set()
    for ws in dashboard_connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    dashboard_connections -= dead


@router.websocket("/ws/jobs/{job_id}")
async def ws_job_progress(websocket: WebSocket, job_id: int):
    """WebSocket for watching a specific job's progress."""
    # Accept connection
    await websocket.accept()

    # Optional: authenticate via query param
    try:
        token = websocket.query_params.get("token", "")
        if token:
            decode_access_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    key = str(job_id)
    if key not in active_connections:
        active_connections[key] = set()
    active_connections[key].add(websocket)

    try:
        while True:
            # Keep connection alive, accept pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        active_connections.get(key, set()).discard(websocket)


@router.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    """WebSocket for dashboard — receives all job updates."""
    await websocket.accept()

    try:
        token = websocket.query_params.get("token", "")
        if token:
            decode_access_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    dashboard_connections.add(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        dashboard_connections.discard(websocket)

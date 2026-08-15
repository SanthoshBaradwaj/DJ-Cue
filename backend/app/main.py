"""DJ-Cue backend entrypoint.

    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

CORS is fully permissive on purpose: guests hit this from arbitrary phones on
a venue LAN, and there is nothing to protect -- no accounts, no personal
data, just an anonymous session id and a song title.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.service import get_service
from .config import settings
from .contracts import (
    DashboardState,
    DJStatusUpdate,
    EventCreate,
    RequestCreate,
    StatusUpdate,
    WSMessage,
)
from .events import bus
from .genres import GENRES

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("cue")

VERSION = "2.1.0"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not settings.has_supabase:
        log.warning(
            "SUPABASE_URL / SUPABASE_ANON_KEY not set -- the API will fail on first "
            "request. Copy .env.example to .env and fill them in."
        )
    log.info("DJ-Cue %s ready | guest URL: http://%s:3000", VERSION, lan_ip())
    yield


app = FastAPI(title="DJ-Cue", version=VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def lan_ip() -> str:
    """Best-effort LAN address, so the QR code points somewhere phones can reach."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))  # no packets sent; just picks the route
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "127.0.0.1"


@app.get("/api/health")
def health():
    db = get_service().db_health()
    return {
        "ok": db.ok,
        "supabase": settings.has_supabase,
        "version": VERSION,
        "db": db.model_dump(mode="json"),
    }


@app.get("/api/genres")
def genres():
    return {"genres": [g.model_dump() for g in GENRES]}


@app.get("/api/events")
def list_events():
    events = get_service().list_events()
    return {"events": [e.model_dump(mode="json") for e in events]}


@app.post("/api/events")
def create_event(payload: EventCreate):
    name = (payload.name or "").strip()
    if not name:
        return JSONResponse(status_code=422, content={"detail": "Event name is required."})
    event = get_service().create_event(name)
    return event.model_dump(mode="json")


@app.post("/api/events/{event_id}/status")
def update_dj_status(event_id: str, payload: DJStatusUpdate):
    if payload.status not in ("open", "busy", "closed"):
        return JSONResponse(status_code=422, content={"detail": "unknown dj status"})
    updated = get_service().set_dj_status(event_id, payload.status)
    if updated is None:
        return JSONResponse(status_code=404, content={"detail": "event not found"})
    return updated.model_dump(mode="json")


@app.get("/api/config")
def config(event_id: Optional[str] = Query(default=None)):
    resolved = get_service().resolve_event_id(event_id)
    event = get_service().get_event(resolved)
    guest_url = settings.public_url or ("http://%s:3000" % lan_ip())
    return {
        "event_id": resolved,
        "guest_url": "%s/?event=%s" % (guest_url, resolved),
        "dj_status": event.dj_status if event else "open",
    }


@app.get("/api/catalog/search")
def catalog_search(q: str = "", genre: Optional[str] = None, limit: int = 8):
    tracks = get_service().search_songs(q, genre, limit=limit)
    return {"songs": [t.model_dump(mode="json") for t in tracks]}


@app.post("/api/requests")
def create_request(payload: RequestCreate):
    song_title = (payload.song_title or "").strip()[:200]
    if not song_title:
        return JSONResponse(
            status_code=422, content={"detail": "Tell the DJ what song you want."}
        )
    session_id = (payload.session_id or "").strip() or ("sess_%s" % uuid.uuid4().hex[:10])
    event_id = get_service().resolve_event_id(payload.event_id)
    ack = get_service().submit_request(
        event_id=event_id,
        session_id=session_id,
        song_title=song_title,
        song_artist=(payload.song_artist or "").strip()[:200],
        genre=(payload.genre or "").strip(),
        song_id=payload.song_id,
        artwork_url=payload.artwork_url,
    )
    return ack.model_dump(mode="json")


@app.get("/api/dashboard", response_model=DashboardState)
def dashboard(event_id: Optional[str] = Query(default=None)):
    resolved = get_service().resolve_event_id(event_id)
    return get_service().build_dashboard(resolved)


@app.post("/api/requests/{request_id}/status")
def update_request_status(request_id: str, payload: StatusUpdate, event_id: str = Query(...)):
    if payload.status not in ("played", "dismissed", "queued"):
        return JSONResponse(status_code=422, content={"detail": "unknown status"})
    updated = get_service().set_request_status(event_id, request_id, payload.status)
    if updated is None:
        return JSONResponse(status_code=404, content={"detail": "request not found"})
    return updated.model_dump(mode="json")


@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket, event_id: Optional[str] = None):
    service = get_service()
    resolved = service.resolve_event_id(event_id)
    await websocket.accept()
    queue = bus.subscribe(resolved)

    try:
        # Paint immediately on connect; never make a dashboard wait for the
        # first mutation to show something.
        await websocket.send_text(
            WSMessage(
                type="state",
                payload=service.build_dashboard(resolved).model_dump(mode="json"),
            ).model_dump_json()
        )
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=20.0)
            except asyncio.TimeoutError:
                # Keepalive: venue wifi and proxies drop idle sockets, and a
                # silently dead socket looks identical to a dead product.
                await websocket.send_text(
                    WSMessage(
                        type="state",
                        payload=service.build_dashboard(resolved).model_dump(mode="json"),
                    ).model_dump_json()
                )
                continue
            await websocket.send_text(message.model_dump_json())
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover - transport noise
        log.info("dashboard socket closed: %s", exc)
    finally:
        bus.unsubscribe(resolved, queue)

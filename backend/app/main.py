"""CUE backend entrypoint.

    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

CORS is fully permissive on purpose: guests hit this from arbitrary phones on a
venue LAN, and there is nothing to protect -- no accounts, no personal data,
one ephemeral event.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Optional

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .api.service import get_service
from .catalog import audio as audio_module
from .config import settings
from .contracts import (
    DashboardState,
    DecisionCreate,
    EventStats,
    RequestAck,
    RequestCreate,
    WSMessage,
)
from .contracts import new_id
from .demo.seeder import seed_event
from .events import bus

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("cue")

VERSION = "1.0.0"

app = FastAPI(title="CUE", version=VERSION)
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
    service = get_service()
    return {
        "ok": True,
        "llm_enabled": settings.has_llm,
        "llm_provider": settings.llm_provider,
        "track_count": len(service.catalog.all()),
        # How many drop-in files were matched. 0 is normal -- the dashboard
        # synthesises audio per track -- but it is the fastest way to confirm
        # from the booth that the MP3s you just copied in were actually seen.
        "audio_files": getattr(service.catalog, "audio_matched", 0),
        "version": VERSION,
    }


@app.get("/api/config")
def config():
    guest_url = settings.public_url or ("http://%s:3000" % lan_ip())
    return {
        "event_id": settings.default_event_id,
        "guest_url": guest_url,
        "llm_enabled": settings.has_llm,
    }


@app.post("/api/requests", response_model=RequestAck)
async def create_request(payload: RequestCreate):
    text = (payload.text or "").strip()
    if not text:
        return JSONResponse(
            status_code=422, content={"detail": "Tell the DJ what you want to hear."}
        )
    # Cap absurd input rather than rejecting it -- a guest pasting an essay
    # should still get a friendly ack.
    text = text[:400]
    session_id = (payload.session_id or "").strip() or new_id("sess")
    return await get_service().submit_request(text, session_id, payload.event_id)


@app.get("/api/dashboard", response_model=DashboardState)
def dashboard(event_id: str = Query(default=settings.default_event_id)):
    return get_service().build_dashboard(event_id)


@app.post("/api/decisions")
def create_decision(payload: DecisionCreate):
    if payload.action not in ("play", "later", "skip"):
        return JSONResponse(status_code=422, content={"detail": "unknown action"})
    dj = get_service().record_decision(
        payload.track_id, payload.action, payload.wave_id, payload.event_id
    )
    return {"ok": True, "dj": dj.model_dump(mode="json")}


@app.get("/api/catalog/search")
def catalog_search(q: str = "", limit: int = 10):
    tracks = get_service().catalog.search(q, limit=limit)
    return {"tracks": [t.model_dump(mode="json") for t in tracks]}


@app.get("/api/stats", response_model=EventStats)
def stats(event_id: str = Query(default=settings.default_event_id)):
    return get_service().store.stats(event_id)


@app.get("/api/setlist")
def get_setlist(event_id: str = Query(default=settings.default_event_id)):
    """The DJ's planned set: what has played, what is next."""
    dj = get_service().store.dj_state(event_id)
    return {
        "event_id": event_id,
        "setlist": [e.model_dump(mode="json") for e in sorted(dj.setlist, key=lambda x: x.position)],
        "upcoming": [e.model_dump(mode="json") for e in dj.upcoming()],
        "current_track": dj.current_track.model_dump(mode="json") if dj.current_track else None,
    }


@app.post("/api/setlist")
def post_setlist(payload: dict):
    """Import a set as ``{entries: [{cue_time, title}, ...]}``.

    ``unmatched`` is the important half of the response: titles the catalog
    could not confidently resolve are reported, never guessed at.
    """
    event_id = payload.get("event_id", settings.default_event_id)
    entries = payload.get("entries") or []
    if not isinstance(entries, list):
        return JSONResponse({"ok": False, "error": "entries must be a list"}, status_code=400)
    dj, unmatched = get_service().load_setlist(event_id, entries)
    return {
        "ok": True,
        "loaded": len(dj.setlist),
        "unmatched": unmatched,
        "upcoming": [e.model_dump(mode="json") for e in dj.upcoming()],
    }


@app.post("/api/setlist/advance")
def advance_setlist(payload: dict):
    """The DJ moved to the next planned slot. Settles tips on it."""
    event_id = payload.get("event_id", settings.default_event_id)
    dj = get_service().advance_setlist(event_id)
    return {"ok": True, "dj": dj.model_dump(mode="json")}


@app.get("/api/insertions")
def insertions(event_id: str = Query(default=settings.default_event_id)):
    """Where the crowd's requests belong inside the DJ's planned set."""
    service = get_service()
    proposals = service.propose_insertions(event_id)
    return {
        "event_id": event_id,
        "proposals": [p.model_dump(mode="json") for p in proposals],
        "tip_totals": service.tip_totals(event_id),
    }


@app.post("/api/insertions/accept")
def accept_insertion(payload: dict):
    """Accept a proposal into the set. Does *not* settle the tip -- playing does."""
    event_id = payload.get("event_id", settings.default_event_id)
    track_id = str(payload.get("track_id", ""))
    position = int(payload.get("position", 0))
    wave_id = payload.get("wave_id")
    dj = get_service().insert_into_setlist(event_id, track_id, position, wave_id)
    return {"ok": True, "dj": dj.model_dump(mode="json")}


@app.post("/api/tips")
def create_tip(payload: dict):
    """Authorise a tip against one track. Nothing is charged at this point."""
    service = get_service()
    tip = service.create_tip(
        event_id=payload.get("event_id", settings.default_event_id),
        session_id=str(payload.get("session_id", "")),
        track_id=str(payload.get("track_id", "")),
        amount_minor=int(payload.get("amount_minor", 0)),
        wave_id=payload.get("wave_id"),
        currency=str(payload.get("currency", "INR")),
    )
    if tip is None:
        return JSONResponse(
            {"ok": False, "error": "unknown track or non-positive amount"},
            status_code=400,
        )
    return {"ok": True, "tip": tip.model_dump(mode="json")}


@app.get("/api/tips")
def list_tips(event_id: str = Query(default=settings.default_event_id)):
    service = get_service()
    return {
        "event_id": event_id,
        "tips": [t.model_dump(mode="json") for t in service.tips(event_id)],
        "totals": service.tip_totals(event_id),
    }


@app.post("/api/tips/release")
def release_tips(payload: dict):
    """End of set: release every tip whose song never played."""
    event_id = payload.get("event_id", settings.default_event_id)
    service = get_service()
    released = service.release_pending_tips(event_id)
    return {
        "ok": True,
        "released": len(released),
        "totals": service.tip_totals(event_id),
    }


@app.get("/audio/{filename}")
def audio(filename: str):
    """Serve a drop-in file from ``audio/``.

    Only ever reachable for a name the catalog already matched to a track;
    ``audio.resolve`` re-checks that the path lands inside the audio directory,
    so a crafted filename cannot read anything else off the DJ's laptop.
    """
    path = audio_module.resolve(filename)
    if path is None:
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    # Range requests matter here: the browser seeks within the file to loop it.
    return FileResponse(path, headers={"Accept-Ranges": "bytes"})


@app.post("/api/demo/seed")
async def demo_seed(payload: dict):
    count = int(payload.get("count", 50))
    event_id = payload.get("event_id", settings.default_event_id)
    delay_ms = int(payload.get("delay_ms", 120))
    seeded = await seed_event(
        get_service(), event_id=event_id, count=count, delay_ms=delay_ms
    )
    return {"ok": True, "seeded": seeded}


@app.post("/api/demo/reset")
def demo_reset(payload: dict):
    event_id = payload.get("event_id", settings.default_event_id)
    get_service().reset(event_id)
    return {"ok": True}


@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket, event_id: Optional[str] = None):
    event_id = event_id or settings.default_event_id
    await websocket.accept()
    service = get_service()
    queue = bus.subscribe(event_id)

    try:
        # Paint immediately on connect; never make a dashboard wait for the
        # first mutation to show something.
        await websocket.send_text(
            WSMessage(
                type="state",
                payload=service.build_dashboard(event_id).model_dump(mode="json"),
            ).model_dump_json()
        )
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=20.0)
            except asyncio.TimeoutError:
                # Keepalive: venue wifi and proxies drop idle sockets, and a
                # silently dead socket looks identical to a dead product.
                await websocket.send_text(
                    WSMessage(type="state",
                              payload=service.build_dashboard(event_id)
                              .model_dump(mode="json")).model_dump_json()
                )
                continue
            await websocket.send_text(message.model_dump_json())
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover - transport noise
        log.info("dashboard socket closed: %s", exc)
    finally:
        bus.unsubscribe(event_id, queue)


@app.on_event("startup")
def on_startup():
    service = get_service()
    log.info(
        "CUE %s ready | %d tracks | LLM: %s | guest URL: http://%s:3000",
        VERSION,
        len(service.catalog.all()),
        settings.llm_provider or "disabled (deterministic interpreter)",
        lan_ip(),
    )

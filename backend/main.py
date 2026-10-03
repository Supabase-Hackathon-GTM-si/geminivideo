"""
FastAPI app: HTTP + WebSocket API for the beverage detector.

Run:  .venv/bin/uvicorn backend.main:app --reload --port 8000
"""

import logging
from typing import Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import config
from .event_sink import sink
from .session_manager import manager
from .sources.browser_source import BrowserSource

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Livestream Beverage Detector")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"])


class CreateSession(BaseModel):
    source: Literal["url", "browser"]
    url: Optional[str] = None
    streamer_id: str = "demo-streamer"


@app.get("/api/health")
async def health():
    return {"ok": True, "model": config.GEMINI_MODEL, "chunk_seconds": config.CHUNK_SECONDS,
            "api_key_set": bool(config.GEMINI_API_KEY)}


@app.post("/api/sessions")
async def create_session(body: CreateSession):
    try:
        s = await manager.create(body.source, body.streamer_id, body.url)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))
    return s.summary()


@app.get("/api/sessions")
async def list_sessions():
    return [s.summary() for s in manager.sessions.values()]


@app.post("/api/sessions/{session_id}/chunk")
async def upload_chunk(session_id: str, file: UploadFile = File(...),
                       duration: float = Form(config.CHUNK_SECONDS)):
    s = manager.sessions.get(session_id)
    if not s or not isinstance(s.source, BrowserSource):
        raise HTTPException(404, "browser session not found")
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty chunk")
    idx = await s.source.push(data, file.content_type or "video/webm", duration)
    return {"chunk_index": idx, "bytes": len(data)}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    await manager.stop(session_id)
    return {"ok": True}


@app.get("/api/events")
async def recent_events():
    return sink.recent


@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await ws.accept()
    sink.sockets.add(ws)
    try:
        for s in manager.sessions.values():
            await ws.send_json({"type": "session", "data": s.summary()})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        sink.sockets.discard(ws)


@app.on_event("shutdown")
async def shutdown():
    for sid in list(manager.sessions):
        await manager.stop(sid)

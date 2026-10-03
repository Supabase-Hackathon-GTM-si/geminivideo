"""
Session manager: one session per stream being watched.

Each session owns a source (URL or browser) and a chunk queue. A worker pulls
chunks, sends them to Gemini (up to MAX_CONCURRENT in flight so a slow call
doesn't stall the stream), and turns detections into events:

- moments below CONFIDENCE_THRESHOLD are dropped
- per streamer, at most one tip-worthy event per COOLDOWN_SECONDS of stream
  time; detections inside the cooldown are still shown on the dashboard but
  are not sent to the tipping webhook
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from uuid import uuid4

from . import config
from .event_sink import sink
from .gemini_analyzer import analyze_clip
from .models import BeverageEvent, ChunkStatus
from .sources import Chunk
from .sources.browser_source import BrowserSource
from .sources.url_source import UrlSource

log = logging.getLogger("session")

MAX_CONCURRENT = 3


@dataclass
class Session:
    id: str
    source_type: str
    streamer_id: str
    url: Optional[str]
    source: UrlSource | BrowserSource | None = None
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    worker: Optional[asyncio.Task] = None
    last_tip_offset: Optional[float] = None
    chunks_analyzed: int = 0
    events_detected: int = 0
    started_at: float = field(default_factory=time.time)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "source": self.source_type,
            "streamer_id": self.streamer_id,
            "url": self.url,
            "chunks_analyzed": self.chunks_analyzed,
            "events_detected": self.events_detected,
            "source_exited": bool(self.source and self.source.exited),
            "started_at": self.started_at,
        }


class SessionManager:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}

    async def create(self, source_type: str, streamer_id: str, url: Optional[str]) -> Session:
        s = Session(id=uuid4().hex[:12], source_type=source_type, streamer_id=streamer_id, url=url)

        async def enqueue(chunk: Chunk) -> None:
            await s.queue.put(chunk)

        if source_type == "url":
            if not url:
                raise ValueError("url is required for source=url")
            s.source = UrlSource(s.id, url, enqueue)
        else:
            s.source = BrowserSource(s.id, enqueue)

        await s.source.start()
        s.worker = asyncio.create_task(self._work(s))
        self.sessions[s.id] = s
        await sink.broadcast({"type": "session", "data": s.summary()})
        log.info("session %s started source=%s url=%s", s.id, source_type, url)
        return s

    async def stop(self, session_id: str) -> None:
        s = self.sessions.pop(session_id, None)
        if not s:
            return
        if s.source:
            await s.source.stop()
        if s.worker:
            s.worker.cancel()
        await sink.broadcast({"type": "session_stopped", "data": {"id": session_id}})

    async def _work(self, s: Session) -> None:
        sem = asyncio.Semaphore(MAX_CONCURRENT)

        async def run(chunk: Chunk) -> None:
            async with sem:
                await self._analyze(s, chunk)

        while True:
            chunk = await s.queue.get()
            asyncio.create_task(run(chunk))

    async def _analyze(self, s: Session, chunk: Chunk) -> None:
        status = ChunkStatus(session_id=s.id, chunk_index=chunk.index,
                             stream_offset_seconds=chunk.stream_offset_seconds, status="analyzing")
        await sink.broadcast({"type": "chunk", "data": status.model_dump(mode="json")})
        started = time.monotonic()
        try:
            result = await analyze_clip(chunk.data, chunk.mime_type)
        except Exception as exc:
            log.exception("chunk %s/%d failed", s.id, chunk.index)
            status.status = "error"
            status.error = str(exc)[:300]
            status.latency_ms = int((time.monotonic() - started) * 1000)
            await sink.broadcast({"type": "chunk", "data": status.model_dump(mode="json")})
            return

        s.chunks_analyzed += 1
        moments = [m for m in result.moments if m.confidence >= config.CONFIDENCE_THRESHOLD]
        status.latency_ms = int((time.monotonic() - started) * 1000)
        status.moments_found = len(moments)
        status.status = "detected" if moments else "nothing_found"
        await sink.broadcast({"type": "chunk", "data": status.model_dump(mode="json")})

        for m in sorted(moments, key=lambda m: m.offset_seconds):
            offset = chunk.stream_offset_seconds + max(0.0, m.offset_seconds)
            event = BeverageEvent(
                session_id=s.id,
                streamer_id=s.streamer_id,
                category=m.category,
                confidence=round(m.confidence, 3),
                description=m.description,
                quote=m.quote,
                brand=m.brand,
                stream_offset_seconds=round(offset, 1),
                suggested_tip_cents=config.TIP_CENTS_BY_CATEGORY.get(m.category.value, 0),
            )
            tipped = s.last_tip_offset is None or offset - s.last_tip_offset >= config.COOLDOWN_SECONDS
            if tipped:
                s.last_tip_offset = offset
                await sink.emit_tip(event)
            s.events_detected += 1
            await sink.broadcast({"type": "event", "data": event.model_dump(mode="json"), "tipped": tipped})

        await sink.broadcast({"type": "session", "data": s.summary()})


manager = SessionManager()

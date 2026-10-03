"""
Data models.

- `Moment` / `BeverageDetection`: the structured JSON schema Gemini must return
  for each analyzed clip.
- `BeverageEvent`: the contract emitted to teammates (Supabase + Stripe). Keep
  this stable; they build against it.
- `ChunkStatus`: per-clip pipeline health shown in the dashboard.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Category(str, Enum):
    sports_drink_mention = "sports_drink_mention"
    drinking_water = "drinking_water"
    drinking_other = "drinking_other"
    holding_or_showing_beverage = "holding_or_showing_beverage"
    verbal_beverage_mention = "verbal_beverage_mention"


class Moment(BaseModel):
    category: Category
    confidence: float = Field(description="0.0 to 1.0")
    offset_seconds: float = Field(description="Seconds from the start of this clip")
    description: str = Field(description="What happened, one sentence")
    quote: Optional[str] = Field(default=None, description="Exact words spoken, if any")
    brand: Optional[str] = Field(default=None, description="Beverage brand if identifiable")


class BeverageDetection(BaseModel):
    detected: bool
    moments: list[Moment]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BeverageEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    streamer_id: str
    category: Category
    confidence: float
    description: str
    quote: Optional[str] = None
    brand: Optional[str] = None
    stream_offset_seconds: float
    detected_at: str = Field(default_factory=_now)
    suggested_tip_cents: int


class ChunkStatus(BaseModel):
    session_id: str
    chunk_index: int
    stream_offset_seconds: float
    status: Literal["analyzing", "nothing_found", "detected", "error"]
    latency_ms: Optional[int] = None
    moments_found: int = 0
    error: Optional[str] = None
    at: str = Field(default_factory=_now)

"""
Stream sources. Each source pushes `Chunk`s into a session's queue.
"""

from dataclasses import dataclass


@dataclass
class Chunk:
    index: int
    stream_offset_seconds: float
    data: bytes
    mime_type: str

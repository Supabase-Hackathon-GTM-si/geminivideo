"""
Gemini video understanding for short livestream clips.

Each clip (mp4 from the URL pipeline or webm from the browser) is sent inline
to Gemini with a JSON response schema. The model watches the video AND listens
to the audio, so it catches both visual moments (sipping water, holding a
bottle) and spoken mentions ("this Gatorade hits different").

Transient errors (503 overloaded, 429 rate limit) are retried with exponential
backoff.

CLI test:  python -m backend.gemini_analyzer path/to/clip.mp4
"""

import asyncio
import logging
import random
import sys
import time

from google import genai
from google.genai import errors, types

from . import config
from .models import BeverageDetection

log = logging.getLogger("gemini")

SYSTEM_PROMPT = """You are a marketing analyst for a sports drink / beverage brand.
You watch short clips from a livestream (video + audio) and report every moment
where the streamer does something beverage-related, so the brand can tip them.

Report a moment for any of these categories:
- sports_drink_mention: streamer names or talks about a sports/energy drink (Gatorade, Prime, Powerade, Liquid IV, BodyArmor, Red Bull, etc.)
- drinking_water: streamer visibly drinks water
- drinking_other: streamer visibly drinks any other beverage
- holding_or_showing_beverage: streamer holds, shows off, or points at a drink/bottle/can/cup without drinking
- verbal_beverage_mention: streamer talks about drinks, hydration, being thirsty, etc. without naming a sports drink

Rules:
- Only report what actually happens in THIS clip. Do not guess.
- A bottle merely sitting on the desk in the background is NOT a moment.
- confidence is 0.0-1.0; be calibrated.
- offset_seconds is when the moment starts, relative to the clip start.
- quote: exact spoken words if the moment involves speech, else null.
- brand: name it only if visible or spoken, else null.
- If nothing beverage-related happens, return detected=false and an empty moments list."""

_client: genai.Client | None = None


def client() -> genai.Client:
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set (put it in backend/.env)")
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, errors.APIError):
        return exc.code in (429, 500, 502, 503, 504)
    return isinstance(exc, (TimeoutError, ConnectionError))


async def analyze_clip(data: bytes, mime_type: str) -> BeverageDetection:
    """Send one clip to Gemini and return the parsed detection."""
    contents = [
        types.Part.from_bytes(data=data, mime_type=mime_type),
        "Analyze this livestream clip for beverage-related moments.",
    ]
    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=BeverageDetection,
        temperature=0.2,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    for attempt in range(config.GEMINI_MAX_RETRIES + 1):
        started = time.monotonic()
        log.info("generate_content model=%s mime=%s bytes=%d attempt=%d",
                 config.GEMINI_MODEL, mime_type, len(data), attempt)
        try:
            resp = await client().aio.models.generate_content(
                model=config.GEMINI_MODEL, contents=contents, config=cfg
            )
        except Exception as exc:
            if attempt < config.GEMINI_MAX_RETRIES and _is_retryable(exc):
                delay = (2 ** attempt) + random.random()
                log.warning("Gemini error %s, retrying in %.1fs", exc, delay)
                await asyncio.sleep(delay)
                continue
            raise

        log.info("gemini output (%.0f ms): %s", (time.monotonic() - started) * 1000, resp.text)
        if isinstance(resp.parsed, BeverageDetection):
            return resp.parsed
        return BeverageDetection.model_validate_json(resp.text or '{"detected": false, "moments": []}')

    raise RuntimeError("unreachable")


def mime_for(path: str) -> str:
    if path.endswith(".webm"):
        return "video/webm"
    if path.endswith(".mov"):
        return "video/quicktime"
    return "video/mp4"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) != 2:
        sys.exit("usage: python -m backend.gemini_analyzer <clip.mp4>")
    path = sys.argv[1]
    with open(path, "rb") as f:
        result = asyncio.run(analyze_clip(f.read(), mime_for(path)))
    print(result.model_dump_json(indent=2))

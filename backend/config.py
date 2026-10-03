"""
Central configuration for the livestream beverage detector.

Everything tunable (model name, chunk length, thresholds, tip amounts, webhook)
lives here so it can be changed via backend/.env without touching code.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

CHUNK_SECONDS = int(os.getenv("CHUNK_SECONDS", "10"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
COOLDOWN_SECONDS = float(os.getenv("COOLDOWN_SECONDS", "30"))

GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "4"))

EVENT_WEBHOOK_URL = os.getenv("EVENT_WEBHOOK_URL", "")

CHUNKS_DIR = BACKEND_DIR / ".chunks"
EVENTS_LOG = BACKEND_DIR / "events.jsonl"

# Suggested tip per category; the Stripe side makes the final call.
TIP_CENTS_BY_CATEGORY = {
    "sports_drink_mention": 300,
    "drinking_water": 100,
    "drinking_other": 100,
    "holding_or_showing_beverage": 50,
    "verbal_beverage_mention": 50,
}

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")


def _csv(name: str, default: str) -> list[str]:
    return [s.strip() for s in os.getenv(name, default).split(",") if s.strip()]


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# Campaign: the brand paying for tips, and brands that must never be tipped.
SPONSOR_BRAND = os.getenv("SPONSOR_BRAND", "Gatorade")
COMPETITOR_BRANDS = _csv(
    "COMPETITOR_BRANDS",
    "Prime,Powerade,BodyArmor,Liquid IV,Red Bull,Monster,Celsius,Ghost,G Fuel,Electrolit",
)

# Second, stricter pass on tip candidates before anything is paid.
GEMINI_VERIFY_MODEL = os.getenv("GEMINI_VERIFY_MODEL", "gemini-pro-latest")
VERIFY_ENABLED = _bool("VERIFY_ENABLED", True)

# real_person, animated_character, video_playback
ALLOWED_SUBJECT_TYPES = set(_csv("ALLOWED_SUBJECT_TYPES", "real_person"))

# Sponsor screen-time bonus, paid per clip on prominence-weighted seconds.
EXPOSURE_CENTS_PER_SECOND = float(os.getenv("EXPOSURE_CENTS_PER_SECOND", "5"))
PROMINENCE_WEIGHTS = {"high": 1.0, "medium": 0.5, "low": 0.0}
MIN_EXPOSURE_SECONDS = float(os.getenv("MIN_EXPOSURE_SECONDS", "2"))

SAFETY_BLOCKS_TIPS = _bool("SAFETY_BLOCKS_TIPS", True)

# At most REPEAT_LIMIT tips for the same category+brand per REPEAT_WINDOW_SECONDS of stream.
REPEAT_LIMIT = int(os.getenv("REPEAT_LIMIT", "3"))
REPEAT_WINDOW_SECONDS = float(os.getenv("REPEAT_WINDOW_SECONDS", "600"))

# Chunks waiting beyond this are dropped so analysis stays close to live.
MAX_BACKLOG = int(os.getenv("MAX_BACKLOG", "3"))

EVIDENCE_DIR = BACKEND_DIR / "evidence"

# Bounding boxes around the product on each evidence thumbnail.
BOXES_ENABLED = _bool("BOXES_ENABLED", True)

# Live chat: Twitch chat is read anonymously; chat around a moment is sent to
# the verifier with the clip to score audience reaction.
TWITCH_CHAT = _bool("TWITCH_CHAT", True)
CHAT_CONTEXT_SECONDS = float(os.getenv("CHAT_CONTEXT_SECONDS", "5"))
CHAT_REACTION_SECONDS = float(os.getenv("CHAT_REACTION_SECONDS", "12"))
REACTION_TIP_MULTIPLIERS = {"none": 1.0, "low": 1.0, "medium": 1.25, "high": 1.5}

# Demo-mode thank-you alerts (sessions created with demo_alerts=true).
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-flash-latest")
GEMINI_TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
TTS_VOICE = os.getenv("TTS_VOICE", "Puck")
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
ALERT_CARDS = _bool("ALERT_CARDS", True)

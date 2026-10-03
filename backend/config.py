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

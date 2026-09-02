"""
Configuration Module for Jules Telegram Bot.
Handles loading environment variables, system constants, and default configurations.
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# Base Directories
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Telegram Bot Configuration
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

# Admin IDs (comma-separated integers: "12345678,87654321")
def _parse_admin_ids(raw_ids: str) -> List[int]:
    admin_ids = []
    if not raw_ids:
        return admin_ids
    for item in raw_ids.split(","):
        cleaned = item.strip()
        if cleaned.isdigit():
            admin_ids.append(int(cleaned))
    return admin_ids

ADMIN_IDS: List[int] = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))

# Google Gemini / Jules Agent API Configuration
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()

# Model Definitions & Aliases
# You can customize the exact model IDs via environment variables
MODEL_PRO_ID: str = os.getenv("MODEL_PRO_ID", "gemini-2.5-pro")
MODEL_FLASH_ID: str = os.getenv("MODEL_FLASH_ID", "gemini-2.5-flash")

# Human-readable display names for Telegram UI
MODEL_PRO_NAME: str = os.getenv("MODEL_PRO_NAME", "Gemini 3.1 Pro (Jules Core)")
MODEL_FLASH_NAME: str = os.getenv("MODEL_FLASH_NAME", "Gemini 3.6 Flash (Fast Agent)")

# Database Configuration
DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(DEFAULT_DATA_DIR / "jules_bot.db")).strip()

# Web Server & Port Configuration (for Render Web Service health-checks)
PORT: int = int(os.getenv("PORT", "8080"))
HOST: str = os.getenv("HOST", "0.0.0.0")

# Jules System Instruction (System Prompt for Code & Architecture Agent)
JULES_SYSTEM_PROMPT: str = os.getenv(
    "JULES_SYSTEM_PROMPT",
    (
        "You are Jules, Google's advanced autonomous coding and architecture AI agent. "
        "You provide world-class software engineering assistance directly inside Telegram.\n\n"
        "Guidelines:\n"
        "1. Write production-ready, clean, well-documented code adhering to industry best practices.\n"
        "2. Break down complex problems, identify root causes of bugs, and suggest robust architectural designs.\n"
        "3. Provide full in-chat code implementations and explanations, never omitting critical parts or deferring to external links.\n"
        "4. Format code using proper language syntax identifiers (e.g. ```python, ```typescript, ```yaml, ```json, etc.).\n"
        "5. Table formatting: Keep tables concise (maximum 2-3 columns for optimal mobile rendering). "
        "Keep each table row on a single line. Always include a header row followed by delimiter |---|---|, "
        "and leave a blank line before and after the table.\n"
        "6. Lists: Use `-` for bullet lists and `- [ ]` / `- [x]` for task checkboxes.\n"
        "7. For analytical explanations, use clean markdown with expandable quotes (> quote) and concise headings.\n"
        "8. Respond politely, efficiently, and in the language preferred by the user (Arabic or English)."
    )
)

# Supported Features Constants
FEATURE_SWITCH_MODEL = "switch_model"
FEATURE_USE_PRO = "use_pro"
FEATURE_UPLOAD_FILES = "upload_files"
FEATURE_SEND_IMAGES = "send_images"
FEATURE_CREATE_SESSIONS = "create_sessions"
FEATURE_CUSTOM_KEYS = "custom_keys"

ALL_FEATURES = [
    FEATURE_SWITCH_MODEL,
    FEATURE_USE_PRO,
    FEATURE_UPLOAD_FILES,
    FEATURE_SEND_IMAGES,
    FEATURE_CREATE_SESSIONS,
    FEATURE_CUSTOM_KEYS,
]

FEATURE_NAMES = {
    FEATURE_SWITCH_MODEL: "تبديل النماذج",
    FEATURE_USE_PRO: "استخدام Gemini 3.1 Pro",
    FEATURE_UPLOAD_FILES: "رفع وتحليل الملفات (PDF/MD/Code)",
    FEATURE_SEND_IMAGES: "إرسال وتحليل الصور",
    FEATURE_CREATE_SESSIONS: "إنشاء جلسات متعددة",
    FEATURE_CUSTOM_KEYS: "استخدام مفاتيح API خاصة",
}

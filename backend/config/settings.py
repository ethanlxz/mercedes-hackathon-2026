"""
config/settings.py
------------------
Application-level configuration and constants.
All environment variables, file paths, and tunable settings live here.
"""

import os

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env from project root (one level above backend/)
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Absolute path to the backend/ directory (one level up from this file)
BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Path to the persistent JSON memory file
MEMORY_FILE: str = os.path.join(BASE_DIR, "memory.json")

# Path to the frontend/ directory (sibling of backend/)
FRONTEND_DIR: str = os.path.join(os.path.dirname(BASE_DIR), "frontend")

# ---------------------------------------------------------------------------
# App metadata
# ---------------------------------------------------------------------------

APP_TITLE: str = "Mercedes Mobility Assistant API"
APP_VERSION: str = "2.0.0"

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

CORS_ORIGINS: list = ["*"]

# ---------------------------------------------------------------------------
# Gemini / LangGraph
# ---------------------------------------------------------------------------

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

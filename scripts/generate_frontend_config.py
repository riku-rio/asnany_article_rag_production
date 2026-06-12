"""
Generate web/config.js from .env settings.

Only public, non-secret values are written to config.js.
Run: uv run python scripts/generate_frontend_config.py
"""

import json
from pathlib import Path

from dotenv import load_dotenv
import os

# ── Load .env ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

# ── Read allowed public variables only ────────────────────────────────────────
api_base = os.getenv("FRONTEND_API_BASE", "http://localhost:8000").strip()

# ── Build config.js content ───────────────────────────────────────────────────
# Use json.dumps for safe value escaping — no manual string concatenation.
config_js = f"window.ASNANY_CONFIG = {{\n  API_BASE: {json.dumps(api_base)}\n}};\n"

# ── Write file ────────────────────────────────────────────────────────────────
out_path = PROJECT_ROOT / "web" / "config.js"
out_path.write_text(config_js, encoding="utf-8")

print(f"✅ config.js written to {out_path}")
print(f"   API_BASE = {api_base}")

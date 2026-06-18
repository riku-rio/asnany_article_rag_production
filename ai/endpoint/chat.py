from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Set
import json
import os
import re
from datetime import datetime
from pathlib import Path

from ai.chatbot.qdrant_retriever import retrieve_chunks
from ai.chatbot.sql_fetch import fetch_sources_by_ids
from ai.chatbot.reply import generate_reply, FALLBACK_TEXT

# ======================
# Router
# ======================

router = APIRouter()

# ======================
# Schemas
# ======================

class ChatRequest(BaseModel):
    query: str


class SourceItem(BaseModel):
    title: str
    url: str


class ChatResponse(BaseModel):
    reply: str
    sources: List[SourceItem] = []


# ======================
# Logging config
# ======================

ENABLE_CHAT_LOGS = os.getenv("ENABLE_CHAT_LOGS", "true").strip().lower() in ("1", "true", "yes", "on")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "chat_logs.jsonl"

if ENABLE_CHAT_LOGS:
    LOG_DIR.mkdir(exist_ok=True)


# ======================
# Constants
# ======================

# Expanded greeting list — includes Arabic variants with diacritics/alef forms
# and common English greetings.
_LOW_INTENT_GREETINGS_RAW = [
    "اهلا",
    "أهلا",
    "اهلاً",
    "أهلاً",
    "مرحبا",
    "مرحباً",
    "هلا",
    "السلام عليكم",
    "سلام عليكم",
    "السلامو عليكم",
    "صباح الخير",
    "مساء الخير",
    "هاي",
    "هلو",
    "hi",
    "hello",
    "hey",
    "good morning",
    "good evening",
]

MIN_QUERY_LENGTH = 6  # Prevent single letters like "ا"


# ======================
# Helpers
# ======================

def _normalize_for_greeting(text: str) -> str:
    """Return a cleaned, canonical form of *text* for greeting comparison.

    Steps:
    1. Lowercase + strip.
    2. Replace Arabic Alef variants (أ إ آ ٱ) → ا.
    3. Remove tatweel ـ.
    4. Strip common punctuation (ASCII and Arabic).
    5. Strip basic emoji ranges.
    6. Collapse repeated whitespace.
    """
    text = text.lower().strip()

    # Normalise Arabic Alef variants → bare alef
    text = re.sub(r"[أإآٱ]", "ا", text)

    # Remove tatweel
    text = text.replace("ـ", "")

    # Strip common punctuation (ASCII + Arabic punctuation)
    text = re.sub(r"[.،,!?؟؛:;'\"]+", "", text)

    # Strip basic emoji (Miscellaneous Symbols, Emoticons, etc.)
    text = re.sub(
        r"[\U0001F300-\U0001FAFF"   # Misc symbols & pictographs
        r"\U00002600-\U000027BF"    # Dingbats / misc symbols
        r"\U0000FE00-\U0000FE0F"    # Variation selectors
        r"\U00002300-\U000023FF]+", # Misc technical
        "",
        text,
    )

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


# Pre-normalise the greeting list once at import time.
_LOW_INTENT_GREETINGS_NORMALISED: List[str] = [
    _normalize_for_greeting(g) for g in _LOW_INTENT_GREETINGS_RAW
]


def is_low_intent_greeting(query: str) -> bool:
    """Return True iff *query* is a standalone greeting with no real question.

    Strategy:
    - Normalise the incoming query.
    - Check whether the full normalised query exactly matches a greeting,
      OR whether it starts with a greeting but contains very little additional
      text (≤ 2 extra tokens) — this catches "اهلا وسهلا" but NOT
      "مرحبا ما أسباب تسوس الأسنان؟".
    - A greeting followed by more than 2 non-empty tokens is treated as a
      real question and returns False.
    """
    normalised = _normalize_for_greeting(query)

    if not normalised:
        return False

    for greeting in _LOW_INTENT_GREETINGS_NORMALISED:
        if normalised == greeting:
            # Exact match — definitely a greeting.
            return True

        if normalised.startswith(greeting):
            # Check what follows the greeting.
            remainder = normalised[len(greeting):].strip()
            extra_tokens = [t for t in remainder.split() if t]
            # Allow at most 2 extra filler tokens (e.g. "وسهلا", "بكم")
            if len(extra_tokens) <= 2:
                return True

    return False


def log_chat_event(
    *,
    query: str,
    blog_ids: List[int],
    urls: List[str],
    reply: str,
):
    if not ENABLE_CHAT_LOGS:
        return

    try:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "query": query,
            "retrieved_blog_ids": blog_ids,
            "retrieved_chunks_count": len(blog_ids),
            "urls_count": len(urls),
            "fallback_used": reply.strip() == FALLBACK_TEXT,
            "response_length": len(reply),
        }

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    except Exception as e:
        # NEVER crash API because of logging
        print(f"⚠️ Logging failed: {e}")

def _dedupe_ints_keep_order(values: List[int]) -> List[int]:
    out: List[int] = []
    seen: Set[int] = set()
    for v in values:
        try:
            i = int(v)
        except Exception:
            continue
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


# ======================
# Endpoint
# ======================

@router.post("/", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest) -> Dict[str, Any]:
    query = (payload.query or "").strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="query cannot be empty",
        )

    # Detect user language once — reused by all early-exit replies below.
    _query_has_arabic = bool(re.search(r'[\u0600-\u06FF]', query))

    # 1️⃣ Greeting handler — runs BEFORE short-query rejection so that
    #    short greetings like "hi" are answered gracefully.
    if is_low_intent_greeting(query):
        _greeting_reply = (
            "مرحبًا بك 👋 يمكنك سؤالي عن أي موضوع يخص الأسئلة الطبية وسأحاول مساعدتك."
            if _query_has_arabic
            else "Welcome! 👋 Feel free to ask me any medical question and I'll do my best to help."
        )
        return {"reply": _greeting_reply, "sources": []}

    # 2️⃣ Reject very short meaningless inputs
    if len(query) < MIN_QUERY_LENGTH:
        _short_reply = (
            "يرجى كتابة سؤال واضح يتعلق بالمجال الطبي 😊"
            if _query_has_arabic
            else "Please write a clear medical question 😊"
        )
        return {"reply": _short_reply, "sources": []}

    # 3️⃣ Retrieve chunks from Qdrant
    try:
        hits = retrieve_chunks(query)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"retriever failed: {e}",
        )

    if not hits:
        _no_results_reply = (
            "يمكنني مساعدتك في الأسئلة المتعلقة بالمواضيع الطبية فقط 😊"
            if _query_has_arabic
            else "I can only help with medical and dental questions 😊"
        )
        return {"reply": _no_results_reply, "sources": []}

    # 4️⃣ Extract chunk_text + blog_ids
    chunks: List[str] = []
    blog_ids: List[int] = []

    for h in hits:
        chunk_text = (h.get("chunk_text") or "").strip()
        blog_id = h.get("blog_id")

        if chunk_text:
            chunks.append(chunk_text)

        if blog_id is not None:
            try:
                blog_ids.append(int(blog_id))
            except Exception:
                pass

    blog_ids = _dedupe_ints_keep_order(blog_ids)

    # 5️⃣ Fetch structured sources
    try:
        sources = fetch_sources_by_ids(blog_ids) if blog_ids else []
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"database fetch failed: {e}",
        )

    # 6️⃣ Generate final structured answer
    try:
        result = generate_reply(
            user_query=query,
            chunks=chunks,
            sources=sources,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"reply generation failed: {e}",
        )

    # 7️⃣ Logging (نخلي اللوج زي ما هو تقريبًا)
    log_chat_event(
        query=query,
        blog_ids=blog_ids,
        urls=[s["url"] for s in result.get("sources", [])],
        reply=result.get("reply", ""),
    )

    return result
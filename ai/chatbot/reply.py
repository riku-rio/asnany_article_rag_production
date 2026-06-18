from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import re

import requests
from dotenv import load_dotenv

# ======================
# Load ENV
# ======================
load_dotenv()

# ======================
# ENV
# ======================
GROQ_TOKEN = os.getenv("GROQ_TOKEN")
GROQ_MODEL = os.getenv("GROQ_MODEL")

GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_TIMEOUT = int(os.getenv("GROQ_TIMEOUT", 60))

# Budget
GROQ_MAX_COMPLETION_TOKENS = int(os.getenv("GROQ_MAX_COMPLETION_TOKENS", 500))
GROQ_TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", 0.2))

# Context safety (chars)
CONTEXT_MAX_CHARS = int(os.getenv("CONTEXT_MAX_CHARS", 10000))

# We reuse ARTICLE_MAX_CHARS as "per-chunk max chars" to avoid changing env names
ARTICLE_MAX_CHARS = int(os.getenv("ARTICLE_MAX_CHARS", 2000))

def _lang_reply(query: str, arabic_text: str, english_text: str) -> str:
    """Return arabic_text if query contains Arabic characters, else english_text."""
    return arabic_text if re.search(r'[\u0600-\u06FF]', query or "") else english_text


# UI strings
READ_MORE_HEADER = "لقراءة المزيد:"
FALLBACK_TEXT_AR = "لا أستطيع الإجابة من المعلومات المتاحة."
FALLBACK_TEXT_EN = "I'm unable to answer from the available information."
DAILY_LIMIT_AR = "تم استهلاك الحد المتاح للاستخدام حاليًا. يرجى المحاولة لاحقًا."
DAILY_LIMIT_EN = "The daily usage limit has been reached. Please try again later."
TRANSIENT_ERROR_AR = "حصلت مشكلة مؤقتة في الخدمة. حاول مرة أخرى بعد قليل."
TRANSIENT_ERROR_EN = "A temporary service error occurred. Please try again shortly."

# Keep a default FALLBACK_TEXT constant for backward-compatible import in chat.py
FALLBACK_TEXT = FALLBACK_TEXT_AR

# ======================
# Prompt Path (required)
# ======================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_PROMPT_PATH = PROJECT_ROOT / "ai" / "prompt" / "system_prompt.txt"


def _clean_text(text: str) -> str:
    # إزالة التشكيل
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)
    # إزالة المدّات الطويلة
    text = re.sub(r'ـ{2,}', 'ـ', text)
    return text.strip()

# ======================
# Legacy validation (optional / transitional)
# ======================
def _validate_legacy_sql_fetch_shape(data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Legacy shape (V1):
    {
      "reply": [
        {"title": "...", "content": "...", "url": "..."}
      ]
    }
    """
    if not isinstance(data, dict):
        raise TypeError("reply payload must be a dict")

    if set(data.keys()) != {"reply"}:
        raise ValueError("reply payload must contain ONLY the 'reply' key")

    reply = data.get("reply")
    if not isinstance(reply, list):
        raise TypeError("'reply' must be a list")

    articles: List[Dict[str, str]] = []
    for i, item in enumerate(reply):
        if not isinstance(item, dict):
            raise TypeError(f"reply[{i}] must be an object")

        if set(item.keys()) != {"title", "content", "url"}:
            raise ValueError(f"reply[{i}] must contain ONLY: title, content, url")

        title = item.get("title")
        content = item.get("content")
        url = item.get("url")

        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"reply[{i}].title must be a non-empty string")
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"reply[{i}].content must be a non-empty string")
        if not isinstance(url, str) or not url.strip():
            raise ValueError(f"reply[{i}].url must be a non-empty string")

        articles.append(
            {
                "title": title.strip(),
                "content": content.strip(),
                "url": url.strip(),
            }
        )

    return articles


def _load_system_prompt() -> str:
    if not SYSTEM_PROMPT_PATH.exists():
        raise FileNotFoundError(f"system_prompt.txt not found: {SYSTEM_PROMPT_PATH}")

    txt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    if not txt:
        raise RuntimeError("system_prompt.txt is empty")

    return txt


# ======================
# Context Building (Chunks)
# ======================
def _build_context_from_chunks(chunks: List[str]) -> str:
    """
    Build context using ONLY chunk_text (NO URLs).
    Apply char limits for safety.
    """
    blocks: List[str] = []
    used = 0

    for idx, chunk in enumerate(chunks, start=1):
        c = (chunk or "").strip()
        if not c:
            continue

        if len(c) > ARTICLE_MAX_CHARS:
            c = c[:ARTICLE_MAX_CHARS].rstrip()

        block = f"[CHUNK {idx}]\nTEXT:\n{c}\n"

        if used + len(block) > CONTEXT_MAX_CHARS:
            remaining = max(CONTEXT_MAX_CHARS - used, 0)
            if remaining <= 0:
                break
            blocks.append(block[:remaining].rstrip())
            break

        blocks.append(block)
        used += len(block)

    return "\n\n".join(blocks).strip()


def _dedupe_urls(urls: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for u in urls:
        u = (u or "").strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


# ======================
# Groq helpers
# ======================
def _safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return None


def _error_to_text(err_obj: Any, fallback: str) -> str:
    if err_obj is None:
        return fallback or ""
    if isinstance(err_obj, str):
        return err_obj
    try:
        return json.dumps(err_obj, ensure_ascii=False)
    except Exception:
        return str(err_obj)


def _looks_like_quota_error(err_text_lower: str) -> bool:
    quota_signals = [
        "insufficient_quota",
        "quota_exceeded",
        "exceeded your current quota",
        "out of credits",
        "not enough credits",
        "billing",
        "payment required",
        "credit",
        "credits",
    ]
    if "daily" in err_text_lower and "limit" in err_text_lower:
        return True
    return any(sig in err_text_lower for sig in quota_signals)


def _looks_like_rate_limit(err_text_lower: str) -> bool:
    rate_signals = [
        "rate_limit",
        "rate limit",
        "too many requests",
        "tpm",
        "rpm",
        "requests per",
        "tokens per",
        "capacity",
        "overloaded",
    ]
    return any(sig in err_text_lower for sig in rate_signals)


# ======================
# Groq Chat Call (robust)
# ======================
def _call_groq_chat(
    system_prompt: str,
    user_message: str,
    *,
    max_completion_tokens: int,
    temperature: float,
) -> str:
    if not GROQ_TOKEN:
        raise RuntimeError("GROQ_TOKEN is not set in .env")
    if not GROQ_MODEL:
        raise RuntimeError("GROQ_MODEL is not set in .env")

    _daily_limit_msg = _lang_reply(user_message, DAILY_LIMIT_AR, DAILY_LIMIT_EN)
    _transient_error_msg = _lang_reply(user_message, TRANSIENT_ERROR_AR, TRANSIENT_ERROR_EN)

    url = f"{GROQ_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_completion_tokens": int(max_completion_tokens),
        "temperature": float(temperature),
    }

    transient_statuses = {429, 502, 503, 504}
    max_attempts = 4
    last_err_text: str = ""

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=(10, GROQ_TIMEOUT),
            )
        except requests.RequestException as e:
            last_err_text = f"network error: {e}"
            if attempt < max_attempts:
                time.sleep(0.6 * attempt)
                continue
            print(f"⚠️ Groq transient failure: {last_err_text}")
            return _transient_error_msg

        # Success
        if resp.status_code == 200:
            data = _safe_json(resp)
            if not isinstance(data, dict):
                print(f"⚠️ Groq returned non-JSON: {resp.text[:800]}")
                return _transient_error_msg

            try:
                content = data["choices"][0]["message"]["content"]
            except Exception:
                print(f"⚠️ Unexpected Groq response shape: {str(data)[:1200]}")
                return TRANSIENT_ERROR_MESSAGE

            if content is None:
                return ""
            if not isinstance(content, str):
                print("[!] Groq returned non-text content")
                return TRANSIENT_ERROR_MESSAGE

            return content.strip()

        # Error handling
        err_obj = _safe_json(resp)
        err_text = _error_to_text(err_obj, resp.text[:1200])
        err_lower = (err_text or "").lower()
        last_err_text = f"HTTP {resp.status_code}: {err_text}"

        # 429 is NOT always daily quota
        if resp.status_code == 429:
            if _looks_like_quota_error(err_lower):
                print(f"⚠️ Groq quota exhausted: {last_err_text}")
                return _daily_limit_msg

            retry_after = resp.headers.get("retry-after")
            if attempt < max_attempts:
                base = 0.9 * attempt
                if retry_after:
                    try:
                        base = max(base, float(retry_after))
                    except Exception:
                        pass
                time.sleep(base + random.uniform(0.0, 0.25))
                continue

            print(f"⚠️ Groq rate limit: {last_err_text}")
            return _transient_error_msg

        if resp.status_code in transient_statuses:
            if attempt < max_attempts:
                time.sleep(0.8 * attempt + random.uniform(0.0, 0.25))
                continue
            print(f"⚠️ Groq transient error: {last_err_text}")
            return TRANSIENT_ERROR_MESSAGE

        # Non-transient errors should be visible (config / model / payload issues)
        raise RuntimeError(f"Groq API error ({resp.status_code}): {err_text}")

    print(f"⚠️ Groq unknown failure: {last_err_text}")
    return _transient_error_msg


def generate_reply(
    user_query: str,
    *,
    chunks: List[str],
    sources: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Clean V3

    Input:
        user_query: سؤال المستخدم
        chunks: نصوص مسترجعة (بدون روابط)
        sources: [
            {"title": "...", "url": "..."}
        ]

    Output:
        {
            "reply": str,
            "sources": [...]
        }
    """

    # ======================
    # Validation
    # ======================
    if not isinstance(user_query, str) or not user_query.strip():
        raise ValueError("user_query must be a non-empty string")

    if not isinstance(chunks, list) or not any(
        isinstance(c, str) and c.strip() for c in chunks
    ):
        return {
            "reply": FALLBACK_TEXT,
            "sources": []
        }

    # ======================
    # Clean chunks
    # ======================
    final_chunks: List[str] = []

    for c in chunks:
        if isinstance(c, str) and c.strip():
            final_chunks.append(c.strip())

    if not final_chunks:
        return {
            "reply": FALLBACK_TEXT,
            "sources": []
        }

    context = _build_context_from_chunks(final_chunks)

    # ======================
    # Build LLM prompt
    # ======================
    system_prompt = _load_system_prompt()

    # Detect user language: if the query contains Arabic characters, respond in Arabic;
    # otherwise respond in English.
    _has_arabic = bool(re.search(r'[\u0600-\u06FF]', user_query))
    _answer_instruction = (
        "أجب بالعربية بشكل واضح ومباشر:"
        if _has_arabic
        else "Answer clearly and directly in English:"
    )

    user_message = (
        "<question>\n"
        f"{user_query.strip()}\n"
        "</question>\n\n"
        "<context>\n"
        f"{context}\n"
        "</context>\n\n"
        f"{_answer_instruction}"
    )

    # ======================
    # Call model
    # ======================
    answer = _call_groq_chat(
        system_prompt=system_prompt,
        user_message=user_message,
        max_completion_tokens=GROQ_MAX_COMPLETION_TOKENS,
        temperature=GROQ_TEMPERATURE,
    )

    if not answer:
        answer = _lang_reply(user_query, FALLBACK_TEXT_AR, FALLBACK_TEXT_EN)

    answer = _clean_text(answer)

    # ======================
    # Clean & dedupe sources
    # ======================
    final_sources: List[Dict[str, str]] = []
    seen_urls = set()

    if sources:
        for src in sources:
            if not isinstance(src, dict):
                continue

            title = (src.get("title") or "").strip()
            url = (src.get("url") or "").strip()

            if not title or not url:
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)

            final_sources.append({
                "title": title,
                "url": url
            })

    # ======================
    # Final structured response
    # ======================
    return {
        "reply": answer,
        "sources": final_sources
    }
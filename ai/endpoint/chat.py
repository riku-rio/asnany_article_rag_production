from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Set
import json
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


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "chat_logs.jsonl"

LOG_DIR.mkdir(exist_ok=True)


# ======================
# Constants
# ======================

LOW_INTENT_GREETINGS = [
    "اهلا",
    "مرحبا",
    "السلام عليكم",
    "hi",
    "hello"
]

MIN_QUERY_LENGTH = 6  # Prevent single letters like "ا"


# ======================
# Helpers
# ======================

def log_chat_event(
    *,
    query: str,
    blog_ids: List[int],
    urls: List[str],
    reply: str,
):
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

    normalized_query = query.lower()

    # 1️⃣ Reject very short meaningless inputs
    if len(normalized_query) < MIN_QUERY_LENGTH:
        return {
            "reply": "يرجى كتابة سؤال واضح يتعلق بالمجال الطبي 😊",
            "sources": []
        }

    # 2️⃣ Greeting handler
    if any(greet in normalized_query for greet in LOW_INTENT_GREETINGS):
        return {
            "reply": "مرحبًا بك 👋 يمكنك سؤالي عن أي موضوع يخص الأسئلة الطبية وسأحاول مساعدتك.",
            "sources": []
        }

    # 3️⃣ Retrieve chunks from Qdrant
    try:
        hits = retrieve_chunks(query)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"retriever failed: {e}",
        )

    if not hits:
        return {
            "reply": "يمكنني مساعدتك في الأسئلة المتعلقة بالمواضيع الطبية فقط 😊",
            "sources": []
        }

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
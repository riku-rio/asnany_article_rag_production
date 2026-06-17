from typing import Any, Dict, List, Set

from fastapi import APIRouter, HTTPException

from ai.chatbot.qdrant_retriever import retrieve_chunks
from ai.chatbot.reply import generate_reply
from ai.chatbot.sql_fetch import fetch_sources_by_ids
from ai.endpoint.chat import is_low_intent_greeting, MIN_QUERY_LENGTH

from database.admin_service import (
    add_knowledge_from_url,
    get_stats,
    list_knowledge,
    get_knowledge,
    delete_knowledge,
    get_logs,
    check_health,
    run_scraper,
    run_embedding,
    rebuild_everything,
)

router = APIRouter()


@router.post("/scrape")
def scrape():
    try:
        return run_scraper()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embedding")
def embedding():
    try:
        return run_embedding()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rebuild")
def rebuild():
    try:
        return rebuild_everything()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
def stats():
    try:
        return get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge")
def knowledge_list():
    try:
        return list_knowledge()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge/{id}")
def knowledge_detail(id: int):
    try:
        item = get_knowledge(id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return item


@router.delete("/knowledge/{id}")
def knowledge_delete(id: int):
    try:
        deleted = delete_knowledge(id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return {"success": True, "message": "Knowledge deleted"}


@router.post("/knowledge/add-url")
def knowledge_add_url(payload: Dict[str, Any]):
    url = (payload.get("url") or "").strip()
    return add_knowledge_from_url(url)


@router.get("/logs")
def logs(limit: int = 50):
    capped = min(limit, 200)
    try:
        return get_logs(limit=capped)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat-test")
def chat_test(payload: Dict[str, Any]):
    query = (payload.get("query") or "").strip()

    if not query:
        raise HTTPException(status_code=400, detail="query cannot be empty")

    # 1 — Greeting check
    if is_low_intent_greeting(query):
        return {
            "reply": "مرحبًا بك 👋 يمكنك سؤالي عن أي موضوع يخص الأسئلة الطبية وسأحاول مساعدتك.",
            "sources": [],
        }

    # 2 — Short query rejection
    if len(query) < MIN_QUERY_LENGTH:
        return {
            "reply": "يرجى كتابة سؤال واضح يتعلق بالمجال الطبي 😊",
            "sources": [],
        }

    # 3 — Retrieve chunks from Qdrant
    try:
        hits = retrieve_chunks(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"retriever failed: {e}")

    if not hits:
        return {
            "reply": "يمكنني مساعدتك في الأسئلة المتعلقة بالمواضيع الطبية فقط 😊",
            "sources": [],
        }

    # 4 — Extract chunk_text + blog_ids
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

    # 5 — Fetch structured sources
    try:
        sources = fetch_sources_by_ids(blog_ids) if blog_ids else []
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"database fetch failed: {e}"
        )

    # 6 — Generate final structured answer
    try:
        result = generate_reply(
            user_query=query,
            chunks=chunks,
            sources=sources,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"reply generation failed: {e}"
        )

    return result


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


@router.get("/health")
def health():
    return check_health()

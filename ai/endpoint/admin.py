import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Set

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from ai.chatbot.qdrant_retriever import retrieve_chunks
from ai.chatbot.reply import generate_reply
from ai.chatbot.sql_fetch import fetch_sources_by_ids
from ai.endpoint.chat import is_low_intent_greeting, MIN_QUERY_LENGTH

from database.admin_service import (
    add_knowledge_from_url,
    authenticate_user,
    check_health,
    create_user,
    delete_knowledge,
    delete_user,
    get_knowledge,
    get_logs,
    get_stats,
    get_user_by_id,
    list_knowledge,
    list_users,
    rebuild_everything,
    reset_user_password,
    run_embedding,
    run_scraper,
    update_user,
)
from database.dashboard_logger import log_event

# ======================
# JWT Session helpers
# ======================

_SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY") or secrets.token_hex(32)
_JWT_ALGORITHM = "HS256"
_COOKIE_NAME = "dashboard_session"
_SESSION_DURATION = timedelta(hours=24)


def _create_session_token(user_id: int, role: str) -> str:
    exp = datetime.now(timezone.utc) + _SESSION_DURATION
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": exp,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=_JWT_ALGORITHM)


def _set_session_cookie(response: JSONResponse, token: str) -> None:
    is_production = os.getenv("ENV", "").lower() == "production"
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=is_production,
        max_age=int(_SESSION_DURATION.total_seconds()),
        path="/",
    )


def _clear_session_cookie(response: JSONResponse) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value="",
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=0,
        path="/",
    )


# ======================
# Auth dependency
# ======================


def require_auth(request: Request) -> dict:
    token = request.cookies.get(_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"success": False, "message": "Authentication required"},
        )
    try:
        payload = jwt.decode(
            token, _SECRET_KEY, algorithms=[_JWT_ALGORITHM]
        )
        user_id = payload.get("user_id")
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={"success": False, "message": "Authentication required"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail={"success": False, "message": "Authentication required"},
        )

    user = get_user_by_id(user_id)
    if not user or not user["is_active"]:
        raise HTTPException(
            status_code=401,
            detail={"success": False, "message": "Authentication required"},
        )
    return user


# ======================
# Routers
# ======================

auth_router = APIRouter()
router = APIRouter(dependencies=[Depends(require_auth)])


# ======================
# Auth endpoints (public)
# ======================


@auth_router.post("/auth/login")
def login(payload: Dict[str, Any]):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if not username or not password:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Invalid username or password",
            },
        )

    user = authenticate_user(username, password)
    if not user:
        log_event("login_failed", f"Failed login attempt for '{username.lower()}'")
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "message": "Invalid username or password",
            },
        )

    token = _create_session_token(user["id"], user["role"])
    response = JSONResponse(
        content={
            "success": True,
            "message": "Logged in successfully",
            "user": user,
        }
    )
    _set_session_cookie(response, token)

    log_event(
        "user_logged_in",
        f"User '{user['username']}' ({user['role']}) logged in",
    )

    return response


# ======================
# Auth endpoints (protected)
# ======================


@router.post("/auth/logout")
def logout(user: dict = Depends(require_auth)):
    log_event(
        "user_logged_out",
        f"User '{user['username']}' ({user['role']}) logged out",
    )
    response = JSONResponse(
        content={"success": True, "message": "Logged out successfully"}
    )
    _clear_session_cookie(response)
    return response


@router.get("/auth/me")
def me(user: dict = Depends(require_auth)):
    return {
        "success": True,
        "user": {
            "id": user["id"],
            "display_name": user["display_name"],
            "username": user["username"],
            "role": user["role"],
        },
    }


# ======================
# User management endpoints
# ======================


@router.get("/users")
def users_list(user: dict = Depends(require_auth)):
    return list_users()


@router.post("/users")
def users_create(
    payload: Dict[str, Any], user: dict = Depends(require_auth)
):
    display_name = (payload.get("display_name") or "").strip()
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    role = (payload.get("role") or "admin").strip().lower()

    success, message = create_user(
        display_name=display_name,
        username=username,
        password=password,
        role=role,
        created_by_role=user["role"],
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.patch("/users/{user_id}")
def users_update(
    user_id: int,
    payload: Dict[str, Any],
    current_user: dict = Depends(require_auth),
):
    success, message = update_user(
        user_id=user_id,
        data=payload,
        current_user_role=current_user["role"],
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.post("/users/{user_id}/reset-password")
def users_reset_password(
    user_id: int,
    payload: Dict[str, Any],
    current_user: dict = Depends(require_auth),
):
    new_password = payload.get("password") or ""
    success, message = reset_user_password(
        user_id=user_id,
        new_password=new_password,
        current_user_role=current_user["role"],
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@router.delete("/users/{user_id}")
def users_delete(
    user_id: int,
    current_user: dict = Depends(require_auth),
):
    success, message = delete_user(
        user_id=user_id,
        current_user_role=current_user["role"],
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


# ======================
# Existing operational endpoints (now protected)
# ======================


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

    if is_low_intent_greeting(query):
        return {
            "reply": "مرحبًا بك 👋 يمكنك سؤالي عن أي موضوع يخص الأسئلة الطبية وسأحاول مساعدتك.",
            "sources": [],
        }

    if len(query) < MIN_QUERY_LENGTH:
        return {
            "reply": "يرجى كتابة سؤال واضح يتعلق بالمجال الطبي 😊",
            "sources": [],
        }

    try:
        hits = retrieve_chunks(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"retriever failed: {e}")

    if not hits:
        return {
            "reply": "يمكنني مساعدتك في الأسئلة المتعلقة بالمواضيع الطبية فقط 😊",
            "sources": [],
        }

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

    try:
        sources = fetch_sources_by_ids(blog_ids) if blog_ids else []
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"database fetch failed: {e}"
        )

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


@router.get("/health")
def health():
    return check_health()


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

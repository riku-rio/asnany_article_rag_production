import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

import bcrypt

import requests
from qdrant_client import QdrantClient, models

from database.db import get_connection
from database.dashboard_logger import log_event
from database.qdrant_uploader import QDRANT_COLLECTION

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "scraper" / "articles.csv"

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_TOKEN = os.getenv("QDRANT_TOKEN")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

# ======================
# Per-job status system
# ======================

_JOB_INIT = {
    "scrape": {"type": "scrape", "status": "idle", "progress": 0, "message": "", "logs": [], "started_at": None, "finished_at": None, "error": None, "total_items": 0, "completed_items": 0},
    "embedding": {"type": "embedding", "status": "idle", "progress": 0, "message": "", "logs": [], "started_at": None, "finished_at": None, "error": None, "total_items": 0, "completed_items": 0},
    "rebuild": {"type": "rebuild", "status": "idle", "progress": 0, "message": "", "logs": [], "started_at": None, "finished_at": None, "error": None, "total_items": 0, "completed_items": 0},
}

_job_statuses: Dict[str, Dict[str, Any]] = {k: dict(v) for k, v in _JOB_INIT.items()}
_jobs_lock = threading.Lock()


def get_job_status(job_type: str) -> Dict[str, Any]:
    with _jobs_lock:
        status = _job_statuses.get(job_type)
        if not status:
            init = _JOB_INIT.get(job_type, {"type": job_type, "status": "idle", "progress": 0, "message": "", "logs": [], "started_at": None, "finished_at": None, "error": None, "total_items": 0, "completed_items": 0})
            return dict(init)
        # Return a copy so callers don't modify internal state
        return {
            "type": status["type"],
            "status": status["status"],
            "progress": status["progress"],
            "message": status["message"],
            "logs": list(status["logs"]),
            "started_at": status["started_at"],
            "finished_at": status["finished_at"],
            "error": status["error"],
            "total_items": status.get("total_items", 0),
            "completed_items": status.get("completed_items", 0),
        }


def _init_job(job_type: str) -> None:
    with _jobs_lock:
        _job_statuses[job_type] = {
            "type": job_type,
            "status": "running",
            "progress": 0,
            "message": "",
            "logs": [{"timestamp": datetime.now(timezone.utc).isoformat(), "message": "Starting..."}],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "error": None,
            "total_items": 0,
            "completed_items": 0,
        }


def _update_job_progress(job_type: str, progress: int, message: str = "") -> None:
    with _jobs_lock:
        s = _job_statuses.get(job_type)
        if s and s["status"] == "running":
            s["progress"] = min(progress, 100)
            if message:
                s["message"] = message


def _add_job_log(job_type: str, log_line: str) -> None:
    with _jobs_lock:
        s = _job_statuses.get(job_type)
        if s and s["status"] == "running":
            s["logs"].append({"timestamp": datetime.now(timezone.utc).isoformat(), "message": log_line})


def _finish_job(job_type: str, success: bool = True, error: str = "") -> None:
    with _jobs_lock:
        s = _job_statuses.get(job_type)
        if s and s["status"] == "running":
            s["status"] = "success" if success else "error"
            s["progress"] = 100
            s["finished_at"] = datetime.now(timezone.utc).isoformat()
            if error:
                s["error"] = error
                s["logs"].append({"timestamp": s["finished_at"], "message": f"Error: {error}"})
            else:
                s["logs"].append({"timestamp": s["finished_at"], "message": "Completed"})


def _update_job_items(job_type: str, *, total_items: Optional[int] = None, completed_items: Optional[int] = None) -> None:
    with _jobs_lock:
        s = _job_statuses.get(job_type)
        if s and s["status"] == "running":
            if total_items is not None:
                s["total_items"] = total_items
            if completed_items is not None:
                s["completed_items"] = completed_items


def _update_job_message(job_type: str, message: str) -> None:
    with _jobs_lock:
        s = _job_statuses.get(job_type)
        if s and s["status"] == "running" and message:
            s["message"] = message


def _make_job_callback(job_type: str) -> Callable:
    """Return a callback (progress, message, log, total_items, completed_items) for background jobs."""
    def cb(*, progress: Optional[int] = None, message: str = "", log: str = "", total_items: Optional[int] = None, completed_items: Optional[int] = None) -> None:
        if progress is not None:
            _update_job_progress(job_type, progress, message)
        elif message:
            _update_job_message(job_type, message)
        if log:
            _add_job_log(job_type, log)
        if total_items is not None or completed_items is not None:
            _update_job_items(job_type, total_items=total_items, completed_items=completed_items)
    return cb

_qdrant_client: Optional[QdrantClient] = None


def _get_qdrant_client() -> Optional[QdrantClient]:
    global _qdrant_client
    if _qdrant_client is not None:
        return _qdrant_client
    if not QDRANT_URL:
        return None
    try:
        _qdrant_client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_TOKEN,
            timeout=10,
            check_compatibility=False,
        )
        return _qdrant_client
    except Exception:
        return None


def _query_scalar(sql: str, params: tuple = ()):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return list(row.values())[0] if row else None
    except Exception:
        return None
    finally:
        conn.close()


def _query_list(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()
    except Exception:
        return []
    finally:
        conn.close()


# ======================
# Background job helpers
# ======================

_JOB_RUNNING_FLAGS: Dict[str, threading.Lock] = {
    "scrape": threading.Lock(),
    "embedding": threading.Lock(),
    "rebuild": threading.Lock(),
}


def _start_job(job_type: str, target_func: Callable) -> Dict[str, Any]:
    lock = _JOB_RUNNING_FLAGS[job_type]
    if not lock.acquire(blocking=False):
        return {"status": "busy", "message": f"This operation is already running"}
    try:
        _init_job(job_type)
        thread = threading.Thread(target=lambda: _run_job(job_type, target_func), daemon=True)
        thread.start()
        return {"success": True, "message": "Job started in background"}
    except Exception:
        lock.release()
        raise


def _run_job(job_type: str, target_func: Callable) -> None:
    lock = _JOB_RUNNING_FLAGS[job_type]
    try:
        target_func()
    except Exception as e:
        print(f"Background job {job_type} failed: {e}")
        _finish_job(job_type, success=False, error=str(e))
    finally:
        lock.release()


def _reset_all_is_embedded():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE blog SET is_embedded = 0;")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ======================
# Scraper
# ======================

def run_scraper():
    def _scrape():
        from database.database_server import (
            insert_blog_article,
            load_known_urls_from_db,
        )
        from scraper.asnany_scraper import scrape_all_articles

        try:
            cb = _make_job_callback("scrape")
            cb(progress=5, message="Checking pages...", log="Starting content import...")
            known_urls = load_known_urls_from_db()
            cb(log=f"Found {len(known_urls)} existing articles")

            scrape_all_articles(
                known_urls,
                csv_path=CSV_PATH,
                total_pages=0,
                sleep_seconds=0.3,
                on_article=insert_blog_article,
                write_csv=False,
                progress_callback=cb,
            )
            log_event("scraper_completed", "Scraper completed successfully")
            _finish_job("scrape", success=True)
        except Exception as e:
            log_event("scraper_failed", f"Scraper failed: {e}")
            _finish_job("scrape", success=False, error=str(e))

    return _start_job("scrape", _scrape)


# ======================
# Embedding
# ======================

def run_embedding():
    def _embed():
        from database.database_server import (
            embed_and_upload_blog_articles,
            export_blog_to_csv,
        )

        try:
            cb = _make_job_callback("embedding")
            log_event("embedding_started", "Embedding triggered from dashboard")

            cb(log="Counting pending content items...")
            pending = _query_scalar("SELECT COUNT(*) FROM blog WHERE is_embedded = 0") or 0

            if pending == 0:
                cb(progress=100, message="No new content to process", total_items=0, completed_items=0, log="No new content to process")
                log_event("embedding_completed", "No new content to process")
                _finish_job("embedding", success=True)
                return

            cb(progress=0, message=f"Processing 0 / {pending} items", total_items=pending, completed_items=0, log=f"Found {pending} pending content items")

            cb(log="Backing up content to CSV...")
            export_blog_to_csv(CSV_PATH)

            cb(log="Processing content...")
            embed_and_upload_blog_articles(progress_callback=cb)

            log_event("embedding_completed", "Embedding completed successfully")
            _finish_job("embedding", success=True)
        except Exception as e:
            log_event("embedding_failed", f"Embedding failed: {e}")
            _finish_job("embedding", success=False, error=str(e))

    return _start_job("embedding", _embed)


# ======================
# Rebuild
# ======================

def rebuild_everything():
    def _rebuild():
        from database.database_server import embed_and_upload_blog_articles

        try:
            cb = _make_job_callback("rebuild")
            log_event("rebuild_started", "Rebuild triggered from dashboard")

            total = _query_scalar("SELECT COUNT(*) FROM blog") or 0

            cb(progress=5, message="Resetting processed content...", total_items=total, completed_items=0, log=f"Reset {total} content items...")
            _reset_all_is_embedded()

            cb(progress=10, message="Clearing AI search index...", log="Clearing AI search index...")

            if total == 0:
                cb(progress=100, message="No content to rebuild", log="No content to rebuild")
                log_event("rebuild_completed", "No content to rebuild")
                _finish_job("rebuild", success=True)
                return

            cb(progress=10, message=f"Reprocessing 0 / {total} items", total_items=total, completed_items=0, log="Reprocessing content...")
            embed_and_upload_blog_articles(progress_callback=cb)

            log_event("rebuild_completed", "Rebuild completed successfully")
            _finish_job("rebuild", success=True)
        except Exception as e:
            log_event("rebuild_failed", f"Rebuild failed: {e}")
            _finish_job("rebuild", success=False, error=str(e))

    return _start_job("rebuild", _rebuild)


# ======================
# Stats
# ======================

def get_stats() -> Dict[str, Any]:
    total = _query_scalar("SELECT COUNT(*) FROM blog") or 0
    embedded = _query_scalar("SELECT COUNT(*) FROM blog WHERE is_embedded = 1") or 0
    pending = _query_scalar("SELECT COUNT(*) FROM blog WHERE is_embedded = 0") or 0

    questions = _query_scalar("SELECT COUNT(*) FROM chat_logs") or 0

    last_embedding = _query_scalar(
        "SELECT created_at FROM dashboard_logs WHERE event_type = 'embedding_completed' ORDER BY created_at DESC LIMIT 1"
    )
    last_scraping = _query_scalar(
        "SELECT created_at FROM dashboard_logs WHERE event_type = 'scraper_completed' ORDER BY created_at DESC LIMIT 1"
    )

    return {
        "total_articles": total,
        "embedded_articles": embedded,
        "pending_articles": pending,
        "questions_count": questions,
        "last_embedding": last_embedding,
        "last_scraping": last_scraping,
    }


# ======================
# Knowledge
# ======================

def list_knowledge() -> List[Dict[str, Any]]:
    return _query_list(
        "SELECT id, title, url, is_embedded, created_at FROM blog ORDER BY id DESC"
    )


def get_knowledge(article_id: int) -> Optional[Dict[str, Any]]:
    rows = _query_list(
        "SELECT id, title, url, content, is_embedded FROM blog WHERE id = %s",
        (article_id,),
    )
    return rows[0] if rows else None


def delete_knowledge(article_id: int) -> bool:
    client = _get_qdrant_client()
    if client is not None:
        try:
            client.delete(
                collection_name=QDRANT_COLLECTION,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="blog_id",
                                match=models.MatchValue(value=article_id),
                            )
                        ]
                    )
                ),
            )
        except Exception as e:
            print(f"Warning: Qdrant delete failed for blog_id={article_id}: {e}")

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM blog WHERE id = %s", (article_id,))
            deleted = cursor.rowcount > 0
        conn.commit()
        if deleted:
            log_event(
                "knowledge_deleted",
                f"Knowledge article {article_id} deleted",
                conn=conn,
            )
            conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ======================
# Add Knowledge (single URL scrape + embed)
# ======================

def add_knowledge_from_url(url: str) -> Dict[str, Any]:
    url = url.strip()
    if not url:
        return {"success": False, "message": "URL is required"}

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return {"success": False, "message": "Invalid URL format"}
    if parsed.scheme not in ("http", "https"):
        return {"success": False, "message": "URL must start with http:// or https://"}

    from database.database_server import load_known_urls_from_db
    from scraper.asnany_scraper import normalize_url

    norm_url = normalize_url(url)
    known = load_known_urls_from_db()
    if norm_url in known:
        return {"success": False, "message": "Knowledge already exists"}

    from scraper.asnany_scraper import scrape_article

    try:
        article = scrape_article(url)
    except Exception as e:
        return {"success": False, "message": f"Failed to scrape URL: {e}"}

    title = (article.get("title") or "").strip()
    content = (article.get("content") or "").strip()
    if not title or not content:
        return {"success": False, "message": "Scraped article has no content"}

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO blog (title, url, content) VALUES (%s, %s, %s)",
                (title, norm_url, content),
            )
            article_id = cursor.lastrowid
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return {"success": False, "message": f"Failed to save article: {e}"}

    if article_id is None or article_id == 0:
        conn.close()
        return {"success": False, "message": "Failed to save article"}

    from database.embedder import chunk_text, get_model
    from database.qdrant_uploader import upload_embeddings

    try:
        chunks = chunk_text(content)
        if not chunks:
            conn.close()
            return {"success": False, "message": "No content to embed"}

        model = get_model()
        passages = []
        meta = []
        for idx, chunk in enumerate(chunks):
            passages.append(f"passage: {title}\n\n{chunk}")
            meta.append((article_id, idx, chunk))

        vectors = model.encode(passages, batch_size=64, normalize_embeddings=True)

        points = []
        for (blog_id, chunk_index, chunk_body), vec in zip(meta, vectors):
            points.append({
                "id": f"{blog_id}_{chunk_index}",
                "vectors": {"embedding_text": vec.tolist()},
                "payload": {
                    "blog_id": blog_id,
                    "chunk_index": chunk_index,
                    "chunk_text": chunk_body,
                },
            })

        upload_embeddings(points)
    except Exception as e:
        conn.close()
        return {"success": False, "message": f"Failed to generate embeddings: {e}"}

    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE blog SET is_embedded = 1 WHERE id = %s", (article_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return {"success": False, "message": f"Failed to finalize article: {e}"}
    finally:
        conn.close()

    log_event("knowledge_added", "Knowledge added from URL")

    return {"success": True, "message": "Knowledge added successfully"}


# ======================
# Logs
# ======================

_EVENT_LABELS = {
    "scraper_started": "Scraper Started",
    "scraper_completed": "Scraper Completed",
    "scraper_failed": "Scraper Failed",
    "embedding_started": "Embedding Started",
    "embedding_completed": "Embedding Completed",
    "embedding_failed": "Embedding Failed",
    "rebuild_started": "Rebuild Started",
    "rebuild_completed": "Rebuild Completed",
    "rebuild_failed": "Rebuild Failed",
    "knowledge_added": "Knowledge Added",
    "knowledge_deleted": "Knowledge Deleted",
    "system_error": "System Error",
    "user_logged_in": "User Logged In",
    "user_logged_out": "User Logged Out",
    "user_created": "User Created",
    "user_updated": "User Updated",
    "user_disabled": "User Disabled",
    "user_enabled": "User Enabled",
    "user_deleted": "User Deleted",
    "user_password_reset": "User Password Reset",
    "login_failed": "Login Failed",
}


def _format_event(event_type: str) -> str:
    return _EVENT_LABELS.get(event_type, event_type.replace("_", " ").title())


def get_logs(limit: int = 50) -> List[Dict[str, Any]]:
    rows = _query_list(
        "SELECT event_type, message, created_at FROM dashboard_logs ORDER BY created_at DESC LIMIT %s",
        (limit,),
    )
    return [
        {
            "timestamp": r["created_at"],
            "event": _format_event(r["event_type"]),
        }
        for r in rows
    ]


# ======================
# Health
# ======================

def check_health() -> Dict[str, bool]:
    result = {
        "api": True,
        "database": False,
        "qdrant": False,
        "groq": False,
    }

    # Database
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        conn.close()
        result["database"] = True
    except Exception:
        pass

    # Qdrant
    client = _get_qdrant_client()
    if client is not None:
        try:
            result["qdrant"] = client.collection_exists(QDRANT_COLLECTION)
        except Exception:
            pass

    # Groq
    try:
        resp = requests.head(GROQ_BASE_URL, timeout=5)
        result["groq"] = resp.status_code < 500
    except Exception:
        pass

    return result


# ======================
# Auth / User Management
# ======================


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"), password_hash.encode("utf-8")
    )


def _validate_username(username: str) -> tuple[bool, str]:
    username = username.strip().lower()
    if not username:
        return False, "Username is required"
    if len(username) < 3 or len(username) > 32:
        return False, "Username must be between 3 and 32 characters"
    if not re.match(r"^[a-z0-9_]+$", username):
        return (
            False,
            "Username can only contain lowercase letters, numbers, and underscores",
        )
    return True, username


def _validate_password(password: str) -> tuple[bool, str]:
    if not password:
        return False, "Password is required"
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if len(password) > 64:
        return False, "Password must be at most 64 characters"
    return True, password


def authenticate_user(username: str, password: str) -> dict | None:
    username = username.strip().lower()
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, display_name, username, password_hash, role, is_active FROM dashboard_users WHERE username = %s",
                (username,),
            )
            user = cursor.fetchone()
        if not user:
            return None
        if not user["is_active"]:
            return None
        if not _check_password(password, user["password_hash"]):
            return None

        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE dashboard_users SET last_login_at = NOW() WHERE id = %s",
                (user["id"],),
            )
        conn.commit()

        return {
            "id": user["id"],
            "display_name": user["display_name"],
            "username": user["username"],
            "role": user["role"],
        }
    except Exception:
        return None
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, display_name, username, role, is_active FROM dashboard_users WHERE id = %s",
                (user_id,),
            )
            return cursor.fetchone()
    except Exception:
        return None
    finally:
        conn.close()


def list_users() -> List[Dict[str, Any]]:
    return _query_list(
        "SELECT id, display_name, username, role, is_active, last_login_at, created_at FROM dashboard_users ORDER BY id ASC"
    )


def _username_exists(username: str) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM dashboard_users WHERE username = %s",
                (username.strip().lower(),),
            )
            return cursor.fetchone() is not None
    finally:
        conn.close()


def create_user(
    display_name: str,
    username: str,
    password: str,
    role: str,
    created_by_role: str,
) -> tuple[bool, str]:
    display_name = display_name.strip()
    if not display_name:
        return False, "Display name is required"
    if len(display_name) > 100:
        return False, "Display name must be at most 100 characters"

    valid, result = _validate_username(username)
    if not valid:
        return False, result
    username = result

    valid, result = _validate_password(password)
    if not valid:
        return False, result

    if role not in ("owner", "admin"):
        return False, "Role must be 'owner' or 'admin'"

    if role == "owner" and created_by_role != "owner":
        return False, "Only owners can create owner users"

    if _username_exists(username):
        return False, "Username already exists"

    password_hash = _hash_password(password)

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO dashboard_users (display_name, username, password_hash, role) VALUES (%s, %s, %s, %s)",
                (display_name, username, password_hash, role),
            )
        conn.commit()

        log_event(
            "user_created",
            f"User '{username}' ({role}) created by {created_by_role}",
        )

        return True, "User created successfully"
    except Exception as e:
        conn.rollback()
        return False, f"Failed to create user: {e}"
    finally:
        conn.close()


def _is_last_owner(user_id: int) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM dashboard_users WHERE role = 'owner' AND is_active = 1 AND id != %s",
                (user_id,),
            )
            row = cursor.fetchone()
            return row["cnt"] == 0
    finally:
        conn.close()


def update_user(
    user_id: int, data: dict, current_user_role: str
) -> tuple[bool, str]:
    target = get_user_by_id(user_id)
    if not target:
        return False, "User not found"

    if current_user_role != "owner" and target["role"] == "owner":
        return False, "Admins cannot modify owner users"

    updates = []
    params = []

    if "display_name" in data:
        name = data["display_name"].strip()
        if not name:
            return False, "Display name is required"
        if len(name) > 100:
            return False, "Display name must be at most 100 characters"
        updates.append("display_name = %s")
        params.append(name)

    if "role" in data:
        new_role = data["role"]
        if new_role not in ("owner", "admin"):
            return False, "Role must be 'owner' or 'admin'"
        if current_user_role != "owner":
            return False, "Only owners can change roles"
        if target["role"] == "owner" and new_role != "owner":
            if _is_last_owner(user_id):
                return False, "Cannot demote the last owner"
        updates.append("role = %s")
        params.append(new_role)

    if "is_active" in data:
        is_active = bool(data["is_active"])
        if target["role"] == "owner" and not is_active:
            if _is_last_owner(user_id):
                return False, "Cannot disable the last owner"
        if current_user_role != "owner" and target["role"] == "owner":
            return False, "Admins cannot modify owner users"
        updates.append("is_active = %s")
        params.append(1 if is_active else 0)

    if not updates:
        return False, "No fields to update"

    params.append(user_id)

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"UPDATE dashboard_users SET {', '.join(updates)} WHERE id = %s",
                tuple(params),
            )
        conn.commit()

        was_disabled = "is_active" in data and not bool(data["is_active"])
        was_enabled = "is_active" in data and bool(data["is_active"])

        if was_disabled:
            log_event(
                "user_disabled",
                f"User '{target['username']}' disabled by {current_user_role}",
            )
        elif was_enabled:
            log_event(
                "user_enabled",
                f"User '{target['username']}' enabled by {current_user_role}",
            )

        if "role" in data or "display_name" in data:
            log_event(
                "user_updated",
                f"User '{target['username']}' updated by {current_user_role}",
            )

        return True, "User updated successfully"
    except Exception as e:
        conn.rollback()
        return False, f"Failed to update user: {e}"
    finally:
        conn.close()


def reset_user_password(
    user_id: int, new_password: str, current_user_role: str
) -> tuple[bool, str]:
    target = get_user_by_id(user_id)
    if not target:
        return False, "User not found"

    if current_user_role != "owner" and target["role"] == "owner":
        return False, "Admins cannot reset owner passwords"

    valid, result = _validate_password(new_password)
    if not valid:
        return False, result

    password_hash = _hash_password(new_password)

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE dashboard_users SET password_hash = %s WHERE id = %s",
                (password_hash, user_id),
            )
        conn.commit()

        log_event(
            "user_password_reset",
            f"Password reset for user '{target['username']}' by {current_user_role}",
        )

        return True, "Password reset successfully"
    except Exception as e:
        conn.rollback()
        return False, f"Failed to reset password: {e}"
    finally:
        conn.close()


def delete_user(user_id: int, current_user_role: str) -> tuple[bool, str]:
    target = get_user_by_id(user_id)
    if not target:
        return False, "User not found"

    if current_user_role != "owner" and target["role"] == "owner":
        return False, "Admins cannot delete owner users"

    if target["role"] == "owner" and _is_last_owner(user_id):
        return False, "Cannot delete the last owner"

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM dashboard_users WHERE id = %s", (user_id,)
            )
        conn.commit()

        log_event(
            "user_deleted",
            f"User '{target['username']}' deleted by {current_user_role}",
        )

        return True, "User deleted successfully"
    except Exception as e:
        conn.rollback()
        return False, f"Failed to delete user: {e}"
    finally:
        conn.close()


def seed_owner() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM dashboard_users WHERE role = 'owner'"
            )
            row = cursor.fetchone()
            if row and row["cnt"] > 0:
                return

        username = os.getenv("DASHBOARD_OWNER_USERNAME", "").strip().lower()
        password = os.getenv("DASHBOARD_OWNER_PASSWORD", "")
        display_name = os.getenv("DASHBOARD_OWNER_NAME", "").strip()

        if not username or not password or not display_name:
            print(
                "⚠️  WARNING: No owner user exists and one or more of "
                "DASHBOARD_OWNER_USERNAME/PASSWORD/NAME env vars are not set.\n"
                "   Dashboard login will not be available until an owner is created.\n"
                "   Set these environment variables and restart the server."
            )
            return

        valid, msg = _validate_username(username)
        if not valid:
            print(f"⚠️  WARNING: Invalid DASHBOARD_OWNER_USERNAME: {msg}")
            return

        valid, msg = _validate_password(password)
        if not valid:
            print(f"⚠️  WARNING: Invalid DASHBOARD_OWNER_PASSWORD: {msg}")
            return

        if not display_name:
            display_name = username

        password_hash = _hash_password(password)

        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO dashboard_users (display_name, username, password_hash, role) VALUES (%s, %s, %s, 'owner')",
                (display_name, username, password_hash),
            )
        conn.commit()
        print(f"✓ Owner user '{username}' created successfully")
    except Exception as e:
        print(f"⚠️  Failed to seed owner: {e}")
    finally:
        conn.close()

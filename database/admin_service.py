import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from qdrant_client import QdrantClient, models

from database.db import get_connection
from database.dashboard_logger import log_event
from database.qdrant_uploader import QDRANT_COLLECTION

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "scraper" / "articles.csv"

_job_lock = threading.Lock()
_job_running = False

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_TOKEN = os.getenv("QDRANT_TOKEN")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

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

def _run_background(target_func):
    global _job_running
    try:
        target_func()
    except Exception as e:
        print(f"Background job failed: {e}")
    finally:
        _job_running = False
        _job_lock.release()


def _start_background_job(target_func):
    global _job_running
    if _job_running:
        return {"status": "busy", "message": "A maintenance job is already running"}
    if not _job_lock.acquire(blocking=False):
        return {"status": "busy", "message": "A maintenance job is already running"}
    _job_running = True
    thread = threading.Thread(target=lambda: _run_background(target_func), daemon=True)
    thread.start()
    return {"status": "started", "message": "Job started in background"}


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

        log_event("scraper_started", "Scraper triggered from dashboard")
        try:
            known_urls = load_known_urls_from_db()
            scrape_all_articles(
                known_urls,
                csv_path=CSV_PATH,
                total_pages=0,
                sleep_seconds=0.3,
                on_article=insert_blog_article,
                write_csv=False,
            )
            log_event("scraper_completed", "Scraper completed successfully")
        except Exception as e:
            log_event("scraper_failed", f"Scraper failed: {e}")
            raise

    return _start_background_job(_scrape)


# ======================
# Embedding
# ======================

def run_embedding():
    def _embed():
        from database.database_server import (
            embed_and_upload_blog_articles,
            export_blog_to_csv,
        )

        log_event("embedding_started", "Embedding triggered from dashboard")
        try:
            export_blog_to_csv(CSV_PATH)
            embed_and_upload_blog_articles()
            log_event("embedding_completed", "Embedding completed successfully")
        except Exception as e:
            log_event("embedding_failed", f"Embedding failed: {e}")
            raise

    return _start_background_job(_embed)


# ======================
# Rebuild
# ======================

def rebuild_everything():
    def _rebuild():
        from database.database_server import embed_and_upload_blog_articles

        log_event("rebuild_started", "Rebuild triggered from dashboard")
        try:
            _reset_all_is_embedded()
            embed_and_upload_blog_articles()
            log_event("rebuild_completed", "Rebuild completed successfully")
        except Exception as e:
            log_event("rebuild_failed", f"Rebuild failed: {e}")
            raise

    return _start_background_job(_rebuild)


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
    "knowledge_deleted": "Knowledge Deleted",
    "system_error": "System Error",
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

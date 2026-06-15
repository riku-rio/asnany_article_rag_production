import pymysql.connections

from database.db import get_connection
from database.tables.dashboard_logs import create_dashboard_logs_table

SUPPORTED_EVENTS = frozenset({
    "scraper_started",
    "scraper_completed",
    "scraper_failed",
    "embedding_started",
    "embedding_completed",
    "embedding_failed",
    "rebuild_started",
    "rebuild_completed",
    "rebuild_failed",
    "knowledge_deleted",
    "system_error",
})


def log_event(
    event_type: str,
    message: str,
    conn: pymysql.connections.Connection = None,
) -> int | None:
    if event_type not in SUPPORTED_EVENTS:
        print(f"⚠️ log_event: unknown event_type '{event_type}'")
        return None

    own_conn = False
    try:
        if conn is None:
            conn = get_connection()
            own_conn = True

        create_dashboard_logs_table(conn)

        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO dashboard_logs (event_type, message) VALUES (%s, %s)",
                (event_type, message),
            )
            conn.commit()
            return cursor.lastrowid

    except Exception as e:
        print(f"⚠️ log_event failed: {e}")
        return None

    finally:
        if own_conn and conn is not None:
            try:
                conn.close()
            except Exception:
                pass

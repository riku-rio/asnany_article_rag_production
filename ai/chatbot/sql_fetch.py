import sqlite3
from typing import List , Dict
from pathlib import Path

# ======================
# Paths
# ======================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "database" / "database.db"

# ======================
# Connection
# ======================

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ======================
# Fetch Structured Sources (NEW - V3 Ready)
# ======================

def fetch_sources_by_ids(article_ids: List[int]) -> List[Dict[str, str]]:
    """
    Fetch blog title + url by article IDs.

    Returns:
        [
            {"title": "...", "url": "..."}
        ]
    """

    if not article_ids:
        return []

    # Normalize + dedupe while preserving order
    clean_ids: List[int] = []
    seen = set()

    for x in article_ids:
        try:
            i = int(x)
        except Exception:
            continue

        if i not in seen:
            seen.add(i)
            clean_ids.append(i)

    if not clean_ids:
        return []

    placeholders = ",".join("?" for _ in clean_ids)

    query = f"""
        SELECT id, title, url
        FROM blog
        WHERE id IN ({placeholders});
    """

    conn = get_connection()

    try:
        rows = conn.execute(query, clean_ids).fetchall()

        # Map id -> {title, url}
        source_map = {
            int(row["id"]): {
                "title": (row["title"] or "").strip(),
                "url": (row["url"] or "").strip(),
            }
            for row in rows
            if row["title"] and row["url"]
        }

        # Preserve original order
        sources: List[Dict[str, str]] = []

        for i in clean_ids:
            src = source_map.get(i)
            if src:
                sources.append(src)

        return sources

    finally:
        conn.close()
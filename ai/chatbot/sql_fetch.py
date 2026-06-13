from typing import Dict, List

from database.db import get_connection

# ======================
# Fetch Structured Sources (MySQL version)
# ======================

def fetch_sources_by_ids(article_ids: List[int]) -> List[Dict[str, str]]:
    """
    Fetch blog title + url by article IDs from MySQL.

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

    placeholders = ",".join("%s" for _ in clean_ids)

    query = f"""
        SELECT id, title, url
        FROM blog
        WHERE id IN ({placeholders});
    """

    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(query, clean_ids)
            rows = cursor.fetchall()

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
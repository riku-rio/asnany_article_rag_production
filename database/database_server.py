import csv
from pathlib import Path
from typing import Any, Dict, List, Set

# ======================
# Paths
# ======================

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR.parent / "scraper" / "articles.csv"

# ======================
# Imports
# ======================

from database.db import get_connection
from database.tables.blog import create_blog_table
from database.embedder import embed_blog_articles
from database.qdrant_uploader import upload_embeddings
from scraper.asnany_scraper import normalize_url


# ======================
# URL Helpers
# ======================

def load_known_urls_from_db() -> Set[str]:
    """
    Load all known article URLs from MySQL and return them normalized.
    Normalizing here ensures the set matches what the scraper compares against,
    even if raw DB values have mixed percent-encoding case (%D9 vs %d9).
    Creates the blog table if it doesn't exist yet.
    """
    conn = get_connection()
    try:
        create_blog_table(conn)
        with conn.cursor() as cursor:
            cursor.execute("SELECT url FROM blog;")
            rows = cursor.fetchall()
        known: Set[str] = set()
        for row in rows:
            raw_url = (row.get("url") or "").strip()
            norm = normalize_url(raw_url)
            if norm:
                known.add(norm)
        return known
    finally:
        conn.close()


# ======================
# Insert
# ======================

def insert_blog_article(article: Dict[str, str]) -> bool:
    """
    Insert a single article into MySQL using INSERT IGNORE.
    Normalizes the URL before storing so the DB is consistent.
    Returns True if a new row was inserted, False if duplicate or invalid.
    """
    title = (article.get("title") or "").strip()
    raw_url = (article.get("url") or "").strip()
    url = normalize_url(raw_url)          # store normalized form
    content = (article.get("content") or "").strip()

    if not title or not url or not content:
        return False

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT IGNORE INTO blog (title, url, content) VALUES (%s, %s, %s);",
                (title, url, content),
            )
            inserted = cursor.rowcount > 0
        conn.commit()
        return inserted
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ======================
# Export CSV
# ======================

def export_blog_to_csv(csv_path: Path = CSV_PATH) -> int:
    """
    Export all articles from MySQL to CSV (backup/export only).
    Writes scraper/articles.csv with UTF-8 and header: title,url,content.
    Returns number of rows written.
    """
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT title, url, content FROM blog ORDER BY id ASC;"
            )
            rows = cursor.fetchall()
    finally:
        conn.close()

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "url", "content"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "title": (row.get("title") or "").strip(),
                    "url": (row.get("url") or "").strip(),
                    "content": (row.get("content") or "").strip(),
                }
            )

    print(f"📄 Exported {len(rows)} articles to {csv_path}")
    return len(rows)


# ======================
# Legacy CSV → MySQL import
# (Do NOT call from main.py — use only for one-off imports)
# ======================

def seed_blog_from_csv(csv_path: Path = CSV_PATH) -> None:
    """
    Legacy helper: import articles from CSV into MySQL.
    Safe/idempotent using normalized URL comparison against DB before insert.

    Do NOT call this in the production pipeline — it exists for migration only.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"❌ CSV not found: {csv_path}")

    known_urls = load_known_urls_from_db()

    inserted = 0
    skipped = 0
    invalid = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            title = (row.get("title") or "").strip()
            raw_url = (row.get("url") or "").strip()
            url = normalize_url(raw_url)
            content = (row.get("content") or "").strip()

            if not title or not url or not content:
                invalid += 1
                continue

            if url in known_urls:
                skipped += 1
                continue

            was_inserted = insert_blog_article({
                "title": title,
                "url": url,
                "content": content,
            })

            if was_inserted:
                inserted += 1
                known_urls.add(url)
            else:
                skipped += 1

    print(
        f"🌱 Seeded {inserted} new articles "
        f"(skipped {skipped} duplicates, invalid {invalid})"
    )


# ======================
# Embeddings + Qdrant (Incremental + per-article marking)
# ======================

def _group_points_by_blog_id(points: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for p in points:
        payload = p.get("payload") or {}
        blog_id = payload.get("blog_id")

        if blog_id is None:
            raise ValueError("Point payload missing 'blog_id'")

        blog_id_int = int(blog_id)
        grouped.setdefault(blog_id_int, []).append(p)

    return grouped


def _mark_article_embedded(conn, blog_id: int) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE blog SET is_embedded = 1 WHERE id = %s;",
            (int(blog_id),),
        )


def embed_and_upload_blog_articles() -> None:
    """
    Incremental pipeline:
    - Embed ONLY articles where is_embedded = 0
    - Upload to Qdrant
    - Mark is_embedded = 1 PER ARTICLE after successful upload
    - Commit per article; rollback on error

    Safe reruns:
    - If upload fails before marking, article remains is_embedded=0 and retries next run.
    - Deterministic point IDs ensure upserts don't duplicate.
    """

    print("🧠 Starting blog embeddings pipeline...")

    # 1) Prepare points for ONLY unembedded articles
    points = embed_blog_articles()

    if not points:
        print("⚠️ No new embeddings generated — skipping upload")
        return

    # 2) Group by blog_id so we can mark per article after successful upload
    grouped = _group_points_by_blog_id(points)
    blog_ids = list(grouped.keys())

    print(f"📦 Articles to upload: {len(blog_ids)}")

    conn = get_connection()

    try:
        # Ensure table exists (safe)
        create_blog_table(conn)

        uploaded_articles = 0

        # 3) Upload article-by-article, then mark embedded
        for blog_id in blog_ids:
            article_points = grouped[blog_id]

            # Upload all chunks for this article
            upload_embeddings(article_points)

            # Mark embedded only AFTER successful upload
            _mark_article_embedded(conn, blog_id)
            conn.commit()

            uploaded_articles += 1
            print(f"✅ Marked embedded: blog_id={blog_id} ({uploaded_articles}/{len(blog_ids)})")

        print("🚀 Blog embeddings pipeline completed")

    except Exception as e:
        conn.rollback()
        print("❌ Embeddings pipeline failed — rollback SQL marking")
        raise e

    finally:
        conn.close()
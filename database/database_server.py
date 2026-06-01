import csv
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Set

# ======================
# Paths
# ======================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
CSV_PATH = BASE_DIR.parent / "scraper" / "articles.csv"

ENV = os.getenv("ENV", "development")

# ======================
# Table
# ======================

from database.tables.blog import create_blog_table

# Embeddings
from database.embedder import embed_blog_articles
from database.qdrant_uploader import upload_embeddings


# ======================
# Connection
# ======================

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ======================
# Seed
# ======================

def seed_blog_from_csv() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"❌ CSV not found: {CSV_PATH}")

    conn = get_connection()

    try:
        create_blog_table(conn)

        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [
                {
                    "title": (row.get("title") or "").strip(),
                    "url": (row.get("url") or "").strip(),
                    "content": (row.get("content") or "").strip(),
                }
                for row in reader
                if (row.get("title") or "").strip()
                and (row.get("url") or "").strip()
                and (row.get("content") or "").strip()
            ]

        conn.executemany(
            """
            INSERT OR IGNORE INTO blog (title, url, content)
            VALUES (:title, :url, :content);
            """,
            rows,
        )

        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM blog;").fetchone()[0]
        print(f"🌱 Blog table seeded — total articles: {count}")

    except Exception as e:
        conn.rollback()
        print("❌ Seeding failed — rollback")
        raise e

    finally:
        conn.close()


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


def _mark_article_embedded(conn: sqlite3.Connection, blog_id: int) -> None:
    conn.execute(
        """
        UPDATE blog
        SET is_embedded = 1
        WHERE id = ?;
        """,
        (int(blog_id),),
    )


def embed_and_upload_blog_articles() -> None:
    """
    Incremental pipeline (Version 1):
    - Embed ONLY articles where is_embedded = 0 (handled inside embed_blog_articles)
    - Upload to Qdrant
    - Mark is_embedded = 1 PER ARTICLE after successful upload of that article's chunks

    Safe reruns:
    - If upload fails before marking, article remains is_embedded=0 and will retry on next run.
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
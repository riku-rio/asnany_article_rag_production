from pathlib import Path
import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient

from scraper.asnany_scraper import scrape_all_articles

from database.db import get_connection
from database.tables.blog import create_blog_table
from database.dashboard_logger import log_event
from database.database_server import (
    load_known_urls_from_db,
    insert_blog_article,
    export_blog_to_csv,
    embed_and_upload_blog_articles,
)

# ======================
# Load ENV
# ======================
load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_TOKEN = os.getenv("QDRANT_TOKEN")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "asnany_article_rag_production")
QDRANT_TIMEOUT = int(os.getenv("QDRANT_TIMEOUT", 300))

# ======================
# Paths
# ======================
PROJECT_ROOT = Path(__file__).resolve().parent
CSV_PATH = PROJECT_ROOT / "scraper" / "articles.csv"


def reset_all_is_embedded() -> None:
    """Reset embedding state so we can rebuild Qdrant from MySQL."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE blog SET is_embedded = 0;")
        conn.commit()
        print("🔄 Reset is_embedded=0 for all articles (rebuild mode)")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ======================
# Main
# ======================
if __name__ == "__main__":
    log_event("rebuild_started", "Pipeline execution started")

    try:
        # 1️⃣ Ensure MySQL table exists and load known URLs from DB
        conn = get_connection()
        try:
            create_blog_table(conn)
        finally:
            conn.close()

        known_urls = load_known_urls_from_db()
        print(f"🗄️ Known URLs in MySQL: {len(known_urls)}")

        # 2️⃣ Scrape incremental — write directly to MySQL, skip CSV write
        scrape_all_articles(
            known_urls,
            csv_path=CSV_PATH,
            total_pages=0,
            sleep_seconds=0.3,
            on_article=insert_blog_article,
            write_csv=False,
        )

        # 3️⃣ Export CSV backup from MySQL
        print("\n📄 Exporting CSV backup from MySQL...")
        export_blog_to_csv(CSV_PATH)

        # 4️⃣ Qdrant reset logic (if collection is missing)
        if not QDRANT_URL:
            raise RuntimeError("QDRANT_URL is not set in .env")

        qdrant_client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_TOKEN,
            timeout=QDRANT_TIMEOUT,
            check_compatibility=False,
        )

        try:
            collection_exists = qdrant_client.collection_exists(QDRANT_COLLECTION)
        except Exception as e:
            raise RuntimeError(f"Qdrant check failed: {e}") from e

        if not collection_exists:
            print(f"\n📦 Qdrant collection '{QDRANT_COLLECTION}' not found — will rebuild embeddings")
            reset_all_is_embedded()
        else:
            print(f"\n📦 Qdrant collection '{QDRANT_COLLECTION}' exists — will embed only new articles")

        # 5️⃣ Embeddings + Upload (incremental per-article marking happens inside database_server.py)
        print("\n🧠 Starting embeddings + Qdrant upload...")
        embed_and_upload_blog_articles()

        log_event("rebuild_completed", "Pipeline completed successfully")

    except Exception as e:
        log_event("system_error", f"Pipeline failed: {e}")
        raise
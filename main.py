from pathlib import Path
import os
import sqlite3

from dotenv import load_dotenv
from qdrant_client import QdrantClient

from scraper.asnany_scraper import (
    scrape_all_articles,
    load_known_urls_from_csv,
)

from database.database_server import (
    seed_blog_from_csv,
    embed_and_upload_blog_articles,
)

# ======================
# Load ENV
# ======================
load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_TOKEN = os.getenv("QDRANT_TOKEN")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "asnany_blog_articles")
QDRANT_TIMEOUT = int(os.getenv("QDRANT_TIMEOUT", 120))

# ======================
# Paths
# ======================
PROJECT_ROOT = Path(__file__).resolve().parent
CSV_PATH = PROJECT_ROOT / "scraper" / "articles.csv"
DB_PATH = PROJECT_ROOT / "database" / "database.db"


def reset_all_is_embedded() -> None:
    """Reset embedding state so we can rebuild Qdrant from SQL."""
    if not DB_PATH.exists():
        # لو الداتابيس مش موجودة لسه، seeding هو اللي هيعملها
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("UPDATE blog SET is_embedded = 0;")
        conn.commit()
        print("🔄 Reset is_embedded=0 for all articles (rebuild mode)")
    finally:
        conn.close()


# ======================
# Main
# ======================
if __name__ == "__main__":
    # 1️⃣ جهّز known_urls من CSV (لو مش موجود هترجع set فاضية)
    known_urls = load_known_urls_from_csv(CSV_PATH)

    if CSV_PATH.exists():
        print(f"📄 articles.csv found — known URLs: {len(known_urls)}")
    else:
        print("📄 articles.csv not found — will create and scrape...")

    # 2️⃣ Scrape incremental (هيضيف الجديد فقط للـ CSV)
    scrape_all_articles(
        known_urls,
        csv_path=CSV_PATH,
    )

    # 3️⃣ SQL / Seeding (بعد ما CSV اتحدّث)
    print("\n🗄️ Starting SQL seeding from CSV...")
    seed_blog_from_csv()

    # 4️⃣ Qdrant reset logic (لو الـ collection مش موجودة)
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
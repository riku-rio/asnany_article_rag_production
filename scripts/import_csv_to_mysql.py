"""
scripts/import_csv_to_mysql.py
-------------------------------
One-time legacy import: reads scraper/articles.csv and inserts all articles
into MySQL using INSERT IGNORE (skips duplicates).

Usage:
    uv run python scripts/import_csv_to_mysql.py

This script is intentionally idempotent — safe to run multiple times.
"""

import sys
import io
from pathlib import Path

# Reconfigure stdout to UTF-8 so emoji work on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure project root is on sys.path when run directly
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

CSV_PATH = PROJECT_ROOT / "scraper" / "articles.csv"

from database.database_server import seed_blog_from_csv


def main() -> None:
    if not CSV_PATH.exists():
        print(f"⚠️ CSV not found at {CSV_PATH} — nothing to import")
        sys.exit(0)

    print(f"📄 Reading CSV from: {CSV_PATH}")
    print("⬆️  Importing articles into MySQL...")

    try:
        seed_blog_from_csv(CSV_PATH)
        print("✅ CSV import completed")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

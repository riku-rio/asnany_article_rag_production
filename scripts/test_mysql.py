"""
scripts/test_mysql.py
---------------------
Smoke test for MySQL connectivity and blog table.

Usage:
    uv run python scripts/test_mysql.py
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

from database.db import get_connection
from database.tables.blog import create_blog_table


def main() -> None:
    print("🔌 Connecting to MySQL...")
    conn = get_connection()
    try:
        print("✅ Connection established")

        print("📋 Ensuring blog table exists...")
        create_blog_table(conn)
        print("✅ Blog table ready")

        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS count FROM blog;")
            row = cursor.fetchone()

        count = row["count"] if row else 0
        print(f"📊 Total articles in blog table: {count}")
        print("\n🎉 MySQL test passed successfully!")

    except Exception as e:
        print(f"\n❌ MySQL test failed: {e}")
        sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()

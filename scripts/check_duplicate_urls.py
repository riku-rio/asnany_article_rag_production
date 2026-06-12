"""
scripts/check_duplicate_urls.py
--------------------------------
Diagnostic: connects to MySQL, fetches all blog URLs, normalizes them,
and reports any duplicate groups (same normalized URL, different raw rows).

Does NOT delete or modify any rows.

Usage:
    uv run python scripts/check_duplicate_urls.py
"""

import sys
import io
from pathlib import Path
from collections import defaultdict

# Reconfigure stdout to UTF-8 so emoji/Arabic work on Windows terminals
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
from scraper.asnany_scraper import normalize_url


def main() -> None:
    print("🔌 Connecting to MySQL...")
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, url FROM blog ORDER BY id ASC;")
            rows = cursor.fetchall()
    finally:
        conn.close()

    total_rows = len(rows)
    raw_urls = {row["id"]: (row["url"] or "").strip() for row in rows}
    unique_raw = len(set(raw_urls.values()))

    # Group by normalized URL
    norm_groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        raw = (row["url"] or "").strip()
        norm = normalize_url(raw)
        norm_groups[norm].append({"id": row["id"], "raw_url": raw})

    unique_norm = len(norm_groups)
    dup_groups = {n: entries for n, entries in norm_groups.items() if len(entries) > 1}

    print()
    print("=" * 70)
    print(f"  Total rows in blog:          {total_rows}")
    print(f"  Unique raw URLs:             {unique_raw}")
    print(f"  Unique normalized URLs:      {unique_norm}")
    print(f"  Duplicate normalized groups: {len(dup_groups)}")
    print("=" * 70)

    if not dup_groups:
        print("\n✅ No normalized URL duplicates found — DB is clean!")
        return

    print(f"\n⚠️  Found {len(dup_groups)} duplicate group(s):\n")

    for norm_url, entries in sorted(dup_groups.items()):
        print(f"  Normalized: {norm_url}")
        for e in entries:
            print(f"    id={e['id']}  raw={e['raw_url']}")
        print()

    print("ℹ️  No rows were deleted. To deduplicate, run a manual cleanup query.")


if __name__ == "__main__":
    main()

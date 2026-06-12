from database.db import get_connection
from scraper.asnany_scraper import normalize_url

DRY_RUN = True  # Set to False to actually delete duplicates

conn = get_connection()

try:
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, url FROM blog ORDER BY id ASC;")
        rows = cursor.fetchall()

    keep_by_norm = {}
    delete_ids = []

    for row in rows:
        blog_id = int(row["id"])
        url = (row.get("url") or "").strip()
        norm = normalize_url(url)

        if not norm:
            continue

        if norm not in keep_by_norm:
            keep_by_norm[norm] = blog_id
        else:
            delete_ids.append(blog_id)

    print(f"Total rows: {len(rows)}")
    print(f"Unique normalized URLs: {len(keep_by_norm)}")
    print(f"Duplicate rows to delete: {len(delete_ids)}")

    if DRY_RUN:
        print("DRY_RUN=True, no rows deleted.")
        print("First duplicate IDs:", delete_ids[:30])
    else:
        if delete_ids:
            placeholders = ",".join(["%s"] * len(delete_ids))
            with conn.cursor() as cursor:
                cursor.execute(
                    f"DELETE FROM blog WHERE id IN ({placeholders});",
                    delete_ids,
                )
            conn.commit()
            print(f"Deleted {len(delete_ids)} duplicate rows.")
        else:
            print("No duplicates found.")

except Exception:
    conn.rollback()
    raise

finally:
    conn.close()
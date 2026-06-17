"""
scripts/delete_all_users.py
---------------------------
WARNING: This script DELETES ALL records from the dashboard_users table.
Use only for local/admin recovery, e.g. to reset the owner account so it
can be re-seeded from .env on the next application startup.

Usage:
    python scripts/delete_all_users.py           # interactive (confirmation)
    python scripts/delete_all_users.py --force   # skip confirmation
"""

import sys
import io
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from database.db import get_connection


def main() -> None:
    force = "--force" in sys.argv

    conn = get_connection()
    try:
        print("Connected to database")

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = %s",
                ("dashboard_users",),
            )
            row = cursor.fetchone()
            if row["cnt"] == 0:
                print("dashboard_users table does not exist — nothing to delete")
                sys.exit(0)

            cursor.execute("SELECT COUNT(*) AS cnt FROM dashboard_users")
            count = cursor.fetchone()["cnt"]
            print(f"Number of users found: {count}")

            if count == 0:
                print("Done")
                sys.exit(0)

            if not force:
                print()
                print("WARNING: This will delete ALL users from dashboard_users.")
                print("Type DELETE_ALL_USERS to continue:")
                try:
                    response = input().strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    print("Aborted")
                    sys.exit(1)
                if response != "DELETE_ALL_USERS":
                    print("Aborted")
                    sys.exit(1)

            cursor.execute("DELETE FROM dashboard_users")
            conn.commit()
            deleted = cursor.rowcount

        print(f"Number of users deleted: {deleted}")
        print("Done")
        print()
        print("After deleting users, make sure your .env contains:")
        print()
        print("DASHBOARD_SECRET_KEY=xxx")
        print("DASHBOARD_OWNER_USERNAME=owner")
        print("DASHBOARD_OWNER_PASSWORD=your-strong-password-here")
        print("DASHBOARD_OWNER_NAME=Owner")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

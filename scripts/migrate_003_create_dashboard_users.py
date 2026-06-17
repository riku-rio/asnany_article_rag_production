from dotenv import load_dotenv
load_dotenv()

from database.db import get_connection
from database.tables.dashboard_users import create_dashboard_users_table


def main():
    conn = get_connection()
    try:
        create_dashboard_users_table(conn)
        print("✓ dashboard_users table ready")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

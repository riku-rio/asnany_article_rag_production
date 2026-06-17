from dotenv import load_dotenv
load_dotenv()

from database.db import get_connection
from database.tables.dashboard_logs import create_dashboard_logs_table


def main():
    conn = get_connection()
    try:
        create_dashboard_logs_table(conn)
        print("✓ dashboard_logs table ready")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

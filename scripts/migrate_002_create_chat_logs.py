from dotenv import load_dotenv
load_dotenv()

from database.db import get_connection
from database.tables.chat_logs import create_chat_logs_table


def main():
    conn = get_connection()
    try:
        create_chat_logs_table(conn)
        print("✓ chat_logs table ready")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

import sqlite3

def create_blog_table(conn: sqlite3.Connection):
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS blog (
        id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
        title TEXT NOT NULL,
        url TEXT NOT NULL UNIQUE,
        content TEXT NOT NULL,
        is_embedded INTEGER NOT NULL DEFAULT 0
    );
    """)

    conn.commit()
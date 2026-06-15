import pymysql.connections


def create_chat_logs_table(conn: pymysql.connections.Connection) -> None:
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_logs (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                question TEXT NOT NULL,
                answer LONGTEXT,
                response_time_ms INT UNSIGNED,
                sources_count INT UNSIGNED,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                INDEX idx_chat_logs_created_at (created_at)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """)
    conn.commit()

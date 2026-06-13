import pymysql.connections


def create_blog_table(conn: pymysql.connections.Connection) -> None:
    """
    Create the blog table in MySQL if it does not already exist.
    Safe to call on every startup.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS blog (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                title VARCHAR(500) NOT NULL,
                url VARCHAR(1000) NOT NULL,
                content LONGTEXT NOT NULL,
                is_embedded TINYINT(1) NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uq_blog_url (url(255)),
                INDEX idx_blog_is_embedded (is_embedded),
                INDEX idx_blog_url_prefix (url(255))
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
        )
    conn.commit()
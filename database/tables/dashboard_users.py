import pymysql.connections


def create_dashboard_users_table(conn: pymysql.connections.Connection) -> None:
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_users (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                display_name VARCHAR(100) NOT NULL,
                username VARCHAR(50) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role ENUM('owner', 'admin') NOT NULL DEFAULT 'admin',
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                last_login_at TIMESTAMP NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uq_dashboard_users_username (username),
                INDEX idx_dashboard_users_username (username),
                INDEX idx_dashboard_users_role (role)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        """)
    conn.commit()

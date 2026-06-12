import os

import pymysql
import pymysql.cursors
from dotenv import load_dotenv

load_dotenv()

# ======================
# MySQL ENV Config
# ======================

_MYSQL_HOST = os.getenv("MYSQL_HOST", "")
_MYSQL_PORT_STR = os.getenv("MYSQL_PORT", "3306")
_MYSQL_USER = os.getenv("MYSQL_USER", "")
_MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
_MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "")


def _validate_env() -> None:
    missing = []
    if not _MYSQL_HOST:
        missing.append("MYSQL_HOST")
    if not _MYSQL_USER:
        missing.append("MYSQL_USER")
    if not _MYSQL_PASSWORD:
        missing.append("MYSQL_PASSWORD")
    if not _MYSQL_DATABASE:
        missing.append("MYSQL_DATABASE")
    if missing:
        raise RuntimeError(
            f"Missing required MySQL environment variables: {', '.join(missing)}. "
            "Please set them in your .env file."
        )


def get_connection() -> pymysql.connections.Connection:
    """
    Return a new PyMySQL connection using env vars.
    Uses DictCursor so rows are accessible as dicts.
    autocommit=False — callers must commit/rollback explicitly.
    """
    _validate_env()

    try:
        port = int(_MYSQL_PORT_STR)
    except (ValueError, TypeError):
        raise RuntimeError(
            f"MYSQL_PORT must be an integer, got: '{_MYSQL_PORT_STR}'"
        )

    return pymysql.connect(
        host=_MYSQL_HOST,
        port=port,
        user=_MYSQL_USER,
        password=_MYSQL_PASSWORD,
        database=_MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=10,
    )

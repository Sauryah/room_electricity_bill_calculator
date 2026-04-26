"""PostgreSQL connection pool + schema bootstrap."""
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

from app.core.config import settings

# Initialize a simple connection pool
_pool: pool.SimpleConnectionPool | None = None


def init_pool() -> None:
    global _pool
    if _pool is None:
        _pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=settings.DATABASE_URL,
        )


@contextmanager
def get_conn():
    """Context manager that yields a (connection, cursor) tuple."""
    if _pool is None:
        init_pool()
    conn = _pool.getconn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield conn, cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        _pool.putconn(conn)


def init_schema() -> None:
    """Create the users table if it does not already exist."""
    init_pool()
    with get_conn() as (conn, cur):
        cur.execute(
            """
            CREATE EXTENSION IF NOT EXISTS pgcrypto;
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )


def get_user_by_username(username: str) -> dict | None:
    with get_conn() as (_conn, cur):
        cur.execute(
            "SELECT id, username, password_hash FROM users WHERE username = %s",
            (username,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "id": str(row["id"]),
            "username": row["username"],
            "password_hash": row["password_hash"],
        }


def create_user(username: str, password_hash: str) -> dict:
    with get_conn() as (_conn, cur):
        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s) "
            "RETURNING id, username",
            (username, password_hash),
        )
        row = cur.fetchone()
        return {"id": str(row["id"]), "username": row["username"]}


def update_user_password(username: str, password_hash: str) -> None:
    with get_conn() as (_conn, cur):
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE username = %s",
            (password_hash, username),
        )

"""
Database Connection and Initialization Module.
Provides thread-safe async SQLite operations using standard library sqlite3.
"""

import asyncio
import logging
import sqlite3
from pathlib import Path
from typing import Any, Callable, List, Optional
import config

logger = logging.getLogger(__name__)

def get_db_connection() -> sqlite3.Connection:
    """Creates and returns a SQLite connection with Row factory enabled."""
    db_path = Path(config.DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # High concurrency & resilience
    return conn


def execute_sync(query: str, params: tuple = ()) -> None:
    """Executes a non-returning SQL query synchronously."""
    conn = get_db_connection()
    try:
        conn.execute(query, params)
        conn.commit()
    finally:
        conn.close()


def fetchone_sync(query: str, params: tuple = ()) -> Optional[dict]:
    """Fetches a single row synchronously as a dictionary."""
    conn = get_db_connection()
    try:
        cursor = conn.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def fetchall_sync(query: str, params: tuple = ()) -> List[dict]:
    """Fetches all rows synchronously as a list of dictionaries."""
    conn = get_db_connection()
    try:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# Asynchronous wrappers for non-blocking database queries
async def run_in_executor(func: Callable[..., Any], *args: Any) -> Any:
    """Runs a synchronous database function inside a separate thread."""
    return await asyncio.to_thread(func, *args)


async def execute(query: str, params: tuple = ()) -> None:
    """Async execution of a query with commit."""
    await run_in_executor(execute_sync, query, params)


async def fetchone(query: str, params: tuple = ()) -> Optional[dict]:
    """Async fetch of a single row."""
    return await run_in_executor(fetchone_sync, query, params)


async def fetchall(query: str, params: tuple = ()) -> List[dict]:
    """Async fetch of all matching rows."""
    return await run_in_executor(fetchall_sync, query, params)


async def init_db() -> None:
    """Initializes the database schema and default configuration."""
    def _init():
        conn = get_db_connection()
        try:
            # Users table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                custom_api_key TEXT DEFAULT NULL,
                selected_model TEXT DEFAULT 'flash',
                is_banned INTEGER DEFAULT 0,
                is_whitelisted INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                last_active TEXT DEFAULT (datetime('now'))
            );
            """)

            # User Granular Permissions Table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS user_permissions (
                user_id INTEGER,
                feature TEXT,
                is_allowed INTEGER NOT NULL,
                updated_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, feature),
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            );
            """)

            # System Settings Table (Key-Value)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            );
            """)

            # Chat Sessions Table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER,
                title TEXT,
                model TEXT DEFAULT 'flash',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            );
            """)

            # Session Messages Table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS session_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                media_type TEXT DEFAULT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
            );
            """)

            # Seed default system settings if not already present
            default_settings = {
                "maintenance_mode": "false",
                "whitelist_mode": "false",
                "feature_switch_model": "true",
                "feature_use_pro": "true",
                "feature_upload_files": "true",
                "feature_send_images": "true",
                "feature_create_sessions": "true",
                "feature_custom_keys": "true",
            }

            for key, val in default_settings.items():
                conn.execute(
                    "INSERT OR IGNORE INTO system_settings (key, value) VALUES (?, ?)",
                    (key, val)
                )

            conn.commit()
            logger.info("Database schema initialized successfully.")
        finally:
            conn.close()

    await run_in_executor(_init)

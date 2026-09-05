"""
Database Repositories Module.
Provides clean data access objects (DAOs) for Users, Permissions, Settings, and Sessions.
"""

import uuid
from typing import Dict, List, Optional
from database.db import execute, fetchall, fetchone
import config

class UserRepository:
    """Repository for managing Telegram bot users."""

    @staticmethod
    async def get_or_create(user_id: int, username: Optional[str], first_name: Optional[str]) -> dict:
        """Retrieves an existing user or creates a new one."""
        user = await fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
        is_admin = 1 if user_id in config.ADMIN_IDS else 0

        if not user:
            sys_model = await fetchone("SELECT value FROM system_settings WHERE key = 'system_model'")
            initial_model = sys_model["value"] if sys_model and sys_model["value"] else "gemini-3.6-flash"
            await execute(
                """
                INSERT INTO users (user_id, username, first_name, is_admin, selected_model, last_active)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                """,
                (user_id, username, first_name, is_admin, initial_model)
            )
            user = await fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
        else:
            # Update username/first_name and admin status if changed
            await execute(
                """
                UPDATE users 
                SET username = ?, first_name = ?, is_admin = ?, last_active = datetime('now')
                WHERE user_id = ?
                """,
                (username, first_name, is_admin, user_id)
            )
        return user

    @staticmethod
    async def get_by_id(user_id: int) -> Optional[dict]:
        """Finds user by Telegram User ID."""
        return await fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))

    @staticmethod
    async def get_by_username(username: str) -> Optional[dict]:
        """Finds user by Telegram Username (case-insensitive)."""
        clean_name = username.lstrip("@").strip()
        return await fetchone("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (clean_name,))

    @staticmethod
    async def update_model(user_id: int, model: str) -> None:
        """Updates user's preferred active model ('flash' or 'pro')."""
        await execute("UPDATE users SET selected_model = ? WHERE user_id = ?", (model, user_id))

    @staticmethod
    async def update_all_models(model: str) -> None:
        """Updates active model for all users."""
        await execute("UPDATE users SET selected_model = ?", (model,))

    @staticmethod
    async def update_custom_api_key(user_id: int, api_key: Optional[str]) -> None:
        """Updates or removes user's custom Google API key."""
        await execute("UPDATE users SET custom_api_key = ? WHERE user_id = ?", (api_key, user_id))

    @staticmethod
    async def set_banned(user_id: int, is_banned: bool) -> None:
        """Bans or unbans a user."""
        await execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (1 if is_banned else 0, user_id))

    @staticmethod
    async def set_whitelisted(user_id: int, is_whitelisted: bool) -> None:
        """Adds or removes a user from the whitelist."""
        await execute("UPDATE users SET is_whitelisted = ? WHERE user_id = ?", (1 if is_whitelisted else 0, user_id))

    @staticmethod
    async def list_users(limit: int = 50, offset: int = 0) -> List[dict]:
        """Lists users sorted by recent activity."""
        return await fetchall(
            "SELECT * FROM users ORDER BY last_active DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )

    @staticmethod
    async def count_users() -> int:
        """Returns total user count."""
        res = await fetchone("SELECT COUNT(*) as count FROM users")
        return res["count"] if res else 0

    @staticmethod
    async def count_banned() -> int:
        """Returns total banned user count."""
        res = await fetchone("SELECT COUNT(*) as count FROM users WHERE is_banned = 1")
        return res["count"] if res else 0

    @staticmethod
    async def count_whitelisted() -> int:
        """Returns total whitelisted user count."""
        res = await fetchone("SELECT COUNT(*) as count FROM users WHERE is_whitelisted = 1")
        return res["count"] if res else 0


class PermissionRepository:
    """Repository for managing granular feature-level permissions per user."""

    @staticmethod
    async def get_user_override(user_id: int, feature: str) -> Optional[bool]:
        """
        Retrieves user override for a specific feature.
        Returns:
            True if explicitly allowed
            False if explicitly denied
            None if no override exists (falls back to global default)
        """
        row = await fetchone(
            "SELECT is_allowed FROM user_permissions WHERE user_id = ? AND feature = ?",
            (user_id, feature)
        )
        if row is None:
            return None
        return bool(row["is_allowed"])

    @staticmethod
    async def set_user_override(user_id: int, feature: str, is_allowed: Optional[bool]) -> None:
        """Sets or removes an explicit permission override for a user."""
        if is_allowed is None:
            await execute(
                "DELETE FROM user_permissions WHERE user_id = ? AND feature = ?",
                (user_id, feature)
            )
        else:
            await execute(
                """
                INSERT INTO user_permissions (user_id, feature, is_allowed, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(user_id, feature) DO UPDATE SET
                    is_allowed = excluded.is_allowed,
                    updated_at = excluded.updated_at
                """,
                (user_id, feature, 1 if is_allowed else 0)
            )

    @staticmethod
    async def get_all_user_overrides(user_id: int) -> Dict[str, bool]:
        """Returns all explicit permission overrides for a user."""
        rows = await fetchall(
            "SELECT feature, is_allowed FROM user_permissions WHERE user_id = ?",
            (user_id,)
        )
        return {row["feature"]: bool(row["is_allowed"]) for row in rows}

    @staticmethod
    async def clear_user_override(user_id: int, feature: str) -> None:
        """Removes an override so the user follows global settings."""
        await execute(
            "DELETE FROM user_permissions WHERE user_id = ? AND feature = ?",
            (user_id, feature)
        )


class SettingsRepository:
    """Repository for managing global bot settings and default feature flags."""

    @staticmethod
    async def get_setting(key: str, default: str = "") -> str:
        """Fetches a setting value."""
        row = await fetchone("SELECT value FROM system_settings WHERE key = ?", (key,))
        return row["value"] if row else default

    @staticmethod
    async def set_setting(key: str, value: str) -> None:
        """Updates or inserts a setting value."""
        await execute(
            """
            INSERT INTO system_settings (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value)
        )

    @staticmethod
    async def is_maintenance_mode() -> bool:
        """Returns whether the bot is in maintenance mode."""
        val = await SettingsRepository.get_setting("maintenance_mode", "false")
        return val.lower() == "true"

    @staticmethod
    async def set_maintenance_mode(enabled: bool) -> None:
        """Enables or disables maintenance mode."""
        await SettingsRepository.set_setting("maintenance_mode", "true" if enabled else "false")

    @staticmethod
    async def is_whitelist_mode() -> bool:
        """Returns whether the bot is in whitelist-only mode."""
        val = await SettingsRepository.get_setting("whitelist_mode", "false")
        return val.lower() == "true"

    @staticmethod
    async def set_whitelist_mode(enabled: bool) -> None:
        """Enables or disables whitelist mode."""
        await SettingsRepository.set_setting("whitelist_mode", "true" if enabled else "false")

    @staticmethod
    async def get_feature_default(feature: str) -> bool:
        """Returns the global default state for a feature."""
        key = f"feature_{feature}"
        val = await SettingsRepository.get_setting(key, "true")
        return val.lower() == "true"

    @staticmethod
    async def set_feature_default(feature: str, enabled: bool) -> None:
        """Sets the global default state for a feature."""
        key = f"feature_{feature}"
        await SettingsRepository.set_setting(key, "true" if enabled else "false")

    @staticmethod
    async def get_all_settings() -> Dict[str, str]:
        """Returns a dictionary of all system settings."""
        rows = await fetchall("SELECT key, value FROM system_settings")
        return {row["key"]: row["value"] for row in rows}


class SessionRepository:
    """Repository for managing multi-turn conversation sessions and message history."""

    @staticmethod
    async def create_session(user_id: int, title: Optional[str] = None, model: str = "flash") -> str:
        """Creates a new session and sets it as active."""
        # Ensure user exists in users table to satisfy foreign key constraint
        user = await fetchone("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if not user:
            await execute(
                "INSERT OR IGNORE INTO users (user_id, first_name) VALUES (?, ?)",
                (user_id, f"User {user_id}")
            )

        session_id = str(uuid.uuid4())[:8]
        if not title:
            title = f"جلسة #{session_id}"

        # Deactivate previous active sessions for this user
        await execute("UPDATE sessions SET is_active = 0 WHERE user_id = ?", (user_id,))

        # Insert new session
        await execute(
            """
            INSERT INTO sessions (session_id, user_id, title, model, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, datetime('now'), datetime('now'))
            """,
            (session_id, user_id, title, model)
        )
        return session_id

    @staticmethod
    async def get_active_session(user_id: int) -> Optional[dict]:
        """Retrieves the current active session for a user or creates one."""
        session = await fetchone(
            "SELECT * FROM sessions WHERE user_id = ? AND is_active = 1 ORDER BY updated_at DESC LIMIT 1",
            (user_id,)
        )
        if not session:
            # Check if any session exists
            latest = await fetchone(
                "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
                (user_id,)
            )
            if latest:
                await execute("UPDATE sessions SET is_active = 1 WHERE session_id = ?", (latest["session_id"],))
                session = await fetchone("SELECT * FROM sessions WHERE session_id = ?", (latest["session_id"],))
            else:
                session_id = await SessionRepository.create_session(user_id)
                session = await fetchone("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        return session

    @staticmethod
    async def get_session_by_id(session_id: str) -> Optional[dict]:
        """Retrieves session details by session_id."""
        return await fetchone("SELECT * FROM sessions WHERE session_id = ?", (session_id,))

    @staticmethod
    async def set_active_session(user_id: int, session_id: str) -> bool:
        """Switches active session for a user."""
        target = await fetchone("SELECT * FROM sessions WHERE session_id = ? AND user_id = ?", (session_id, user_id))
        if not target:
            return False
        await execute("UPDATE sessions SET is_active = 0 WHERE user_id = ?", (user_id,))
        await execute("UPDATE sessions SET is_active = 1, updated_at = datetime('now') WHERE session_id = ?", (session_id,))
        return True

    @staticmethod
    async def list_user_sessions(user_id: int, limit: int = 10) -> List[dict]:
        """Lists user sessions ordered by recent activity."""
        return await fetchall(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
            (user_id, limit)
        )

    @staticmethod
    async def delete_session(session_id: str, user_id: int) -> bool:
        """Deletes a session and its associated messages."""
        session = await fetchone("SELECT * FROM sessions WHERE session_id = ? AND user_id = ?", (session_id, user_id))
        if not session:
            return False
        await execute("DELETE FROM session_messages WHERE session_id = ?", (session_id,))
        await execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        return True

    @staticmethod
    async def update_session_timestamp(session_id: str) -> None:
        """Touches updated_at timestamp for a session."""
        await execute("UPDATE sessions SET updated_at = datetime('now') WHERE session_id = ?", (session_id,))

    @staticmethod
    async def add_message(session_id: str, role: str, content: str, media_type: Optional[str] = None) -> None:
        """Records a user or model message in the session."""
        await execute(
            """
            INSERT INTO session_messages (session_id, role, content, media_type, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            (session_id, role, content, media_type)
        )
        await SessionRepository.update_session_timestamp(session_id)

    @staticmethod
    async def get_session_messages(session_id: str, limit: int = 20) -> List[dict]:
        """Retrieves recent conversation messages for a session in chronological order."""
        rows = await fetchall(
            """
            SELECT * FROM (
                SELECT * FROM session_messages 
                WHERE session_id = ? 
                ORDER BY id DESC LIMIT ?
            ) ORDER BY id ASC
            """,
            (session_id, limit)
        )
        return rows

    @staticmethod
    async def count_sessions() -> int:
        """Returns total session count."""
        res = await fetchone("SELECT COUNT(*) as count FROM sessions")
        return res["count"] if res else 0

    @staticmethod
    async def count_messages() -> int:
        """Returns total message count."""
        res = await fetchone("SELECT COUNT(*) as count FROM session_messages")
        return res["count"] if res else 0


class TaskRepository:
    """Repository for isolating tasks and sessions per user."""

    @staticmethod
    async def add_task(user_id: int, session_name: str, prompt: str, repo_name: Optional[str] = None) -> None:
        """Records a task associated strictly with a specific user."""
        clean_name = session_name if session_name.startswith("sessions/") else f"sessions/{session_name}"
        await execute(
            """
            INSERT OR REPLACE INTO user_tasks (user_id, session_name, prompt, repo_name, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            (user_id, clean_name, prompt, repo_name)
        )

    @staticmethod
    async def list_user_tasks(user_id: int, limit: int = 6) -> List[dict]:
        """Retrieves recent tasks strictly belonging to the given user."""
        return await fetchall(
            """
            SELECT * FROM user_tasks 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
            """,
            (user_id, limit)
        )

    @staticmethod
    async def is_task_owned_by_user(user_id: int, session_name: str) -> bool:
        """Verifies whether a session is owned by the specified user."""
        clean_name = session_name if session_name.startswith("sessions/") else f"sessions/{session_name}"
        res = await fetchone(
            "SELECT id FROM user_tasks WHERE user_id = ? AND (session_name = ? OR session_name = ?)",
            (user_id, session_name, clean_name)
        )
        return bool(res)


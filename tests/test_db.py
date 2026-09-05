"""
Automated unit tests for Database and Repositories.
"""

import asyncio
import os
import tempfile
import unittest
import config

temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
temp_db_path = temp_db.name
temp_db.close()

config.DATABASE_PATH = temp_db_path
config.ADMIN_IDS = [1001, 1002]

from database.db import init_db
from database.repositories import (
    UserRepository,
    PermissionRepository,
    SettingsRepository,
    SessionRepository,
    TaskRepository
)

class TestDatabase(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        config.DATABASE_PATH = temp_db_path
        config.ADMIN_IDS = [1001, 1002]
        await init_db()
        await SettingsRepository.set_maintenance_mode(False)
        await SettingsRepository.set_whitelist_mode(False)
        await UserRepository.get_or_create(12345, "testuser", "Test")

    async def test_user_creation_and_retrieval(self):
        user = await UserRepository.get_by_id(12345)
        self.assertIsNotNone(user)
        self.assertEqual(user["user_id"], 12345)
        self.assertEqual(user["username"], "testuser")
        self.assertEqual(user["is_admin"], 0)

        # Admin user
        admin_user = await UserRepository.get_or_create(1001, "adminuser", "Admin")
        self.assertEqual(admin_user["is_admin"], 1)

        # Update model
        await UserRepository.update_model(12345, "pro")
        updated = await UserRepository.get_by_id(12345)
        self.assertEqual(updated["selected_model"], "pro")

    async def test_sessions_and_messages(self):
        session_id = await SessionRepository.create_session(12345, "جلسة تجريبية", "flash")
        self.assertIsNotNone(session_id)

        active = await SessionRepository.get_active_session(12345)
        self.assertEqual(active["session_id"], session_id)
        self.assertEqual(active["title"], "جلسة تجريبية")

        # Add messages
        await SessionRepository.add_message(session_id, "user", "مرحبا")
        await SessionRepository.add_message(session_id, "model", "أهلا بك")

        messages = await SessionRepository.get_session_messages(session_id)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "model")

    async def test_settings_and_permissions(self):
        # Settings
        self.assertFalse(await SettingsRepository.is_maintenance_mode())
        await SettingsRepository.set_maintenance_mode(True)
        self.assertTrue(await SettingsRepository.is_maintenance_mode())
        await SettingsRepository.set_maintenance_mode(False)

        # Permissions override
        override = await PermissionRepository.get_user_override(12345, "upload_files")
        self.assertIsNone(override)

        await PermissionRepository.set_user_override(12345, "upload_files", False)
        self.assertFalse(await PermissionRepository.get_user_override(12345, "upload_files"))

        await PermissionRepository.set_user_override(12345, "upload_files", True)
        self.assertTrue(await PermissionRepository.get_user_override(12345, "upload_files"))

    async def test_task_isolation_and_ownership(self):
        user_a = 12345
        user_b = 67890
        await UserRepository.get_or_create(user_b, "userb", "User B")

        # User A creates tasks
        await TaskRepository.add_task(user_a, "sessions/sess-111", "Task 1 for User A", "repo-a")
        await TaskRepository.add_task(user_a, "sess-222", "Task 2 for User A", "repo-a")

        # User B creates a task
        await TaskRepository.add_task(user_b, "sessions/sess-333", "Secret Task for User B", "repo-b")

        # Verify strict isolation: User A sees only their 2 tasks
        tasks_a = await TaskRepository.list_user_tasks(user_a)
        self.assertEqual(len(tasks_a), 2)
        sess_names_a = [t["session_name"] for t in tasks_a]
        self.assertIn("sessions/sess-111", sess_names_a)
        self.assertIn("sessions/sess-222", sess_names_a)
        self.assertNotIn("sessions/sess-333", sess_names_a)

        # Verify User B sees only their 1 task
        tasks_b = await TaskRepository.list_user_tasks(user_b)
        self.assertEqual(len(tasks_b), 1)
        self.assertEqual(tasks_b[0]["session_name"], "sessions/sess-333")

        # Verify ownership checks
        self.assertTrue(await TaskRepository.is_task_owned_by_user(user_a, "sessions/sess-111"))
        self.assertTrue(await TaskRepository.is_task_owned_by_user(user_a, "sess-111"))
        self.assertFalse(await TaskRepository.is_task_owned_by_user(user_a, "sess-333"))
        self.assertFalse(await TaskRepository.is_task_owned_by_user(user_a, "sessions/sess-333"))

        self.assertTrue(await TaskRepository.is_task_owned_by_user(user_b, "sess-333"))
        self.assertFalse(await TaskRepository.is_task_owned_by_user(user_b, "sess-111"))

    async def asyncTearDown(self):
        try:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
        except Exception:
            pass

if __name__ == "__main__":
    unittest.main()

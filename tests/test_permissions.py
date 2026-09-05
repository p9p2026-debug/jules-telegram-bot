"""
Automated unit tests for PermissionService.
"""

import os
import tempfile
import unittest
import config

temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
temp_db_path = temp_db.name
temp_db.close()

from database.db import init_db
from database.repositories import (
    PermissionRepository,
    SettingsRepository,
    UserRepository
)
from services.permission_service import PermissionService

class TestPermissions(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        config.DATABASE_PATH = temp_db_path
        config.ADMIN_IDS = [99999]
        await init_db()
        await SettingsRepository.set_maintenance_mode(False)
        await SettingsRepository.set_whitelist_mode(False)
        await UserRepository.get_or_create(100, "normal_user", "Normal")
        await UserRepository.get_or_create(200, "banned_user", "Banned")
        await UserRepository.set_banned(200, True)

    async def test_admin_bypass(self):
        # Admin is 99999
        allowed, _ = await PermissionService.check_access(99999)
        self.assertTrue(allowed)

        # Even in maintenance mode, admin has access
        await SettingsRepository.set_maintenance_mode(True)
        allowed, _ = await PermissionService.check_access(99999)
        self.assertTrue(allowed)
        await SettingsRepository.set_maintenance_mode(False)

    async def test_banned_user(self):
        allowed, reason = await PermissionService.check_access(200)
        self.assertFalse(allowed)
        self.assertIn("محظور", reason)

    async def test_maintenance_mode(self):
        await SettingsRepository.set_maintenance_mode(True)
        allowed, reason = await PermissionService.check_access(100)
        self.assertFalse(allowed)
        self.assertIn("الصيانة", reason)
        await SettingsRepository.set_maintenance_mode(False)

    async def test_granular_override(self):
        # Normally upload_files is allowed globally
        allowed, _ = await PermissionService.check_access(100, "upload_files")
        self.assertTrue(allowed)

        # Deny upload_files specifically for user 100
        await PermissionRepository.set_user_override(100, "upload_files", False)
        allowed, reason = await PermissionService.check_access(100, "upload_files")
        self.assertFalse(allowed)
        self.assertIn("تقييد", reason)

        # Other features still allowed for user 100
        allowed, _ = await PermissionService.check_access(100, "send_images")
        self.assertTrue(allowed)

    async def test_admin_model_and_key_controls(self):
        # Admin can update model for all users
        await UserRepository.update_all_models("gemini-3.1-pro")
        u1 = await UserRepository.get_by_id(100)
        u2 = await UserRepository.get_by_id(200)
        self.assertEqual(u1["selected_model"], "gemini-3.1-pro")
        self.assertEqual(u2["selected_model"], "gemini-3.1-pro")

        # Admin can update model for a specific user
        await UserRepository.update_model(100, "gemini-3.7-flash")
        u1_updated = await UserRepository.get_by_id(100)
        u2_same = await UserRepository.get_by_id(200)
        self.assertEqual(u1_updated["selected_model"], "gemini-3.7-flash")
        self.assertEqual(u2_same["selected_model"], "gemini-3.1-pro")

        # Admin can assign custom key to user
        await UserRepository.update_custom_api_key(100, "AIzaSyCustomKeyForUser")
        u1_key = await UserRepository.get_by_id(100)
        self.assertEqual(u1_key["custom_api_key"], "AIzaSyCustomKeyForUser")

        # Verify admin identification
        self.assertTrue(PermissionService.is_admin(99999))
        self.assertFalse(PermissionService.is_admin(100))

    async def asyncTearDown(self):
        try:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
        except Exception:
            pass

if __name__ == "__main__":
    unittest.main()

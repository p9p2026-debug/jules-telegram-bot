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

    async def asyncTearDown(self):
        try:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
        except Exception:
            pass

if __name__ == "__main__":
    unittest.main()

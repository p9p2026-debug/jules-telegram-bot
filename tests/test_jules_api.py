"""
Unit tests for Jules REST API Client, Keyboards, and Task Monitoring.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import config
from services.jules_api_client import JulesApiClient, JulesApiException
from utils.keyboards import get_model_switch_keyboard, get_sources_keyboard

class TestJulesApiClient(unittest.TestCase):

    def test_model_switch_keyboard_has_three_models(self):
        kb = get_model_switch_keyboard(config.MODEL_CHOICE_FLASH)
        # Should have 4 rows: Flash, Pro, Agent, Close
        self.assertEqual(len(kb.inline_keyboard), 4)

        buttons = [row[0] for row in kb.inline_keyboard]
        callbacks = [btn.callback_data for btn in buttons]
        self.assertIn("user:set_model:flash", callbacks)
        self.assertIn("user:set_model:pro", callbacks)
        self.assertIn("user:set_model:agent", callbacks)
        self.assertIn("user:close", callbacks)

        # Check checkmark prefix on active flash model
        self.assertTrue(buttons[0].text.startswith("✅"))

    def test_sources_keyboard(self):
        mock_sources = [
            {
                "name": "sources/github-p9p2026-debug-jules-telegram-bot",
                "githubRepo": {"owner": "p9p2026-debug", "repo": "jules-telegram-bot"}
            },
            {
                "name": "sources/github-myorg-awesome-app",
                "githubRepo": {"owner": "myorg", "repo": "awesome-app"}
            }
        ]
        kb = get_sources_keyboard(mock_sources, selected_source="sources/github-p9p2026-debug-jules-telegram-bot")
        # 2 repos + 1 action row = 3 rows
        self.assertEqual(len(kb.inline_keyboard), 3)

        # First button should have star indicator
        self.assertIn("⭐", kb.inline_keyboard[0][0].text)
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "user:sel_src:sources/github-p9p2026-debug-jules-telegram-bot")

        # Second button should have folder indicator
        self.assertIn("📁", kb.inline_keyboard[1][0].text)
        self.assertEqual(kb.inline_keyboard[1][0].callback_data, "user:sel_src:sources/github-myorg-awesome-app")

    @patch("services.jules_api_client.urllib.request.urlopen")
    def test_list_sources_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"sources": [{"name": "sources/github-test-repo"}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        result = JulesApiClient._execute_request("sources", "GET", None, api_key="dummy_test_key")
        self.assertIn("sources", result)
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["name"], "sources/github-test-repo")

    def test_missing_api_key_raises_exception(self):
        with patch.object(config, "JULES_API_KEY", ""):
            with self.assertRaises(JulesApiException) as ctx:
                JulesApiClient._execute_request("sources", "GET", None, api_key="")
            self.assertIn("لم يتم ضبط مفتاح Jules API", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()

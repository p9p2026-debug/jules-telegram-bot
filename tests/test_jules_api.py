"""
Unit tests for Jules REST API Client, Keyboards, and Task Monitoring.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import config
from services.jules_api_client import JulesApiClient, JulesApiException
from utils.keyboards import get_model_switch_keyboard, get_sources_keyboard

class TestJulesApiClient(unittest.TestCase):

    def test_model_switch_keyboard(self):
        kb = get_model_switch_keyboard("gemini-3.6-flash")
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        callbacks = [btn.callback_data for btn in all_buttons]

        # Check canonical Jules & Studio models
        self.assertIn("user:set_model:gemini-3.6-flash", callbacks)
        self.assertIn("user:set_model:gemini-3.1-pro", callbacks)
        self.assertIn("user:set_model:gemini-3.1-flash", callbacks)
        self.assertIn("user:set_model:gemini-3.5-flash", callbacks)
        self.assertIn("user:set_model:gemini-3.7-flash", callbacks)
        self.assertIn("user:set_model:gemini-3.8-flash", callbacks)
        self.assertIn("user:set_model:agent", callbacks)
        self.assertIn("user:close", callbacks)

        # Check that active model has checkmark
        active_btn = [btn for btn in all_buttons if btn.callback_data == "user:set_model:gemini-3.6-flash"][0]
        self.assertTrue(active_btn.text.startswith("✅"))

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
        # 1 none-repo row + 2 repos + 1 action row = 4 rows
        self.assertEqual(len(kb.inline_keyboard), 4)

        # Row 0: Option to use without repo
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "user:sel_src:none")

        # Row 1: Selected repo has star indicator
        self.assertIn("⭐", kb.inline_keyboard[1][0].text)
        self.assertEqual(kb.inline_keyboard[1][0].callback_data, "user:sel_src:sources/github-p9p2026-debug-jules-telegram-bot")

        # Row 2: Unselected repo has folder indicator
        self.assertIn("📁", kb.inline_keyboard[2][0].text)
        self.assertEqual(kb.inline_keyboard[2][0].callback_data, "user:sel_src:sources/github-myorg-awesome-app")

    @patch("services.jules_api_client.urllib.request.urlopen")
    def test_list_sources_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"sources": [{"name": "sources/github-test-repo"}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        result = JulesApiClient._execute_request("sources", "GET", None, api_key="dummy_test_key")
        self.assertIn("sources", result)
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["name"], "sources/github-test-repo")

    @patch("services.jules_api_client.urllib.request.urlopen")
    def test_create_chat_session(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"name": "sessions/12345", "prompt": "test prompt"}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        result = JulesApiClient._execute_request("sessions", "POST", {"prompt": "test prompt"}, api_key="dummy_test_key")
        self.assertIn("name", result)
        self.assertEqual(result["name"], "sessions/12345")
        self.assertEqual(result["prompt"], "test prompt")

    @patch("services.jules_api_client.urllib.request.urlopen")
    def test_approve_plan(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"name": "sessions/12345"}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        result = JulesApiClient._execute_request("sessions/12345:approvePlan", "POST", {}, api_key="dummy_test_key")
        self.assertEqual(result.get("name"), "sessions/12345")

    def test_missing_api_key_raises_exception(self):
        with patch.object(config, "JULES_API_KEY", ""):
            with self.assertRaises(JulesApiException) as ctx:
                JulesApiClient._execute_request("sources", "GET", None, api_key="")
            self.assertIn("لم يتم ضبط مفتاح Jules API", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()

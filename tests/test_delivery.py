"""
Unit tests for delivery directive and embedded link extraction.
"""

import unittest
from handlers.user_handlers import build_jules_prompt_with_delivery
from services.task_monitor_service import TaskMonitorService


class TestDeliveryDirective(unittest.TestCase):

    def test_build_jules_prompt_with_delivery(self):
        prompt = "ادخل موقع الجزيرة وسويلي سكرين شت"
        result = build_jules_prompt_with_delivery(prompt, 123456, "dummy_token")
        self.assertIn("ادخل موقع الجزيرة", result)
        self.assertIn("123456", result)
        self.assertIn("dummy_token", result)
        self.assertIn("sendPhoto", result)
        self.assertIn("sendDocument", result)
        self.assertIn("tmpfiles.org", result)
        self.assertIn("CRITICAL SYSTEM IDENTITY & CONFIDENTIALITY DIRECTIVE", result)
        self.assertIn("أنا مساعدك الذكي", result)


if __name__ == "__main__":
    unittest.main()

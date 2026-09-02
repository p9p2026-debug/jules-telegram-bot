"""
Automated unit tests for RichService, RTL detection, and Table Formatting.
"""

import unittest
from services.rich_service import (
    ComposeSession,
    build_rich_payload,
    detect_direction,
    ensure_blank_before_table,
    format_tables_for_telegram,
    repair_table_rows,
    unwrap_fence
)

class TestRichService(unittest.TestCase):

    def test_detect_direction_arabic_and_english(self):
        # Pure Arabic
        self.assertTrue(detect_direction("مرحباً بك في بوت الذكاء الاصطناعي"))

        # Pure English
        self.assertFalse(detect_direction("Hello and welcome to Google Jules AI"))

        # Technical Arabic with English code blocks and URLs
        mixed = (
            "هذا كود بايثون بسيط لشرح الفكرة البرمجية:\n"
            "```python\ndef get_status():\n    return 'OK'\n```\n"
            "يمكنك مراجعة الرابط: https://github.com/example/repo"
        )
        self.assertTrue(detect_direction(mixed))

    def test_unwrap_fence(self):
        wrapped = "```markdown\n# Header\nThis is content\n```"
        unwrapped = unwrap_fence(wrapped)
        self.assertEqual(unwrapped, "# Header\nThis is content")

        normal = "Just regular text"
        self.assertEqual(unwrap_fence(normal), normal)

    def test_ensure_blank_before_and_after_table(self):
        sample = (
            "Paragraph before\n"
            "| Name | Age |\n"
            "|---|---|\n"
            "| Ali | 25 |\n"
            "Paragraph after"
        )
        processed = ensure_blank_before_table(sample)
        self.assertIn("Paragraph before\n\n| Name | Age |", processed)
        self.assertIn("| Ali | 25 |\n\nParagraph after", processed)

    def test_format_tables_for_telegram(self):
        sample = (
            "Here is the comparison table:\n"
            "| Feature | Pro | Flash |\n"
            "|---|---|---|\n"
            "| Speed | Good | Fast |\n"
            "End of report."
        )
        formatted = format_tables_for_telegram(sample)
        self.assertIn("```\n| Feature | Pro | Flash |", formatted)
        self.assertIn("| Speed | Good | Fast |\n```", formatted)

    def test_build_rich_payload(self):
        pieces = [
            {"kind": "text", "value": "# تقرير معماري شامل\n| بند | قيمة |\n|---|---|\n| الحالة | ممتاز |"},
            {"kind": "photo", "file_id": "AgACAgIAAxkBAA...", "caption": "مخطط الشبكة السحابية"}
        ]
        md, media = build_rich_payload(pieces)
        self.assertIn("![](tg://photo?id=m0 \"مخطط الشبكة السحابية\")", md)
        self.assertEqual(len(media), 1)
        self.assertEqual(media[0]["id"], "m0")
        self.assertEqual(media[0]["media"]["type"], "photo")
        self.assertEqual(media[0]["media"]["media"], "AgACAgIAAxkBAA...")

    def test_compose_session_lifecycle(self):
        session = ComposeSession(user_id=123)
        session.add_text("فقرة البداية")
        session.add_photo("photo_id_abc", "صورة رقم 1")
        session.add_text("فقرة الخاتمة")

        self.assertEqual(session.size, 3)
        desc = session.describe()
        self.assertEqual(len(desc), 3)
        self.assertIn("فقرة البداية", desc[0])
        self.assertIn("صورة", desc[1])

        # Undo
        removed = session.undo()
        self.assertEqual(removed["kind"], "text")
        self.assertEqual(session.size, 2)

        # Build
        md, media, is_rtl = session.build()
        self.assertIn("![](tg://photo?id=m0 \"صورة رقم 1\")", md)
        self.assertEqual(len(media), 1)
        self.assertTrue(is_rtl)

if __name__ == "__main__":
    unittest.main()

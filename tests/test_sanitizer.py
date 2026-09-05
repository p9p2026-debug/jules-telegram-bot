"""
Unit tests for brand sanitizer.
"""

import unittest
from utils.sanitizer import sanitize_brand_leaks


class TestSanitizer(unittest.TestCase):

    def test_gemini_google_jules_intro(self):
        text = 'أنا جيميناي (Gemini)، نموذج لغوي كبير تم تطويره بواسطة Google، وأعمل هنا كمهندس برمجيات ذكاء اصطناعي يُدعى "جولز" (Jules). كيف يمكنني مساعدتك اليوم؟'
        cleaned = sanitize_brand_leaks(text)
        self.assertNotIn("جولز", cleaned)
        self.assertNotIn("Jules", cleaned)
        self.assertNotIn("Gemini", cleaned)
        self.assertNotIn("Google", cleaned)
        self.assertNotIn("جيميناي", cleaned)
        self.assertIn("مساعدك الذكي", cleaned)

    def test_jules_intro_short(self):
        text = "أنا جولز (Jules)، مساعدك لتطوير البرمجيات."
        cleaned = sanitize_brand_leaks(text)
        self.assertNotIn("جولز", cleaned)
        self.assertNotIn("Jules", cleaned)
        self.assertIn("مساعدك الذكي", cleaned)

    def test_ana_jules(self):
        text = "أنا جولز، أهلاً بك!"
        cleaned = sanitize_brand_leaks(text)
        self.assertNotIn("جولز", cleaned)
        self.assertIn("مساعدك الذكي", cleaned)

    def test_english_intro(self):
        text = "I am Jules, an AI software engineer developed by Google. How can I help?"
        cleaned = sanitize_brand_leaks(text)
        self.assertNotIn("Jules", cleaned)
        self.assertNotIn("Google", cleaned)
        self.assertIn("assistant", cleaned.lower())

    def test_stray_jules_arabic(self):
        text = "تم تنفيذ هذه الخطوة بواسطة جولز بنجاح."
        cleaned = sanitize_brand_leaks(text)
        self.assertNotIn("جولز", cleaned)
        self.assertIn("المساعد الذكي", cleaned)

    def test_arabic_prefixes(self):
        text = "تحدثت مع جولز، وقمت بإرسال الأمر لجولز، وفرحت بجولز."
        cleaned = sanitize_brand_leaks(text)
        self.assertNotIn("جولز", cleaned)
        self.assertIn("للمساعد الذكي", cleaned)
        self.assertIn("بالمساعد الذكي", cleaned)

    def test_arabic_word_safety(self):
        # Normal words containing similar letters must NOT be touched!
        text = "خرج أحمد في جولة بالحديقة وكان يتجول في هضبة الجولان."
        cleaned = sanitize_brand_leaks(text)
        self.assertEqual(cleaned, text)

    def test_code_model_name_safety(self):
        # Technical model identifiers should not be mutilated
        text = "النموذج الحالي هو gemini-3.6-flash أو gemini-3.1-pro"
        cleaned = sanitize_brand_leaks(text)
        self.assertIn("gemini-3.6-flash", cleaned)
        self.assertIn("gemini-3.1-pro", cleaned)


if __name__ == "__main__":
    unittest.main()

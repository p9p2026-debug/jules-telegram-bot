"""
Automated unit tests for FormatService.
"""

import unittest
from services.format_service import FormatService

class TestFormatService(unittest.TestCase):

    def test_code_block_conversion(self):
        sample = "Here is Python code:\n```python\ndef hello():\n    print('Hello <world>')\n```\nDone."
        html = FormatService.markdown_to_telegram_html(sample)
        self.assertIn('<pre><code class="language-python">', html)
        self.assertIn("&lt;world&gt;", html)
        self.assertIn("</code></pre>", html)

    def test_expandable_blockquotes(self):
        sample = "> This is an important note\n> Second line of note\nNormal text"
        html = FormatService.markdown_to_telegram_html(sample)
        self.assertIn("<blockquote expandable>", html)
        self.assertIn("This is an important note\nSecond line of note", html)
        self.assertIn("</blockquote>", html)

    def test_message_splitting(self):
        # Generate long message
        long_text = "Line of text.\n\n" * 300
        chunks = FormatService.split_message(long_text, max_size=1000)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 1050)

    def test_code_block_tag_balancing_on_split(self):
        long_code = "<pre><code class=\"language-python\">\n" + ("x = 1\n" * 200) + "</code></pre>"
        chunks = FormatService.split_message(long_code, max_size=500)
        self.assertGreater(len(chunks), 1)
        # Every chunk with <pre> must have matching </pre>
        for chunk in chunks:
            self.assertEqual(chunk.count("<pre"), chunk.count("</pre>"))
            self.assertEqual(chunk.count("<code"), chunk.count("</code>"))

if __name__ == "__main__":
    unittest.main()

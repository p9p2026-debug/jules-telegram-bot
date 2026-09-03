"""
Unit Tests for Incoming Service (Telegram Entities & Rich Messages to Markdown).
"""

import unittest
from unittest.mock import MagicMock
from telegram import MessageEntity
from services.incoming_service import (
    parse_entities_to_markdown,
    extract_incoming_message
)


class TestIncomingService(unittest.TestCase):

    def test_plain_text_without_entities(self):
        text = "Hello world"
        result = parse_entities_to_markdown(text, [])
        self.assertEqual(result, text)

    def test_single_bold_entity(self):
        text = "Hello world"
        # "world" is at offset 6, length 5
        entity = MessageEntity(type=MessageEntity.BOLD, offset=6, length=5)
        result = parse_entities_to_markdown(text, [entity])
        self.assertEqual(result, "Hello **world**")

    def test_nested_entities_bold_and_italic(self):
        text = "Deep bold and italic text"
        # "bold and italic" offset 5, length 15 (bold)
        # "italic" offset 14, length 6 (italic)
        ent1 = MessageEntity(type=MessageEntity.BOLD, offset=5, length=15)
        ent2 = MessageEntity(type=MessageEntity.ITALIC, offset=14, length=6)
        result = parse_entities_to_markdown(text, [ent1, ent2])
        self.assertEqual(result, "Deep **bold and *italic*** text")

    def test_code_block_with_language(self):
        text = "print('hello')"
        ent = MessageEntity(type=MessageEntity.PRE, offset=0, length=len(text), language="python")
        result = parse_entities_to_markdown(text, [ent])
        self.assertEqual(result, "```python\nprint('hello')\n```")

    def test_blockquote_multiline(self):
        text = "Line 1\nLine 2"
        ent = MessageEntity(type=MessageEntity.BLOCKQUOTE, offset=0, length=len(text))
        result = parse_entities_to_markdown(text, [ent])
        self.assertEqual(result, "> Line 1\n> Line 2")

    def test_extract_incoming_message_object(self):
        msg = MagicMock()
        msg.rich_message = None
        msg.text = "Check this code"
        msg.caption = None
        msg.entities = [MessageEntity(type=MessageEntity.CODE, offset=11, length=4)]
        msg.caption_entities = None

        plain, md = extract_incoming_message(msg)
        self.assertEqual(plain, "Check this code")
        self.assertEqual(md, "Check this `code`")


if __name__ == "__main__":
    unittest.main()

"""
Formatting and Message Delivery Service.
Handles conversion of AI markdown to Telegram-safe HTML,
supports expandable blockquotes, code syntax highlighting,
and intelligent splitting for messages exceeding Telegram's 4096 character limit.
"""

import html
import re
from typing import List, Tuple
import logging
from telegram import Bot
from telegram.constants import ParseMode
from utils.sanitizer import sanitize_brand_leaks

logger = logging.getLogger(__name__)

class FormatService:
    """Service for transforming and splitting markdown for Telegram presentation."""

    MAX_CHUNK_SIZE = 3800  # Safe threshold below Telegram's 4096 char limit

    @staticmethod
    def markdown_to_telegram_html(text: str) -> str:
        """
        Converts standard AI Markdown into Telegram-compliant HTML.
        Supports:
        - Multiline code blocks with syntax highlighting: <pre><code class="language-xyz">
        - Inline code: <code>
        - Expandable blockquotes: <blockquote expandable>
        - Bold, Italic, Strikethrough
        - Headers
        """
        if not text:
            return ""

        # Sanitize any accidental brand or engine disclosures
        text = sanitize_brand_leaks(text)

        # Step 1: Protect and extract code blocks so internal markdown is preserved
        code_blocks: List[Tuple[str, str]] = []

        def _code_block_replacer(match: re.Match) -> str:
            lang = (match.group(1) or "").strip().lower()
            code_body = match.group(2)
            # Escape HTML characters inside code
            escaped_code = html.escape(code_body)
            placeholder = f"@@@CODEBLOCK_PH_{len(code_blocks)}@@@"
            code_blocks.append((lang, escaped_code))
            return placeholder

        # Match ```lang\ncode\n```
        text = re.sub(r"```([a-zA-Z0-9_\-\+]*)\n([\s\S]*?)```", _code_block_replacer, text)

        # Step 2: Protect inline code `code`
        inline_codes: List[str] = []

        def _inline_code_replacer(match: re.Match) -> str:
            raw_code = match.group(1)
            escaped_inline = html.escape(raw_code)
            placeholder = f"@@@INLINECODE_PH_{len(inline_codes)}@@@"
            inline_codes.append(escaped_inline)
            return placeholder

        text = re.sub(r"`([^`\n]+)`", _inline_code_replacer, text)

        # Step 3: Handle blockquotes (convert > quotes into expandable blockquotes)
        lines = text.split("\n")
        processed_lines: List[str] = []
        in_quote = False
        quote_buffer: List[str] = []

        for line in lines:
            if line.startswith("> ") or line.startswith(">"):
                quote_text = line[1:].lstrip()
                in_quote = True
                quote_buffer.append(quote_text)
            else:
                if in_quote:
                    joined_quote = "\n".join(quote_buffer)
                    escaped_quote = html.escape(joined_quote)
                    processed_lines.append(f"<blockquote expandable>{escaped_quote}</blockquote>")
                    quote_buffer = []
                    in_quote = False
                processed_lines.append(line)

        if in_quote:
            joined_quote = "\n".join(quote_buffer)
            escaped_quote = html.escape(joined_quote)
            processed_lines.append(f"<blockquote expandable>{escaped_quote}</blockquote>")

        text = "\n".join(processed_lines)

        # Step 4: Escape remaining HTML outside of protected tags
        parts = re.split(r"(<blockquote expandable>[\s\S]*?</blockquote>)", text)
        escaped_parts = []
        for part in parts:
            if part.startswith("<blockquote expandable>"):
                escaped_parts.append(part)
            else:
                escaped_parts.append(html.escape(part))
        text = "".join(escaped_parts)

        # Step 5: Convert Markdown bold, italic, strikethrough, and headers
        # Headers: ### Header -> <b><u>Header</u></b>
        text = re.sub(r"^(?:#{1,6})\s+(.+)$", r"<b><u>\1</u></b>", text, flags=re.MULTILINE)

        # Bold: **text** or __text__
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

        # Italic: *text* or _text_
        text = re.sub(r"(?<!\w)\*([^\*\n]+)\*(?!\w)", r"<i>\1</i>", text)
        text = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"<i>\1</i>", text)

        # Strikethrough: ~~text~~
        text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)

        # Step 6: Restore inline codes
        for idx, code_content in enumerate(inline_codes):
            placeholder = f"@@@INLINECODE_PH_{idx}@@@"
            text = text.replace(placeholder, f"<code>{code_content}</code>")

        # Step 7: Restore code blocks with language classes
        for idx, (lang, code_content) in enumerate(code_blocks):
            placeholder = f"@@@CODEBLOCK_PH_{idx}@@@"
            if lang:
                replacement = f'<pre><code class="language-{lang}">{code_content}</code></pre>'
            else:
                replacement = f"<pre><code>{code_content}</code></pre>"
            text = text.replace(placeholder, replacement)

        return text

    @staticmethod
    def split_message(text: str, max_size: int = MAX_CHUNK_SIZE) -> List[str]:
        """
        Splits a long message into smaller safe chunks, ensuring that
        code blocks (<pre><code> ... </code></pre>) are closed properly before splitting
        and reopened in subsequent chunks.
        """
        if len(text) <= max_size:
            return [text]

        chunks: List[str] = []
        remaining = text

        while remaining:
            if len(remaining) <= max_size:
                chunks.append(remaining)
                break

            # Find a convenient breakpoint (double newline or newline)
            split_index = remaining.rfind("\n\n", 0, max_size)
            if split_index == -1 or split_index < max_size // 2:
                split_index = remaining.rfind("\n", 0, max_size)
            if split_index == -1 or split_index < max_size // 2:
                split_index = remaining.rfind(" ", 0, max_size)
            if split_index == -1:
                split_index = max_size

            chunk = remaining[:split_index].strip()
            remaining = remaining[split_index:].lstrip()

            # Ensure balanced pre/code tags
            pre_open_count = chunk.count("<pre")
            pre_close_count = chunk.count("</pre>")
            code_open_count = chunk.count("<code")
            code_close_count = chunk.count("</code>")

            if pre_open_count > pre_close_count:
                # Find the last open pre tag to preserve language class if any
                last_pre_match = list(re.finditer(r"<pre(?: class=\"language-([^\"]+)\")?>", chunk))
                lang = ""
                if last_pre_match:
                    lang = last_pre_match[-1].group(1) or ""

                # Close tags in current chunk
                if code_open_count > code_close_count:
                    chunk += "</code>"
                chunk += "</pre>"

                # Reopen in remaining
                reopen_tag = f'<pre><code class="language-{lang}">' if lang else "<pre><code>"
                remaining = reopen_tag + remaining

            # Ensure balanced blockquote tags
            bq_open_count = chunk.count("<blockquote")
            bq_close_count = chunk.count("</blockquote>")
            if bq_open_count > bq_close_count:
                chunk += "</blockquote>"
                remaining = "<blockquote expandable>" + remaining

            chunks.append(chunk)

        return chunks

    @classmethod
    async def send_smart_message(
        cls,
        bot: Bot,
        chat_id: int,
        raw_markdown_text: str,
        reply_to_message_id: int = None
    ) -> List[int]:
        """
        Processes AI markdown, converts it to Telegram HTML, splits it if necessary,
        and safely transmits all chunks. Falls back to plain text if HTML rendering fails.
        """
        formatted_html = cls.markdown_to_telegram_html(raw_markdown_text)
        chunks = cls.split_message(formatted_html)
        sent_message_ids: List[int] = []

        for i, chunk in enumerate(chunks):
            reply_id = reply_to_message_id if i == 0 else None
            try:
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    parse_mode=ParseMode.HTML,
                    reply_to_message_id=reply_id,
                    disable_web_page_preview=True
                )
                sent_message_ids.append(msg.message_id)
            except Exception as exc:
                logger.warning("HTML parse failed for chunk, falling back to plain text: %s", exc)
                plain_chunk = re.sub(r"<[^>]+>", "", chunk)
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=plain_chunk or "...",
                    parse_mode=None,
                    reply_to_message_id=reply_id,
                    disable_web_page_preview=True
                )
                sent_message_ids.append(msg.message_id)

        return sent_message_ids

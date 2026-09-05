"""
Rich Message & Compose Service.
Inspired by Telegram Bot API sendRichMessage and gptcopy-main techniques.
Provides:
1. Pure functions for Arabic RTL detection, table repairing, and mobile formatting.
2. Direct integration with sendRichMessage Telegram endpoint with 3-tier fallback.
3. Embedded inline media handling (e.g. ![](tg://photo?id=m0 "Caption")).
4. Interactive multi-part message composer (ComposeSession).
"""

import html
import json
import logging
import re
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from telegram import Bot, InputMediaPhoto
from telegram.constants import ParseMode
import config
from services.format_service import FormatService
from utils.sanitizer import sanitize_brand_leaks

logger = logging.getLogger(__name__)

RTL_LETTERS = re.compile(r"[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
RTL_THRESHOLD = 0.2  # 20% Arabic threshold to account for technical English words

def detect_direction(text: str, threshold: float = RTL_THRESHOLD) -> bool:
    """
    Detects whether the text should be treated as RTL (Right-to-Left).
    Excludes code blocks, inline code, and URLs so technical snippets
    do not falsely skew the Arabic language detection.
    """
    if not text:
        return False

    # Strip code blocks, inline code, and URLs
    stripped = re.sub(r"```[\s\S]*?```", " ", text)
    stripped = re.sub(r"`[^`\n]*`", " ", stripped)
    stripped = re.sub(r"https?://\S+", " ", stripped)

    # Exclude table rows first to judge by narrative prose
    lines = stripped.split("\n")
    prose = "\n".join([line for line in lines if not re.match(r"^\s*\|", line)])

    rtl_count = len(RTL_LETTERS.findall(prose))
    latin_count = len(re.findall(r"[A-Za-z]", prose))

    if rtl_count + latin_count == 0:
        # If document is mostly tables, judge by the full stripped text
        rtl_count = len(RTL_LETTERS.findall(stripped))
        latin_count = len(re.findall(r"[A-Za-z]", stripped))

    total = rtl_count + latin_count
    if total == 0:
        return False

    ratio = rtl_count / total
    return ratio >= threshold


def unwrap_fence(text: str) -> str:
    """Strips outer code fence if the entire text was wrapped in ```...```."""
    m = re.match(r"^\s*```[a-zA-Z]*\n([\s\S]*?)\n?```\s*$", text)
    return m.group(1) if m else text


def cell_count(line: str) -> int:
    """Counts table cells in a line, ignoring outer pipes."""
    parts = line.strip().split("|")
    if parts and parts[0].strip() == "":
        parts.pop(0)
    if parts and parts[-1].strip() == "":
        parts.pop()
    return len(parts)


def is_delimiter_row(line: str) -> bool:
    """Checks if a line is a markdown table delimiter row like |---|---|."""
    return bool(re.match(r"^\s*\|[\s:|-]*-[\s:|-]*\|\s*$", line))


def repair_table_rows(md: str, max_join: int = 8) -> str:
    """
    Repairs table rows that were accidentally broken across multiple lines
    due to copy-paste or AI output.
    """
    lines = md.split("\n")
    out = []
    expected = 0
    i = 0

    while i < lines.length if hasattr(lines, "length") else i < len(lines):
        line = lines[i]

        if line.strip() == "":
            expected = 0
            out.append(line)
            i += 1
            continue

        if is_delimiter_row(line):
            expected = cell_count(line)
            out.append(line)
            i += 1
            continue

        if re.match(r"^\s*\|", line):
            def is_complete(s: str) -> bool:
                return bool(re.search(r"\|\s*$", s)) and (expected == 0 or cell_count(s) >= expected)

            next_is_row = bool(re.match(r"^\s*\|", lines[i + 1])) if (i + 1 < len(lines)) else False
            incomplete = (
                (cell_count(line) < expected or (not re.search(r"\|\s*$", line) and not next_is_row))
                if expected > 0
                else (not re.search(r"\|\s*$", line) and not next_is_row)
            )

            if incomplete:
                joined = line.rstrip()
                j = i + 1
                steps = 0
                while j < len(lines) and steps < max_join and not is_complete(joined):
                    if lines[j].strip() == "":
                        break
                    joined += " " + lines[j].strip()
                    j += 1
                    steps += 1

                if is_complete(joined) and j > i + 1:
                    out.append(joined)
                    i = j
                    continue

        out.append(line)
        i += 1

    return "\n".join(out)


def ensure_blank_before_table(md: str) -> str:
    """
    Ensures a blank line exists immediately before and after every markdown table.
    Telegram markdown requires blank lines around tables to render them as tables.
    """
    lines = md.split("\n")
    out = []

    def is_table(line_str: str) -> bool:
        return bool(re.match(r"^\s*\|", line_str))

    for i, line in enumerate(lines):
        is_table_line = is_table(line)
        prev_empty = (i == 0) or (lines[i - 1].strip() == "")
        prev_is_table = (i > 0) and is_table(lines[i - 1])

        # First line of table after regular text: insert empty line before
        if is_table_line and not prev_empty and not prev_is_table:
            out.append("")

        out.append(line)

        # After the last line of table: insert empty line after
        if is_table_line and (i + 1 < len(lines)):
            next_line = lines[i + 1]
            if next_line.strip() != "" and not is_table(next_line):
                out.append("")

    return "\n".join(out)


def format_tables_for_telegram(text: str) -> str:
    """
    Wraps markdown tables into monospace code blocks (```)
    for optimal mobile screen readability when falling back to standard Telegram messages.
    """
    if not text:
        return ""
    lines = text.split("\n")
    result = []
    in_table = False
    table_lines = []

    for line in lines:
        if re.match(r"^\s*\|", line):
            if not in_table:
                in_table = True
            table_lines.append(line)
        else:
            if in_table:
                in_table = False
                result.append("```")
                result.extend(table_lines)
                result.append("```")
                table_lines = []
            result.append(line)

    if in_table:
        result.append("```")
        result.extend(table_lines)
        result.append("```")

    return "\n".join(result)


def sanitize_caption(caption: Optional[str]) -> str:
    """Escapes quotes and cleans caption for inline tg:// media link."""
    if not caption:
        return ""
    return re.sub(r"\s+", " ", caption).replace("\\", "\\\\").replace('"', '\\"').strip()


def build_rich_payload(pieces: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Builds a unified rich markdown document with embedded media references:
    ![](tg://photo?id=m0 "Caption")
    and compiles the corresponding Telegram media array.
    """
    blocks: List[str] = []
    media_list: List[Dict[str, Any]] = []

    for piece in pieces:
        kind = piece.get("kind", "text")

        if kind == "text":
            val = unwrap_fence(piece.get("value", ""))
            val = repair_table_rows(val)
            val = ensure_blank_before_table(val).strip()
            if val:
                blocks.append(val)
            continue

        file_id = piece.get("file_id")
        if not file_id:
            continue

        media_id = f"m{len(media_list)}"
        input_type = "photo" if kind == "photo" else ("document" if kind == "document" else "video")
        link_kind = "photo" if kind == "photo" else ("document" if kind == "document" else "video")

        media_list.append({
            "id": media_id,
            "media": {
                "type": input_type,
                "media": file_id
            }
        })

        raw_cap = piece.get("caption") or ""
        clean_cap = sanitize_caption(raw_cap)
        title_attr = f' "{clean_cap}"' if clean_cap else ""
        blocks.append(f"![]({link_kind}://tg?id={media_id}{title_attr})".replace(f"{link_kind}://tg", f"tg://{link_kind}"))

    markdown_doc = "\n\n".join(blocks)
    return markdown_doc, media_list


class ComposeSession:
    """In-memory draft container for building a multi-part rich message."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.pieces: List[Dict[str, Any]] = []

    def add_text(self, text: str) -> None:
        self.pieces.append({"kind": "text", "value": text})

    def add_photo(self, file_id: str, caption: Optional[str] = None) -> None:
        self.pieces.append({"kind": "photo", "file_id": file_id, "caption": caption})

    def add_document(self, file_id: str, caption: Optional[str] = None) -> None:
        self.pieces.append({"kind": "document", "file_id": file_id, "caption": caption})

    def undo(self) -> Optional[Dict[str, Any]]:
        return self.pieces.pop() if self.pieces else None

    def clear(self) -> None:
        self.pieces.clear()

    @property
    def size(self) -> int:
        return len(self.pieces)

    def describe(self) -> List[str]:
        desc = []
        for i, p in enumerate(self.pieces, 1):
            kind = p.get("kind")
            if kind == "text":
                val = p.get("value", "").replace("\n", " ")[:40]
                desc.append(f"{i}. 📝 نص: {val}...")
            elif kind == "photo":
                cap = f" (كابشن: {p.get('caption')[:25]})" if p.get("caption") else ""
                desc.append(f"{i}. 🖼️ صورة{cap}")
            else:
                desc.append(f"{i}. 📁 ملف / مستند")
        return desc

    def build(self) -> Tuple[str, List[Dict[str, Any]], bool]:
        md, media = build_rich_payload(self.pieces)
        is_rtl = detect_direction(md)
        return md, media, is_rtl


class ComposeStore:
    """Manages active compose sessions per user."""
    _store: Dict[int, ComposeSession] = {}

    @classmethod
    def get_or_create(cls, user_id: int) -> ComposeSession:
        if user_id not in cls._store:
            cls._store[user_id] = ComposeSession(user_id)
        return cls._store[user_id]

    @classmethod
    def get(cls, user_id: int) -> Optional[ComposeSession]:
        return cls._store.get(user_id)

    @classmethod
    def is_composing(cls, user_id: int) -> bool:
        return user_id in cls._store

    @classmethod
    def remove(cls, user_id: int) -> Optional[ComposeSession]:
        return cls._store.pop(user_id, None)


class RichService:
    """High-level service coordinating Rich Message transmission with graceful fallbacks."""

    @staticmethod
    def call_raw_api(bot_token: str, method: str, payload: dict) -> dict:
        """Invokes Telegram Bot API via raw JSON POST request."""
        url = f"https://api.telegram.org/bot{bot_token}/{method}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "AIAssistantBot"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @classmethod
    async def deliver_rich(
        cls,
        bot: Bot,
        chat_id: int,
        raw_markdown: str,
        media: Optional[List[Dict[str, Any]]] = None,
        reply_markup: Optional[Any] = None,
        reply_to_message_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes the 3-Tier Delivery Ladder:
        Tier 1: sendRichMessage (Rich Markdown + Tables + Inline Media in ONE message)
        Tier 2: sendMediaGroup (or sendPhoto) + smart split Markdown/HTML
        Tier 3: Plain text safe transmission
        """
        # Step 1: Sanitize brand leaks and repair markdown
        raw_markdown = sanitize_brand_leaks(raw_markdown)
        repaired_md = unwrap_fence(raw_markdown)
        repaired_md = repair_table_rows(repaired_md)
        repaired_md = ensure_blank_before_table(repaired_md)
        is_rtl = detect_direction(repaired_md)

        # -------------------------------------------------------------
        # Tier 1: Try sendRichMessage directly
        # -------------------------------------------------------------
        try:
            payload = {
                "chat_id": chat_id,
                "rich_message": {
                    "markdown": repaired_md,
                    "is_rtl": is_rtl,
                }
            }
            if media and len(media) > 0:
                payload["rich_message"]["media"] = media
            if reply_markup:
                # Convert reply_markup to dict if object
                if hasattr(reply_markup, "to_dict"):
                    payload["reply_markup"] = reply_markup.to_dict()
                else:
                    payload["reply_markup"] = reply_markup
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id

            # Call API in executor thread to prevent blocking
            import asyncio
            res = await asyncio.to_thread(cls.call_raw_api, config.BOT_TOKEN, "sendRichMessage", payload)
            if res.get("ok"):
                logger.info("Delivered via sendRichMessage successfully to chat %s", chat_id)
                return {"ok": True, "via": "rich", "result": res.get("result")}
        except Exception as exc:
            logger.debug("sendRichMessage API attempt failed or unsupported (%s), falling back to Tier 2", exc)

        # -------------------------------------------------------------
        # Tier 2: Fallback - Separate Media + Formatted Table Text
        # -------------------------------------------------------------
        try:
            # Send media first if present
            if media and len(media) > 0:
                # Clean tg:// media links from markdown body so reader doesn't see dead links
                cleaned_text = re.sub(r"!\[[^\]]*\]\(tg://[^\)]+\)", "", repaired_md).strip()
                photos = [m["media"]["media"] for m in media if m.get("media", {}).get("type") == "photo"]

                if len(photos) == 1:
                    # Single photo with caption if short, or sent before text
                    await bot.send_photo(chat_id=chat_id, photo=photos[0])
                elif len(photos) > 1:
                    media_group = [InputMediaPhoto(media=p) for p in photos[:10]]
                    await bot.send_media_group(chat_id=chat_id, media=media_group)

                # Send text with formatted tables
                formatted_md = format_tables_for_telegram(cleaned_text or repaired_md)
                await FormatService.send_smart_message(
                    bot=bot,
                    chat_id=chat_id,
                    raw_markdown_text=formatted_md,
                    reply_to_message_id=reply_to_message_id
                )
                return {"ok": True, "via": "fallback_media"}
            else:
                # No media, send text with formatted tables
                formatted_md = format_tables_for_telegram(repaired_md)
                await FormatService.send_smart_message(
                    bot=bot,
                    chat_id=chat_id,
                    raw_markdown_text=formatted_md,
                    reply_to_message_id=reply_to_message_id
                )
                return {"ok": True, "via": "fallback_text"}

        except Exception as exc2:
            logger.warning("Tier 2 fallback failed: %s, falling back to Tier 3 plain text", exc2)

        # -------------------------------------------------------------
        # Tier 3: Plain text safe delivery
        # -------------------------------------------------------------
        plain = re.sub(r"<[^>]+>", "", repaired_md)
        await bot.send_message(
            chat_id=chat_id,
            text=plain or "...",
            parse_mode=None,
            reply_to_message_id=reply_to_message_id
        )
        return {"ok": True, "via": "plain"}

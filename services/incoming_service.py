"""
Incoming Message Parser Service.
Translates incoming Telegram rich messages and entity-formatted texts into clean Markdown.
Inspired by Telegram Bot API 2026 specifications and incoming.mjs techniques.
"""

import logging
from typing import Any, List, Optional, Tuple
from telegram import Message, MessageEntity

logger = logging.getLogger(__name__)

INLINE_WRAP = {
    MessageEntity.BOLD: lambda s: f"**{s}**",
    MessageEntity.ITALIC: lambda s: f"*{s}*",
    MessageEntity.STRIKETHROUGH: lambda s: f"~~{s}~~",
    MessageEntity.UNDERLINE: lambda s: f"<u>{s}</u>",
    MessageEntity.SPOILER: lambda s: f"<tg-spoiler>{s}</tg-spoiler>",
    MessageEntity.CODE: lambda s: f"`{s}`",
}

BLOCK_QUOTES = {
    MessageEntity.BLOCKQUOTE,
    getattr(MessageEntity, "EXPANDABLE_BLOCKQUOTE", "expandable_blockquote")
}


def _quote_lines(text: str) -> str:
    """Prepends markdown quote marker to each line."""
    return "\n".join(f"> {line}" for line in text.splitlines())


class _EntityNode:
    def __init__(self, entity: MessageEntity):
        self.entity = entity
        self.children: List["_EntityNode"] = []


def _build_entity_tree(entities: List[MessageEntity]) -> List[_EntityNode]:
    """
    Builds a tree of nested Telegram message entities sorted by offset and length.
    Prevents corrupt intersecting markdown tags when bold/italic overlap.
    """
    sorted_entities = sorted(
        [e for e in entities if e and e.length > 0],
        key=lambda e: (e.offset, -e.length)
    )

    roots: List[_EntityNode] = []
    stack: List[_EntityNode] = []

    for ent in sorted_entities:
        node = _EntityNode(ent)
        end = ent.offset + ent.length

        while stack:
            top = stack[-1].entity
            if top.offset + top.length <= ent.offset:
                stack.pop()
            else:
                break

        if stack:
            parent = stack[-1]
            if end <= parent.entity.offset + parent.entity.length:
                parent.children.append(node)
            else:
                # Partial crossing, ignore to avoid broken markdown
                continue
        else:
            roots.append(node)

        stack.append(node)

    return roots


def _render_entity_tree(utf16_units: List[str], nodes: List[_EntityNode], start: int, end: int) -> str:
    """Renders UTF-16 code units into formatted markdown using entity tree."""
    out = []
    cursor = start

    for node in nodes:
        ent = node.entity
        ent_start = ent.offset
        ent_end = ent.offset + ent.length

        if ent_start > cursor:
            out.append("".join(utf16_units[cursor:ent_start]))

        inner = _render_entity_tree(utf16_units, node.children, ent_start, ent_end)
        ent_type = ent.type

        if ent_type in INLINE_WRAP:
            out.append(INLINE_WRAP[ent_type](inner))
        elif ent_type == MessageEntity.PRE:
            lang = ent.language or ""
            out.append(f"```{lang}\n{inner}\n```")
        elif ent_type in BLOCK_QUOTES:
            out.append(_quote_lines(inner))
        elif ent_type == MessageEntity.TEXT_LINK and ent.url:
            out.append(f"[{inner}]({ent.url})")
        else:
            out.append(inner)

        cursor = ent_end

    if cursor < end:
        out.append("".join(utf16_units[cursor:end]))

    return "".join(out)


def parse_entities_to_markdown(text: str, entities: Optional[List[MessageEntity]]) -> str:
    """
    Converts plain text + Telegram UTF-16 MessageEntities into clean Markdown.
    """
    if not text:
        return ""
    if not entities:
        return text

    # Telegram entity offsets are in UTF-16 code units
    encoded = text.encode("utf-16-le")
    utf16_units = [encoded[i:i+2].decode("utf-16-le", errors="ignore") for i in range(0, len(encoded), 2)]

    tree = _build_entity_tree(entities)
    return _render_entity_tree(utf16_units, tree, 0, len(utf16_units))


def extract_incoming_message(message: Message) -> Tuple[str, str]:
    """
    Extracts plain text and formatted markdown from any incoming Telegram message.
    Handles:
    - Standard text with formatting entities
    - Media captions with formatting entities
    - Rich messages (Telegram 2026 rich_message attribute)
    Returns:
        Tuple[str, str]: (plain_text_for_command_routing, markdown_text_for_ai)
    """
    # 1. Check if raw rich_message payload exists
    rich_payload = getattr(message, "rich_message", None)
    if isinstance(rich_payload, dict):
        rich_md = rich_payload.get("markdown")
        if rich_md:
            return rich_md, rich_md

    # 2. Extract standard text or caption
    raw_text = message.text or message.caption or ""
    entities = message.entities or message.caption_entities or []

    if not raw_text:
        return "", ""

    if not entities:
        return raw_text, raw_text

    markdown_text = parse_entities_to_markdown(raw_text, entities)
    return raw_text, markdown_text

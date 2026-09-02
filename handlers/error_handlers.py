"""
Global Error Handler Module for Jules Telegram Bot.
Catches, logs, and safely reports runtime exceptions without crashing the bot.
"""

import html
import json
import logging
import traceback
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes
import config

logger = logging.getLogger(__name__)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Logs the error and notifies the user with a friendly message."""
    if isinstance(context.error, BadRequest) and "message is not modified" in str(context.error).lower():
        # Benign Telegram error when a user presses a button resulting in identical markup/text
        logger.debug("Silently ignoring 'Message is not modified' error.")
        return

    logger.error("Exception while handling an update:", exc_info=context.error)

    # Format traceback for logging
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    logger.debug("Update payload that caused error: %s", update_str)

    user_message = (
        "⚠️ **عذراً، حدث خطأ غير متوقع أثناء معالجة طلبك.**\n\n"
        "تم تسجيل الخطأ وإشعار الدعم الفني لمراجعته."
    )

    if isinstance(update, Update):
        if update.effective_message:
            try:
                await update.effective_message.reply_text(
                    user_message,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass
        elif update.callback_query:
            try:
                await update.callback_query.answer("⚠️ حدث خطأ أثناء تنفيذ الأمر.", show_alert=True)
            except Exception:
                pass

    # Optionally notify superadmin if critical
    if config.ADMIN_IDS and context.bot:
        admin_alert = (
            f"🚨 <b>تنبيه خطأ برمجي (Bot Error):</b>\n\n"
            f"<pre><code>{html.escape(str(context.error)[:400])}</code></pre>"
        )
        for admin_id in config.ADMIN_IDS[:1]:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_alert,
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass

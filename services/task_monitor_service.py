"""
Task Monitor Service.
Polls Jules API asynchronous coding sessions and provides live progress
updates directly inside the Telegram chat by editing status messages.
"""

import asyncio
import logging
from typing import Optional
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError
from services.jules_api_client import JulesApiClient

logger = logging.getLogger(__name__)

class TaskMonitorService:
    """Monitors running autonomous tasks on Jules API and streams updates to Telegram."""

    @classmethod
    async def start_monitoring(
        cls,
        bot: Bot,
        chat_id: int,
        status_message_id: int,
        session_name: str,
        repo_name: str,
        prompt: str,
        api_key: Optional[str] = None
    ) -> None:
        """Launches background monitoring task."""
        asyncio.create_task(
            cls._monitor_loop(
                bot=bot,
                chat_id=chat_id,
                message_id=status_message_id,
                session_name=session_name,
                repo_name=repo_name,
                prompt=prompt,
                api_key=api_key
            )
        )

    @classmethod
    async def _monitor_loop(
        cls,
        bot: Bot,
        chat_id: int,
        message_id: int,
        session_name: str,
        repo_name: str,
        prompt: str,
        api_key: Optional[str] = None,
        max_iterations: int = 50,
        interval_seconds: int = 6
    ) -> None:
        """Internal polling loop."""
        last_rendered_text = ""

        for _ in range(max_iterations):
            await asyncio.sleep(interval_seconds)

            try:
                session_data = await JulesApiClient.get_session(session_name, api_key)
                state = session_data.get("state", "RUNNING").upper()
                activities = await JulesApiClient.list_activities(session_name, api_key)

                # Check if Pull Request was opened
                outputs = session_data.get("outputs", {})
                pr_info = outputs.get("pullRequest", {})
                pr_url = pr_info.get("url") or pr_info.get("htmlUrl")

                # Extract latest activity notes
                latest_activity = "جاري استنساخ وفحص المستودع..."
                if activities:
                    last_act = activities[-1]
                    latest_activity = (
                        last_act.get("description")
                        or last_act.get("summary")
                        or last_act.get("title")
                        or latest_activity
                    )

                # Terminal: COMPLETED
                if state in ["COMPLETED", "SUCCEEDED"] or pr_url:
                    final_text = (
                        "🎉 <b>تم إنجاز المهمة البرمجية بنجاح!</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📁 <b>المستودع:</b> <code>{repo_name}</code>\n"
                        f"📝 <b>الطلب:</b> <i>{prompt}</i>\n\n"
                        "✨ <b>خطوات الإنجاز:</b>\n"
                        "• [✅] فحص وتحليل بنية المشروع\n"
                        "• [✅] وضع خطة التعديل البرمجي\n"
                        "• [✅] تطبيق التعديلات وكتابة الأكواد\n"
                        "• [✅] إنشاء الفرع وفتح Pull Request\n"
                        "━━━━━━━━━━━━━━━━━━━━━\n"
                    )
                    buttons = []
                    if pr_url:
                        final_text += f"🔗 <b>رابط الـ Pull Request:</b>\n{pr_url}\n"
                        buttons.append([InlineKeyboardButton("🚀 معاينة الـ Pull Request على GitHub", url=pr_url)])

                    keyboard = InlineKeyboardMarkup(buttons) if buttons else None
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=final_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard,
                        disable_web_page_preview=False
                    )
                    return

                # Terminal: FAILED
                if state in ["FAILED", "ERROR", "CANCELLED"]:
                    error_msg = session_data.get("error", {}).get("message", "فشلت العملية أثناء تنفيذ الأكواد.")
                    fail_text = (
                        "❌ <b>تعذر استكمال المهمة البرمجية</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📁 <b>المستودع:</b> <code>{repo_name}</code>\n"
                        f"⚠️ <b>السبب:</b> {error_msg}\n"
                        "━━━━━━━━━━━━━━━━━━━━━\n"
                        "يرجى مراجعة إعدادات المستودع وصلاحيات الحساب."
                    )
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=fail_text,
                        parse_mode=ParseMode.HTML
                    )
                    return

                # In-Progress state update
                progress_text = (
                    "🛠️ <b>جاري تنفيذ المهمة البرمجية آلياً...</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📁 <b>المستودع:</b> <code>{repo_name}</code>\n"
                    f"📝 <b>الطلب:</b> <i>{prompt}</i>\n"
                    f"🔄 <b>النشاط الحالي:</b> {latest_activity}\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    "<i>تتحدث هذه الرسالة تلقائياً مع تقدم العمل...</i>"
                )

                if progress_text != last_rendered_text:
                    last_rendered_text = progress_text
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=progress_text,
                        parse_mode=ParseMode.HTML
                    )

            except TelegramError as tg_err:
                if "Message is not modified" not in str(tg_err):
                    logger.debug("Telegram edit notice: %s", tg_err)
            except Exception as exc:
                logger.warning("Error in task monitor loop: %s", exc)

        # Timeout notification
        try:
            timeout_text = (
                "⏳ <b>المهمة استغرقت وقتاً طويلاً</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 <b>المستودع:</b> <code>{repo_name}</code>\n"
                "الوكيل لا يزال يعمل في الخلفية على خوادم Google Cloud. يمكنك مراجعة حالة الـ PR لاحقاً عبر /tasks."
            )
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=timeout_text,
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass

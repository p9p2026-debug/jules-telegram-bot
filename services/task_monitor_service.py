"""
Task Monitor Service.
Polls Jules API asynchronous coding sessions and provides live progress
updates directly inside the Telegram chat, and delivers the generated
files and code artifacts directly to Telegram as documents and messages.
"""

import asyncio
import io
import json
import logging
import os
import urllib.request
from typing import Dict, List, Optional, Tuple
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError
from database.repositories import SettingsRepository
from services.jules_api_client import JulesApiClient

logger = logging.getLogger(__name__)

class TaskMonitorService:
    """Monitors running autonomous tasks on Jules API and streams updates & artifacts to Telegram."""

    @classmethod
    async def start_monitoring(
        cls,
        bot: Bot,
        chat_id: int,
        status_message_id: int,
        session_name: str,
        repo_name: str,
        prompt: str,
        user_id: Optional[int] = None,
        api_key: Optional[str] = None
    ) -> None:
        """Launches background monitoring task."""
        effective_user_id = user_id or chat_id
        asyncio.create_task(
            cls._monitor_loop(
                bot=bot,
                chat_id=chat_id,
                message_id=status_message_id,
                session_name=session_name,
                repo_name=repo_name,
                prompt=prompt,
                user_id=effective_user_id,
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
        user_id: int,
        api_key: Optional[str] = None,
        max_iterations: int = 60,
        interval_seconds: int = 5
    ) -> None:
        """Internal polling loop."""
        last_rendered_text = ""

        for _ in range(max_iterations):
            await asyncio.sleep(interval_seconds)

            try:
                session_data = await JulesApiClient.get_session(session_name, api_key)
                state = session_data.get("state", "RUNNING").upper()
                activities = await JulesApiClient.list_activities(session_name, api_key)

                # Check if Pull Request was opened (outputs is a list or dict)
                raw_outputs = session_data.get("outputs", [])
                pr_url = None
                if isinstance(raw_outputs, list):
                    for item in raw_outputs:
                        if isinstance(item, dict) and "pullRequest" in item:
                            pr_url = item["pullRequest"].get("url") or item["pullRequest"].get("htmlUrl")
                            if pr_url:
                                break
                elif isinstance(raw_outputs, dict):
                    pr_info = raw_outputs.get("pullRequest", {})
                    pr_url = pr_info.get("url") or pr_info.get("htmlUrl")

                # Extract latest activity notes
                latest_activity = "جاري استنساخ وفحص المستودع..."
                if activities:
                    last_act = activities[-1]
                    latest_activity = (
                        last_act.get("description")
                        or last_act.get("summary")
                        or last_act.get("title")
                        or (last_act.get("agentMessaged", {}).get("agentMessage") if "agentMessaged" in last_act else None)
                        or (last_act.get("progressUpdated", {}).get("description") if "progressUpdated" in last_act else None)
                        or latest_activity
                    )

                # Terminal: COMPLETED
                if state in ["COMPLETED", "SUCCEEDED"] or pr_url:
                    clean_id = session_name.replace("sessions/", "")
                    final_text = (
                        "🎉 <b>تم إنجاز المهمة البرمجية بنجاح!</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📁 <b>المستودع:</b> <code>{repo_name}</code>\n"
                        f"📝 <b>الطلب:</b> <i>{prompt}</i>\n\n"
                        "✨ <b>خطوات الإنجاز:</b>\n"
                        "• [✅] فحص وتحليل بنية المشروع\n"
                        "• [✅] وضع خطة التعديل البرمجي\n"
                        "• [✅] تطبيق التعديلات وتوليد الملفات\n"
                        "• [✅] إنشاء الفرع وفتح Pull Request\n"
                        "━━━━━━━━━━━━━━━━━━━━━\n"
                        "📦 <i>جاري سحب وإرسال الملفات الناتجة إلى الشات فوراً...</i>\n"
                    )

                    buttons = []
                    if pr_url:
                        final_text += f"\n🔗 <b>رابط الـ Pull Request:</b>\n{pr_url}\n"
                        buttons.append([
                            InlineKeyboardButton("🚀 الـ Pull Request", url=pr_url),
                            InlineKeyboardButton("📥 تصفح الملفات على GitHub", url=f"{pr_url}/files")
                        ])

                    sess_url = session_data.get("url") or f"https://jules.google.com/session/{clean_id}"
                    buttons.append([InlineKeyboardButton("🌐 عرض الجلسة في منصة Jules", url=sess_url)])

                    keyboard = InlineKeyboardMarkup(buttons)
                    try:
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=final_text,
                            parse_mode=ParseMode.HTML,
                            reply_markup=keyboard,
                            disable_web_page_preview=False
                        )
                    except Exception:
                        pass

                    # Deliver files and reports directly into Telegram!
                    await cls.deliver_task_artifacts(
                        bot=bot,
                        chat_id=chat_id,
                        user_id=user_id,
                        pr_url=pr_url,
                        activities=activities
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
                    try:
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=fail_text,
                            parse_mode=ParseMode.HTML
                        )
                    except Exception:
                        pass
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
                    try:
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=progress_text,
                            parse_mode=ParseMode.HTML
                        )
                    except Exception:
                        pass

            except TelegramError as tg_err:
                if "Message is not modified" not in str(tg_err):
                    logger.debug("Telegram edit notice: %s", tg_err)
            except Exception as exc:
                logger.warning("Error in task monitor loop: %s", exc)

    @staticmethod
    def parse_patch_files(unidiff_text: str) -> Dict[str, str]:
        """Parses a unified diff patch to extract modified/added file contents."""
        files = {}
        cur_file = None
        cur_lines = []
        for line in unidiff_text.splitlines():
            if line.startswith("+++ b/"):
                if cur_file and cur_lines:
                    files[cur_file] = "\n".join(cur_lines)
                cur_file = line.replace("+++ b/", "").strip()
                cur_lines = []
            elif cur_file:
                if line.startswith("+") and not line.startswith("+++"):
                    cur_lines.append(line[1:])
                elif not line.startswith("-") and not line.startswith("@@") and not line.startswith("diff"):
                    cur_lines.append(line)
        if cur_file and cur_lines:
            files[cur_file] = "\n".join(cur_lines)
        return files

    @classmethod
    async def deliver_task_artifacts(
        cls,
        bot: Bot,
        chat_id: int,
        user_id: int,
        pr_url: Optional[str],
        activities: list
    ) -> None:
        """
        Fetches and delivers files, code, and reports produced by Jules directly into the Telegram chat.
        """
        delivered_count = 0

        # 1. Check activities for agent messages or explanations
        for act in activities:
            if act.get("originator") == "agent":
                if "agentMessaged" in act:
                    msg = act["agentMessaged"].get("agentMessage")
                    if msg:
                        try:
                            await bot.send_message(
                                chat_id=chat_id,
                                text=f"💬 <b>تقرير من وكيل Jules:</b>\n\n{msg}",
                                parse_mode=ParseMode.HTML
                            )
                        except Exception:
                            pass

        # 2. Extract media and code patches from activities
        for act in activities:
            artifacts = act.get("artifacts", [])
            for art in artifacts:
                # Check media (e.g. UI screenshots)
                if "media" in art:
                    import base64
                    m = art["media"]
                    b64_data = m.get("data")
                    if b64_data:
                        try:
                            img_bytes = base64.b64decode(b64_data)
                            bio = io.BytesIO(img_bytes)
                            bio.name = "verification_screenshot.png"
                            await bot.send_photo(
                                chat_id=chat_id,
                                photo=bio,
                                caption="🖼️ <b>معاينة من وكيل Jules</b>",
                                parse_mode=ParseMode.HTML
                            )
                        except Exception as exc:
                            logger.warning("Failed sending Jules media: %s", exc)

                # Check changeSet / gitPatch
                if "changeSet" in art:
                    patch_obj = art["changeSet"].get("gitPatch", {})
                    unidiff = ""
                    if isinstance(patch_obj, dict):
                        unidiff = patch_obj.get("unidiffPatch", "")
                    elif isinstance(patch_obj, str):
                        unidiff = patch_obj

                    if unidiff:
                        parsed_files = cls.parse_patch_files(unidiff)
                        for fname, content in parsed_files.items():
                            try:
                                base_name = os.path.basename(fname)
                                bio = io.BytesIO(content.encode("utf-8"))
                                bio.name = base_name
                                await bot.send_document(
                                    chat_id=chat_id,
                                    document=bio,
                                    caption=f"📄 <b>الملف المُولد من جولز:</b> <code>{base_name}</code>",
                                    parse_mode=ParseMode.HTML
                                )
                                delivered_count += 1
                            except Exception as exc:
                                logger.warning("Failed sending patch file %s: %s", fname, exc)

        # 3. If PR URL exists, fetch and download files directly from GitHub API
        if pr_url and "github.com" in pr_url:
            parts = pr_url.strip("/").split("/")
            if len(parts) >= 4 and "pull" in parts:
                owner = parts[-4]
                repo = parts[-3]
                pr_number = parts[-1]

                github_token = await SettingsRepository.get_setting(f"github_token:{user_id}", "")
                if not github_token:
                    github_token = os.getenv("GITHUB_TOKEN", "")

                api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
                headers = {"User-Agent": "JulesTelegramBot/1.0", "Accept": "application/vnd.github.v3+json"}
                if github_token:
                    headers["Authorization"] = f"Bearer {github_token.strip()}"

                try:
                    def _fetch_pr_files_list():
                        req = urllib.request.Request(api_url, headers=headers)
                        with urllib.request.urlopen(req) as resp:
                            return json.loads(resp.read().decode("utf-8"))
                    files_list = await asyncio.to_thread(_fetch_pr_files_list)

                    for item in files_list:
                        raw_url = item.get("raw_url")
                        fname = item.get("filename", "file")
                        base_fname = os.path.basename(fname)
                        if not raw_url:
                            continue

                        def _download_file(url):
                            req = urllib.request.Request(url, headers=headers)
                            with urllib.request.urlopen(req) as resp:
                                return resp.read()

                        try:
                            file_bytes = await asyncio.to_thread(_download_file, raw_url)
                            bio = io.BytesIO(file_bytes)
                            bio.name = base_fname
                            await bot.send_document(
                                chat_id=chat_id,
                                document=bio,
                                caption=f"📥 <b>تم سحب الملف من المستودع مباشرة:</b> <code>{base_fname}</code>",
                                parse_mode=ParseMode.HTML
                            )
                            delivered_count += 1
                        except Exception as exc:
                            logger.warning("Failed downloading file %s from GitHub: %s", fname, exc)

                except Exception as exc:
                    logger.debug("GitHub API fetch for PR files notice: %s", exc)

        if delivered_count == 0 and pr_url:
            # Send direct download guidance
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    "💡 <b>معاينة وتحميل الملفات:</b>\n"
                    f"• يمكنك تصفح وتحميل الملفات مباشرة من GitHub عبر الرابط:\n"
                    f"🔗 <a href='{pr_url}/files'>معاينة ملفات الـ Pull Request المباشرة</a>\n\n"
                    "• لسحب الملفات الخاصة (كالـ Word و PDF) تلقائياً إلى تيليجرام، يمكنك إدخال التوكن عبر: <code>/github &lt;token&gt;</code>"
                ),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )

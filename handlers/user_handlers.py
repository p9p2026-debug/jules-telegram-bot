"""
User Interaction Handlers Module.
Handles /start, /help, /model, /new, /sessions, /apikey,
incoming text messages, photos, and programming documents (PDF/MD/Code).
"""

import io
import logging
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)
import config
from database.repositories import SessionRepository, SettingsRepository, UserRepository
from services.format_service import FormatService
from services.jules_service import JulesService
from services.jules_api_client import JulesApiClient, JulesApiException
from services.task_monitor_service import TaskMonitorService
from services.permission_service import PermissionService
from services.rich_service import RichService, ComposeStore
from utils.keyboards import (
    get_main_keyboard,
    get_model_switch_keyboard,
    get_sessions_keyboard,
    get_sources_keyboard
)

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /start command: registers user and introduces Jules AI."""
    user = update.effective_user
    user_db = await UserRepository.get_or_create(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )

    allowed, reason = await PermissionService.check_access(user.id)
    if not allowed:
        await update.message.reply_text(reason)
        return

    active_session = await SessionRepository.get_active_session(user.id)
    model_choice = user_db.get("selected_model", config.MODEL_CHOICE_FLASH)
    if model_choice == config.MODEL_CHOICE_PRO:
        model_display = config.MODEL_PRO_NAME
    elif model_choice == config.MODEL_CHOICE_AGENT:
        model_display = config.MODEL_AGENT_NAME
    else:
        model_display = config.MODEL_FLASH_NAME

    is_admin = PermissionService.is_admin(user.id)

    welcome_text = (
        f"🤖 <b>أهلاً بك يا {user.first_name} في المساعد البرمجي والهندسي المتقدم!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "أنا مساعدك التقني المتكامل لحل المشكلات البرمجية، وتصميم المعماريات السحابية، وتنفيذ المهام التلقائية.\n\n"
        "✨ <b>قدراتي وخدماتي البرمجية:</b>\n"
        "• كتابة وتدقيق الأكواد بمختلف لغات البرمجة وحل المشكلات المعقدة.\n"
        "• تنفيذ مهام برمجية متكاملة على مستودعات GitHub وفتح Pull Requests آلياً.\n"
        "• مراجعة وتصميم المعماريات البرمجية السحابية (Cloud Architectures).\n"
        "• تحليل مستندات الأكواد والملفات البرمجية (PDF, Markdown, Python, إلخ).\n"
        "• فحص وتفسير المخططات والتصاميم من الصور والمخططات التوضيحية.\n\n"
        f"⚡ <b>الوضع والنموذج النشط:</b> <code>{model_display}</code>\n"
        f"💬 <b>الجلسة النشطة:</b> <code>{active_session['title']}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>أرسل استفسارك البرمجي، ملفك، أو صورتك مباشرة وسأقوم بتحليلها فوراً!</i>"
    )

    await update.message.reply_text(
        text=welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard(is_admin)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /help command: displays detailed guide of features and commands."""
    user_id = update.effective_user.id
    allowed, reason = await PermissionService.check_access(user_id)
    if not allowed:
        await update.message.reply_text(reason)
        return

    is_admin = PermissionService.is_admin(user_id)

    help_text = (
        "📖 <b>دليل استخدام وأوامر المساعد الذكي:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <b>النماذج والذكاء الاصطناعي:</b>\n"
        "• <code>/model</code> - التبديل التفاعلي بين النماذج (السريع، المتعمق، ووكيل المستودعات التلقائي).\n"
        "• <code>/repos</code> - استعراض مستودعات GitHub المتصلة بحسابك واختيار المشروع.\n"
        "• <code>/tasks</code> - متابعة المهام البرمجية الجارية والسابقة وروابط الـ Pull Requests.\n\n"
        "💬 <b>إدارة الجلسات والسياق:</b>\n"
        "• <code>/new</code> - بدء جلسة جديدة كلياً وتصفير سياق المحادثة.\n"
        "• <code>/sessions</code> - استعراض الجلسات السابقة والتبديل بينها أو حذفها.\n\n"
        "🔑 <b>مفاتيح API:</b>\n"
        "• <code>/apikey &lt;key&gt;</code> - تعيين مفتاح API خاص بك لتجنب نفاد الحصة.\n"
        "• <code>/apikey clear</code> - إزالة مفتاحك الخاص والعودة للمفتاح الافتراضي للبوت.\n\n"
        "📝 <b>المنشورات الغنية (Rich Messages):</b>\n"
        "• <code>/compose</code> - بدء محرر المنشور المركب لتجميع نصوص وجداول وصور ونشرها كرسالة غنية واحدة.\n\n"
        "📁 <b>المستندات والوسائط:</b>\n"
        "• أرسل أي ملف (<code>.pdf</code>, <code>.md</code>, <code>.py</code>, <code>.json</code>) مع تعليق تريده وسيقوم المساعد بفحصه وتقديم الشرح والحلول داخل المحادثة.\n"
        "• أرسل صورة أو مخطط هيكلي وسأقوم بتحليله وتفسير محتواه برمجياً.\n"
    )

    if is_admin:
        help_text += (
            "\n👑 <b>أوامر الإدارة (Admins Only):</b>\n"
            "• <code>/admin</code> - فتح لوحة التحكم الرئيسية والصلاحيات.\n"
            "• <code>/search &lt;id/username&gt;</code> - البحث عن مستخدم وإدارة صلاحياته وحظره.\n"
        )

    help_text += "━━━━━━━━━━━━━━━━━━━━━"

    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)


async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /model command: presents model selection inline keyboard."""
    user_id = update.effective_user.id
    allowed, reason = await PermissionService.check_access(user_id, config.FEATURE_SWITCH_MODEL)
    if not allowed:
        await update.message.reply_text(reason)
        return

    user = await UserRepository.get_by_id(user_id)
    current_model = user.get("selected_model", config.MODEL_CHOICE_FLASH) if user else config.MODEL_CHOICE_FLASH

    text = (
        "⚡ <b>اختر وضع ونموذج الذكاء الاصطناعي المطلوب:</b>\n\n"
        f"1. ⚡ <b>{config.MODEL_FLASH_NAME}:</b>\n"
        "• استجابة فورية فائقة السرعة، ممتاز للمهام اليومية والأسئلة السريعة والتحليلات الخفيفة.\n\n"
        f"2. 🧠 <b>{config.MODEL_PRO_NAME}:</b>\n"
        "• عمق تحليلي استثنائي، تفكير منطقي متقدم لحل أعقد المعضلات المعمارية والبرمجية.\n\n"
        f"3. 🛠️ <b>{config.MODEL_AGENT_NAME}:</b>\n"
        "• وكيل مستقل يتصل بمستودعات GitHub، يستنسخ المشروع، ينفذ الأكواد، ويفتح Pull Request تلقائياً!"
    )

    await update.message.reply_text(
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_model_switch_keyboard(current_model)
    )


async def new_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /new command: creates a new session."""
    user_id = update.effective_user.id
    allowed, reason = await PermissionService.check_access(user_id, config.FEATURE_CREATE_SESSIONS)
    if not allowed:
        await update.message.reply_text(reason)
        return

    session_id = await SessionRepository.create_session(user_id)
    await update.message.reply_text(
        f"✨ <b>تم بدء جلسة محادثة جديدة بنجاح!</b>\n"
        f"🆔 معرف الجلسة: <code>{session_id}</code>\n"
        "تم مسح السياق المؤقت للبدء في نقاش برمجي جديد ونظيف.",
        parse_mode=ParseMode.HTML
    )


async def sessions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /sessions command: lists recent sessions."""
    user_id = update.effective_user.id
    allowed, reason = await PermissionService.check_access(user_id)
    if not allowed:
        await update.message.reply_text(reason)
        return

    sessions = await SessionRepository.list_user_sessions(user_id, limit=8)
    active = await SessionRepository.get_active_session(user_id)
    active_id = active["session_id"] if active else ""

    if not sessions:
        await update.message.reply_text("📂 ليس لديك جلسات سابقة بعد. أرسل أي رسالة لبدء أول جلسة!")
        return

    text = (
        "📂 <b>جلسات المحادثة الخاصة بك:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "• اضغط على عنوان الجلسة للتبديل إليها واستئناف سياقها.\n"
        "• اضغط على 🗑️ لحذف الجلسة وسجلها نهائياً."
    )

    await update.message.reply_text(
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_sessions_keyboard(sessions, active_id)
    )


async def apikey_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /apikey command: manages personal Google API keys."""
    user_id = update.effective_user.id
    allowed, reason = await PermissionService.check_access(user_id, config.FEATURE_CUSTOM_KEYS)
    if not allowed:
        await update.message.reply_text(reason)
        return

    if not context.args:
        user = await UserRepository.get_by_id(user_id)
        has_key = bool(user and user.get("custom_api_key"))
        status = "🟢 لديك مفتاح خاص محفوظ" if has_key else "⚪ أنت تستخدم مفتاح البوت الافتراضي"

        await update.message.reply_text(
            f"🔑 <b>إدارة مفتاح API الخاص بك:</b>\n"
            f"الحالة الحالية: {status}\n\n"
            "• لتعيين مفتاحك الخاص:\n"
            "<code>/apikey YOUR_API_KEY_HERE</code>\n\n"
            "• لمسح مفتاحك الخاص والعودة للافتراضي:\n"
            "<code>/apikey clear</code>",
            parse_mode=ParseMode.HTML
        )
        return

    arg = context.args[0].strip()
    if arg.lower() == "clear":
        await UserRepository.update_custom_api_key(user_id, None)
        await update.message.reply_text("✅ تم مسح مفتاحك الخاص بنجاح. يتم الآن استخدام المفتاح الافتراضي للبوت.")
    else:
        # Validate key roughly
        if len(arg) < 15:
            await update.message.reply_text("❌ يبدو أن المفتاح المدخل غير صالح (قصير جداً).")
            return
        await UserRepository.update_custom_api_key(user_id, arg)
        await update.message.reply_text("✅ تم حفظ مفتاح API الخاص بك بنجاح! سيتم توجيه جميع طلباتك باستخدامه.")


async def repos_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /repos: lists connected GitHub repositories from Jules API."""
    user_id = update.effective_user.id
    allowed, reason = await PermissionService.check_access(user_id, config.FEATURE_AUTONOMOUS_AGENT)
    if not allowed:
        await update.message.reply_text(reason)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    try:
        sources = await JulesApiClient.list_sources()
        if not sources:
            await update.message.reply_text(
                "ℹ️ <b>لم يتم العثور على مستودعات متصلة في Jules</b>\n\n"
                "• تأكد من ربط حساب GitHub بمستودعاتك عبر موقع Jules:\n"
                "https://jules.google.com\n"
                "• وتأكد من ضبط المتغير البيئي <code>JULES_API_KEY</code> في الخادم.",
                parse_mode=ParseMode.HTML
            )
            return

        active_source = await SettingsRepository.get_setting(f"user_source:{user_id}", "")
        keyboard = get_sources_keyboard(sources, active_source)
        await update.message.reply_text(
            "📁 <b>مستودعات GitHub المتصلة بالوكيل المستقل:</b>\n"
            "اضغط على المستودع المطلوب لتحديده كوجهة للمهام البرمجية القادمة:",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
    except JulesApiException as j_err:
        await update.message.reply_text(f"⚠️ <b>خطأ في واجهة Jules API:</b>\n{j_err}", parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.exception("Error in /repos: %s", exc)
        await update.message.reply_text(f"⚠️ تعذر جلب قائمة المستودعات: {exc}")


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /tasks: lists recent coding sessions on Jules API."""
    user_id = update.effective_user.id
    allowed, reason = await PermissionService.check_access(user_id, config.FEATURE_AUTONOMOUS_AGENT)
    if not allowed:
        await update.message.reply_text(reason)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    try:
        sessions = await JulesApiClient.list_sessions()
        if not sessions:
            await update.message.reply_text("ℹ️ لا توجد مهام برمجية سابقة مسجلة على الوكيل.")
            return

        lines = ["📋 <b>آخر المهام البرمجية لوكيل المستودعات:</b>\n━━━━━━━━━━━━━━━━━━━━━"]
        for s in sessions[:6]:
            name = s.get("name", "").replace("sessions/", "")
            state = s.get("state", "UNKNOWN")
            prompt = (s.get("prompt") or "بدون عنوان")[:45]
            outputs = s.get("outputs", {})
            pr = outputs.get("pullRequest", {}).get("url", "")
            state_emoji = "✅" if state in ["COMPLETED", "SUCCEEDED"] or pr else ("⏳" if state == "RUNNING" else "❌")
            pr_text = f"\n  🔗 <a href='{pr}'>Pull Request على GitHub</a>" if pr else ""
            lines.append(f"{state_emoji} <b>#{name}</b>: {prompt} [{state}]{pr_text}")

        lines.append("━━━━━━━━━━━━━━━━━━━━━\n• لتشغيل مهمة جديدة، حدد المستودع عبر <code>/repos</code> ثم أرسل طلبك في الشات مباشرة.")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except JulesApiException as j_err:
        await update.message.reply_text(f"⚠️ <b>خطأ في واجهة Jules API:</b>\n{j_err}", parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.exception("Error in /tasks: %s", exc)
        await update.message.reply_text(f"⚠️ تعذر استرجاع قائمة المهام: {exc}")


async def compose_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /compose: starts interactive multi-part rich message builder."""
    user_id = update.effective_user.id
    allowed, reason = await PermissionService.check_access(user_id)
    if not allowed:
        await update.message.reply_text(reason)
        return

    session = ComposeStore.get_or_create(user_id)
    session.clear()

    compose_text = (
        "📝 <b>محرر المنشور المركب (Rich Message Composer)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "أنت الآن في وضع تجميع المنشور الغني! يمكنك إرسال عدة قطع بالترتيب:\n"
        "• ✍️ أرسل نصوصاً أو شروحات.\n"
        "• 📊 أرسل جداول ماركداون (أعمدة وصفوف).\n"
        "• 🖼️ أرسل صوراً أو مخططات (مع كابشن أو بدونه).\n\n"
        "سيقوم البوت بحقن الصور والجداول ودمجها في <b>رسالة واحدة متصلة (Single Rich Message)</b>!\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ <b>أوامر التحكم أثناء التحرير:</b>\n"
        "• <code>/preview</code> - معاينة القطع المجمعة حتى الآن.\n"
        "• <code>/undo</code> - التراجع عن وحذف آخر قطعة.\n"
        "• <code>/done</code> - تجميع وبناء ونشر الرسالة الغنية الواحدة.\n"
        "• <code>/cancel</code> - إلغاء وضع التحرير ومسح المسودة."
    )
    await update.message.reply_text(compose_text, parse_mode=ParseMode.HTML)


async def preview_compose_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /preview: shows current draft summary."""
    user_id = update.effective_user.id
    session = ComposeStore.get(user_id)
    if not session or session.size == 0:
        await update.message.reply_text("ℹ️ مسودة المنشور المركب فارغة حالياً. أرسل نصاً أو صورة أولاً.")
        return

    desc = "\n".join(session.describe())
    await update.message.reply_text(
        f"👁️ <b>معاينة قطع المنشور ({session.size} قطع):</b>\n\n{desc}\n\n"
        "• أرسل المزيد من القطع لإضافتها.\n"
        "• اكتب <code>/done</code> للنشر كرسالة واحدة.\n"
        "• اكتب <code>/undo</code> لحذف آخر قطعة.",
        parse_mode=ParseMode.HTML
    )


async def undo_compose_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /undo: removes the last piece added."""
    user_id = update.effective_user.id
    session = ComposeStore.get(user_id)
    if not session or session.size == 0:
        await update.message.reply_text("ℹ️ لا توجد قطع للتراجع عنها في المسودة.")
        return

    session.undo()
    await update.message.reply_text(
        f"↩️ تم التراجع عن آخر قطعة بنجاح. المتبقي في المسودة: {session.size} قطعة.\n"
        "اكتب <code>/preview</code> للمعاينة أو <code>/done</code> للنشر.",
        parse_mode=ParseMode.HTML
    )


async def done_compose_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /done: compiles and publishes the single rich message."""
    user_id = update.effective_user.id
    session = ComposeStore.get(user_id)
    if not session or session.size == 0:
        await update.message.reply_text("ℹ️ مسودة المنشور فارغة. أرسل محتوى أولاً ثم اكتب /done.")
        return

    md, media, _ = session.build()
    ComposeStore.remove(user_id)

    await update.message.reply_text("🚀 <b>جاري دمج ونشر الرسالة الغنية المركبة...</b>", parse_mode=ParseMode.HTML)

    await RichService.deliver_rich(
        bot=context.bot,
        chat_id=update.effective_chat.id,
        raw_markdown=md,
        media=media
    )


async def cancel_compose_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /cancel: cancels active compose mode."""
    user_id = update.effective_user.id
    if ComposeStore.is_composing(user_id):
        ComposeStore.remove(user_id)
        await update.message.reply_text("❌ تم إلغاء وضع التحرير ومسح المسودة بنجاح.")
    else:
        await update.message.reply_text("ℹ️ لست في وضع تحرير المنشور حالياً.")


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles general incoming text messages from users."""
    user = update.effective_user
    text = update.message.text.strip()

    # Reply Keyboard button shortcuts
    if text == "⚡ تبديل النموذج":
        await model_command(update, context)
        return
    elif text == "💬 جلسة جديدة":
        await new_session_command(update, context)
        return
    elif text == "📂 جلساتي":
        await sessions_command(update, context)
        return
    elif text == "🔑 مفتاح API":
        await apikey_command(update, context)
        return
    elif text == "ℹ️ المساعدة والمعلومات":
        await help_command(update, context)
        return
    elif text == "🛠️ لوحة تحكم الأدمن (/admin)":
        from handlers.admin_handlers import admin_command
        await admin_command(update, context)
        return

    # Check if user is actively in /compose mode
    if ComposeStore.is_composing(user.id):
        if text.startswith("/"):
            return
        session = ComposeStore.get(user.id)
        session.add_text(text)
        await update.message.reply_text(
            f"✅ تمت إضافة النص إلى المنشور المركب (إجمالي القطع: <b>{session.size}</b>).\n"
            "• أرسل صورة أو نصاً آخر، أو اكتب <code>/preview</code> للمعاينة أو <code>/done</code> للنشر.",
            parse_mode=ParseMode.HTML
        )
        return

    # Permission check for chat
    allowed, reason = await PermissionService.check_access(user.id)
    if not allowed:
        await update.message.reply_text(reason)
        return

    # Update user record
    user_db = await UserRepository.get_or_create(user.id, user.username, user.first_name)
    selected_model = user_db.get("selected_model", config.MODEL_CHOICE_FLASH)

    # If the user selected the Autonomous Agent mode:
    if selected_model == config.MODEL_CHOICE_AGENT:
        allowed_agent, reason_agent = await PermissionService.check_access(user.id, config.FEATURE_AUTONOMOUS_AGENT)
        if not allowed_agent:
            await update.message.reply_text(reason_agent)
            return

        active_source = await SettingsRepository.get_setting(f"user_source:{user.id}", "")
        if not active_source:
            try:
                sources = await JulesApiClient.list_sources()
                if sources:
                    keyboard = get_sources_keyboard(sources, "")
                    await update.message.reply_text(
                        "⚠️ <b>يرجى تحديد المستودع المستهدف أولاً!</b>\n"
                        "اختر المستودع الذي ترغب في أن ينفذ الوكيل المهمة عليه ويفتح Pull Request:",
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard
                    )
                else:
                    await update.message.reply_text(
                        "⚠️ <b>لم يتم العثور على مستودعات مرتبطة بحسابك في Jules</b>\n"
                        "يرجى ربط مستودعك عبر https://jules.google.com ثم تشغيل الأمر <code>/repos</code>.",
                        parse_mode=ParseMode.HTML
                    )
            except Exception as exc:
                await update.message.reply_text(f"⚠️ يرجى اختيار المستودع أولاً عبر <code>/repos</code> ({exc})")
            return

        repo_display = active_source.replace("sources/github-", "").replace("sources/", "")
        status_msg = await update.message.reply_text(
            f"🚀 <b>جاري إرسال المهمة البرمجية لوكيل المستودعات...</b>\n"
            f"📁 <b>المستودع:</b> <code>{repo_display}</code>\n"
            f"📝 <b>الطلب:</b> <i>{text[:100]}</i>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⏳ جاري تشغيل بيئة سحابية واستنساخ المشروع...",
            parse_mode=ParseMode.HTML
        )

        try:
            session_obj = await JulesApiClient.create_session(
                source=active_source,
                prompt=text
            )
            session_name = session_obj.get("name")
            await TaskMonitorService.start_monitoring(
                bot=context.bot,
                chat_id=update.effective_chat.id,
                status_message_id=status_msg.message_id,
                session_name=session_name,
                repo_name=repo_display,
                prompt=text
            )
        except Exception as exc:
            logger.exception("Error launching Jules API session: %s", exc)
            await status_msg.edit_text(
                f"❌ <b>فشل إطلاق مهمة الوكيل:</b>\n<code>{exc}</code>\n\n"
                "يمكنك العودة لنموذج الدردشة السريع عبر <code>/model</code>.",
                parse_mode=ParseMode.HTML
            )
        return

    # Conversational chat with Flash or Pro
    session = await SessionRepository.get_active_session(user.id)

    # Send live typing action indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # Generate answer with Jules
    response_text = await JulesService.generate_response(
        user_id=user.id,
        session_id=session["session_id"],
        user_prompt=text
    )

    # Deliver using Rich Message Service (supporting tables, RTL, and intelligent fallback)
    await RichService.deliver_rich(
        bot=context.bot,
        chat_id=update.effective_chat.id,
        raw_markdown=response_text,
        reply_to_message_id=update.message.message_id
    )


async def photo_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming photos for visual and architectural analysis or compose mode."""
    user = update.effective_user

    # If in compose mode, store photo as piece
    if ComposeStore.is_composing(user.id):
        photo_obj = update.message.photo[-1]
        session = ComposeStore.get(user.id)
        session.add_photo(file_id=photo_obj.file_id, caption=update.message.caption)
        await update.message.reply_text(
            f"✅ تمت إضافة الصورة إلى المنشور المركب (إجمالي القطع: <b>{session.size}</b>).\n"
            "• أرسل نصوصاً أو صوراً أخرى، أو اكتب <code>/preview</code> للمعاينة أو <code>/done</code> للنشر.",
            parse_mode=ParseMode.HTML
        )
        return

    allowed, reason = await PermissionService.check_access(user.id, config.FEATURE_SEND_IMAGES)
    if not allowed:
        await update.message.reply_text(reason)
        return

    await UserRepository.get_or_create(user.id, user.username, user.first_name)
    session = await SessionRepository.get_active_session(user.id)

    # Send visual processing action
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)

    # Download highest resolution photo
    photo_obj = update.message.photo[-1]
    file = await context.bot.get_file(photo_obj.file_id)
    bio = io.BytesIO()
    await file.download_to_memory(out=bio)
    image_bytes = bio.getvalue()

    caption = update.message.caption or "يرجى فحص وتحليل هذه الصورة/المخطط المعماري برمجياً بالتفصيل."

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    response_text = await JulesService.generate_response(
        user_id=user.id,
        session_id=session["session_id"],
        user_prompt=caption,
        media_bytes=image_bytes,
        mime_type="image/jpeg",
        file_name="image.jpg"
    )

    # Build integrated rich response: embed photo + tables + code in ONE message
    media_list = [{
        "id": "m0",
        "media": {
            "type": "photo",
            "media": photo_obj.file_id
        }
    }]
    clean_cap = (update.message.caption or "مخطط التحليل البرمجي").replace('"', '')[:60]
    integrated_markdown = f"![](tg://photo?id=m0 \"{clean_cap}\")\n\n{response_text}"

    await RichService.deliver_rich(
        bot=context.bot,
        chat_id=update.effective_chat.id,
        raw_markdown=integrated_markdown,
        media=media_list,
        reply_to_message_id=update.message.message_id
    )


async def document_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming code documents, markdown, and PDF files."""
    user = update.effective_user

    doc = update.message.document
    file_name = doc.file_name or "document"

    # If in compose mode, store document as piece
    if ComposeStore.is_composing(user.id):
        session = ComposeStore.get(user.id)
        session.add_document(file_id=doc.file_id, caption=update.message.caption or file_name)
        await update.message.reply_text(
            f"✅ تمت إضافة الملف إلى المنشور المركب (إجمالي القطع: <b>{session.size}</b>).\n"
            "• اكتب <code>/preview</code> للمعاينة أو <code>/done</code> للنشر.",
            parse_mode=ParseMode.HTML
        )
        return

    allowed, reason = await PermissionService.check_access(user.id, config.FEATURE_UPLOAD_FILES)
    if not allowed:
        await update.message.reply_text(reason)
        return

    mime_type = doc.mime_type or "text/plain"

    # Identify file extension
    ext = file_name.lower().split(".")[-1] if "." in file_name else ""
    if ext in ["py", "js", "ts", "json", "html", "css", "md", "txt", "yaml", "yml", "sql", "sh"]:
        mime_type = "text/plain"
    elif ext == "pdf":
        mime_type = "application/pdf"

    await UserRepository.get_or_create(user.id, user.username, user.first_name)
    session = await SessionRepository.get_active_session(user.id)

    # Indicate upload/processing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_DOCUMENT)

    file = await context.bot.get_file(doc.file_id)
    bio = io.BytesIO()
    await file.download_to_memory(out=bio)
    doc_bytes = bio.getvalue()

    caption = update.message.caption or f"يرجى فحص وتحليل الملف ({file_name}) وتقديم مراجعة برمجية شاملة له مع جداول مقارنة إن لزم."

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    response_text = await JulesService.generate_response(
        user_id=user.id,
        session_id=session["session_id"],
        user_prompt=caption,
        media_bytes=doc_bytes,
        mime_type=mime_type,
        file_name=file_name
    )

    await RichService.deliver_rich(
        bot=context.bot,
        chat_id=update.effective_chat.id,
        raw_markdown=response_text,
        reply_to_message_id=update.message.message_id
    )


async def user_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles user callback queries (model switching, sessions)."""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    if data == "user:close":
        await query.delete_message()

    elif data.startswith("user:set_model:"):
        model_target = data.split(":")[2]

        # Permission check: switch_model
        allowed, reason = await PermissionService.check_access(user_id, config.FEATURE_SWITCH_MODEL)
        if not allowed:
            await query.answer(reason, show_alert=True)
            return

        # If selecting pro, check use_pro permission
        if model_target == config.MODEL_CHOICE_PRO:
            allowed_pro, reason_pro = await PermissionService.check_access(user_id, config.FEATURE_USE_PRO)
            if not allowed_pro:
                await query.answer(reason_pro, show_alert=True)
                return
        elif model_target == config.MODEL_CHOICE_AGENT:
            allowed_agent, reason_agent = await PermissionService.check_access(user_id, config.FEATURE_AUTONOMOUS_AGENT)
            if not allowed_agent:
                await query.answer(reason_agent, show_alert=True)
                return

        await UserRepository.update_model(user_id, model_target)

        if model_target == config.MODEL_CHOICE_PRO:
            display_name = config.MODEL_PRO_NAME
        elif model_target == config.MODEL_CHOICE_AGENT:
            display_name = config.MODEL_AGENT_NAME
        else:
            display_name = config.MODEL_FLASH_NAME

        try:
            await query.edit_message_reply_markup(reply_markup=get_model_switch_keyboard(model_target))
        except Exception:
            pass

        extra_tip = ""
        if model_target == config.MODEL_CHOICE_AGENT:
            active_src = await SettingsRepository.get_setting(f"user_source:{user_id}", "")
            if active_src:
                clean_src = active_src.replace("sources/github-", "").replace("sources/", "")
                extra_tip = f"\n📁 <b>المستودع المستهدف:</b> <code>{clean_src}</code>\nأرسل طلبك في الشات لتنفيذ المهمة!"
            else:
                extra_tip = "\n⚠️ لم تحدد مستودعاً بعد! استخدم الأمر <code>/repos</code> لاختيار المستودع."

        await query.message.reply_text(f"✅ تم تغيير الوضع بنجاح إلى:\n<b>{display_name}</b>{extra_tip}", parse_mode=ParseMode.HTML)

    elif data.startswith("user:sel_src:"):
        source_name = data.replace("user:sel_src:", "")
        await SettingsRepository.set_setting(f"user_source:{user_id}", source_name)
        await UserRepository.update_model(user_id, config.MODEL_CHOICE_AGENT)

        display_name = source_name.replace("sources/github-", "").replace("sources/", "")
        await query.answer("تم تفعيل المستودع بنجاح!")
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await query.message.reply_text(
            f"⭐ <b>تم اختيار المستودع بنجاح:</b>\n<code>{display_name}</code>\n\n"
            f"• تم تحويل النموذج تلقائياً إلى: <b>{config.MODEL_AGENT_NAME}</b>\n"
            "💬 أرسل الآن أي مهمة برمجية في الشات مباشرة (مثل: 'أصلح الأخطاء واكتب اختبارات الوحدة') وسيقوم الوكيل بتنفيذها وفتح Pull Request!",
            parse_mode=ParseMode.HTML
        )

    elif data == "user:refresh_sources":
        try:
            sources = await JulesApiClient.list_sources()
            active_src = await SettingsRepository.get_setting(f"user_source:{user_id}", "")
            await query.edit_message_reply_markup(reply_markup=get_sources_keyboard(sources, active_src))
            await query.answer("تم تحديث قائمة المستودعات!")
        except Exception as exc:
            if "not modified" in str(exc).lower():
                await query.answer("القائمة محدثة بالفعل.")
            else:
                await query.answer(f"فشل التحديث: {exc}", show_alert=True)

    elif data.startswith("user:select_session:"):
        session_id = data.split(":")[2]
        success = await SessionRepository.set_active_session(user_id, session_id)
        if success:
            sessions = await SessionRepository.list_user_sessions(user_id, limit=8)
            try:
                await query.edit_message_reply_markup(reply_markup=get_sessions_keyboard(sessions, session_id))
            except Exception:
                pass
            await query.message.reply_text(f"🔄 تم التبديل إلى الجلسة <code>#{session_id}</code> واستئناف سياقها.", parse_mode=ParseMode.HTML)

    elif data.startswith("user:delete_session:"):
        session_id = data.split(":")[2]
        await SessionRepository.delete_session(session_id, user_id)
        sessions = await SessionRepository.list_user_sessions(user_id, limit=8)
        active = await SessionRepository.get_active_session(user_id)
        active_id = active["session_id"] if active else ""

        try:
            if sessions:
                await query.edit_message_reply_markup(reply_markup=get_sessions_keyboard(sessions, active_id))
            else:
                await query.edit_message_text("📂 تم حذف جميع جلساتك السابقة.")
        except Exception:
            pass

    elif data == "user:new_session":
        allowed, reason = await PermissionService.check_access(user_id, config.FEATURE_CREATE_SESSIONS)
        if not allowed:
            await query.answer(reason, show_alert=True)
            return

        session_id = await SessionRepository.create_session(user_id)
        await query.edit_message_text(
            f"✨ <b>تم بدء جلسة جديدة كلياً!</b>\n🆔 المعرف: <code>{session_id}</code>\nيمكنك البدء في إرسال استفساراتك الآن.",
            parse_mode=ParseMode.HTML
        )


def register_user_handlers(app: Application) -> None:
    """Registers user command and message handlers."""
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CommandHandler("new", new_session_command))
    app.add_handler(CommandHandler("sessions", sessions_command))
    app.add_handler(CommandHandler("apikey", apikey_command))

    # Autonomous repo agent commands
    app.add_handler(CommandHandler("repos", repos_command))
    app.add_handler(CommandHandler("sources", repos_command))
    app.add_handler(CommandHandler("tasks", tasks_command))

    # Compose mode commands
    app.add_handler(CommandHandler("compose", compose_command))
    app.add_handler(CommandHandler("preview", preview_compose_command))
    app.add_handler(CommandHandler("undo", undo_compose_command))
    app.add_handler(CommandHandler("done", done_compose_command))
    app.add_handler(CommandHandler("cancel", cancel_compose_command))

    app.add_handler(CallbackQueryHandler(user_callback_handler, pattern=r"^user:"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_message_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, document_message_handler))


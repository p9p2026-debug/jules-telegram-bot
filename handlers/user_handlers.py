"""
User Interaction Handlers Module.
Handles /start, /help, /model, /new, /sessions, /apikey,
incoming text messages, photos, and programming documents (PDF/MD/Code).
"""

import io
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
from database.repositories import SessionRepository, SettingsRepository, TaskRepository, UserRepository
from services.format_service import FormatService
from services.incoming_service import extract_incoming_message
from services.jules_service import JulesService
from services.jules_api_client import JulesApiClient, JulesApiException
from services.task_monitor_service import TaskMonitorService
from services.permission_service import PermissionService
from services.rich_service import RichService, ComposeStore
from utils.keyboards import (
    get_main_keyboard,
    get_model_switch_keyboard,
    get_sessions_keyboard,
    get_sources_keyboard,
    get_apikey_dashboard_keyboard
)

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /start command: registers user with a minimal, clean, professional greeting."""
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

    is_admin = PermissionService.is_admin(user.id)
    has_custom_key = bool(user_db.get("custom_api_key"))

    welcome_text = "أهلاً بك 👋"

    await update.message.reply_text(
        text=welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard(is_admin, has_custom_key)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /help command: displays detailed guide of features and commands."""
    user_id = update.effective_user.id
    allowed, reason = await PermissionService.check_access(user_id)
    if not allowed:
        await update.message.reply_text(reason)
        return

    is_admin = PermissionService.is_admin(user_id)
    if not is_admin:
        return

    admin_help_text = (
        "👑 <b>لوحة مساعدة إدارة النظام (Admins Only):</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "• <code>/admin</code> - فتح لوحة التحكم الرئيسية والصلاحيات.\n"
        "• <code>/search &lt;id/username&gt;</code> - البحث عن مستخدم وإدارة صلاحياته.\n"
        "• <code>/adminguide</code> - فتح دليل الأدمن الشامل.\n"
        "• <code>/repos</code> - استعراض مستودعات GitHub المتصلة.\n"
        "• <code>/apikey</code> - إدارة مفاتيح النظام الخاصة والعامة.\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(admin_help_text, parse_mode=ParseMode.HTML)


async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /model command: presents model selection inline keyboard or sets model directly."""
    user_id = update.effective_user.id
    if not PermissionService.is_admin(user_id):
        await update.message.reply_text("⛔ اختيار وتعيين النماذج يدار مركزياً من قِبل إدارة النظام.")
        return

    allowed, reason = await PermissionService.check_access(user_id, config.FEATURE_SWITCH_MODEL)
    if not allowed:
        await update.message.reply_text(reason)
        return

    # Direct model setting via command argument: e.g. /model gemini-3.6-flash, /model gemini-3.1-pro
    if context.args:
        raw_arg = context.args[0].strip().lower()
        if raw_arg in ["agent", "jules"]:
            canonical = "agent"
            display = "🛠️ وكيل هندسة البرمجيات المستقل"
            extra_note = "\n🛠️ تم تفعيل وضع وكيل البرمجة المستقل."
        else:
            canonical = JulesService.resolve_model_id(raw_arg)
            display = canonical
            extra_note = ""

        await UserRepository.update_model(user_id, canonical)
        await update.message.reply_text(
            f"✅ <b>تم تفعيل النموذج المعتمد بنجاح:</b>\n"
            f"🎯 <code>{display}</code>{extra_note}\n\n"
            "سيتم توجيه جميع طلباتك القادمة بهذا الاسم الرسمي الدقيق.",
            parse_mode=ParseMode.HTML
        )
        return

    user = await UserRepository.get_by_id(user_id)
    current_model = user.get("selected_model", "gemini-3.6-flash") if user else "gemini-3.6-flash"
    resolved_current = "🛠️ وكيل هندسة البرمجيات المستقل" if current_model == "agent" else JulesService.resolve_model_id(current_model)

    text = (
        "🎯 <b>قائمة النماذج والقدرات المعتمدة:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>النموذج النشط حالياً:</b> <code>{resolved_current}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🛠️ <b>نماذج محرك الوكيل المتقدم:</b>\n"
        "• <code>gemini-3.6-flash</code>\n"
        "• <code>gemini-3.1-pro</code>\n\n"
        "⚡ <b>نماذج المعالجة المباشرة:</b>\n"
        "• <code>gemini-3.1-pro</code> (النموذج الوحيد Pro)\n"
        "• <code>gemini-3.1-flash</code>\n"
        "• <code>gemini-3.5-flash</code>\n"
        "• <code>gemini-3.6-flash</code>\n"
        "• <code>gemini-3.7-flash</code>\n"
        "• <code>gemini-3.8-flash</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>اختر النموذج من الأزرار بالأسفل، أو اكتب اسمه بالكامل:</i>\n"
        "<code>/model gemini-3.6-flash</code>"
    )

    await update.message.reply_text(
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_model_switch_keyboard(current_model)
    )


async def new_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /new command: creates a new session and clears active task."""
    user = update.effective_user
    user_id = user.id
    await UserRepository.get_or_create(user_id, user.username, user.first_name)
    allowed, reason = await PermissionService.check_access(user_id, config.FEATURE_CREATE_SESSIONS)
    if not allowed:
        await update.message.reply_text(reason)
        return

    await SettingsRepository.set_setting(f"active_jules_sess:{user_id}", "")
    session_id = await SessionRepository.create_session(user_id)
    await update.message.reply_text(
        f"✨ <b>تم بدء جلسة محادثة ومهمة جديدة بنجاح!</b>\n"
        f"🆔 معرف الجلسة: <code>{session_id}</code>\n\n"
        "• تم تصفير سياق المحادثة وفك الارتباط التام بأي مهمة سابقة.\n"
        "• أي رسالة أو مهمة ترسلها الآن ستبدأ كجلسة عمل جديدة ونظيفة من الصفر.",
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
    """Handles /apikey command: manages personal Google Studio & Jules API keys with full interactive UI."""
    user_id = update.effective_user.id
    if not PermissionService.is_admin(user_id):
        await update.message.reply_text("⛔ إدارة المفاتيح تدار مركزياً من قِبل إدارة النظام.")
        return

    allowed, reason = await PermissionService.check_access(user_id, config.FEATURE_CUSTOM_KEYS)
    if not allowed:
        await update.message.reply_text(reason)
        return

    # If no arguments provided, show interactive dashboard with inline buttons
    if not context.args:
        user = await UserRepository.get_by_id(user_id)
        custom_key = user.get("custom_api_key", "") if user else ""
        gemini_key = await SettingsRepository.get_setting(f"user_gemini_key:{user_id}", "")
        jules_key = await SettingsRepository.get_setting(f"user_jules_key:{user_id}", "")

        # Auto-detect general custom key if specific keys aren't set
        if custom_key:
            if custom_key.startswith("AQ.") and not jules_key:
                jules_key = custom_key
            elif custom_key.startswith("AIza") and not gemini_key:
                gemini_key = custom_key

        has_gemini = bool(gemini_key)
        has_jules = bool(jules_key)

        gemini_txt = f"🟢 <b>مسجل</b> (<code>...{gemini_key[-6:]}</code>)" if has_gemini else "⚪ <i>غير مسجل (يستخدم الافتراضي)</i>"
        jules_txt = f"🟢 <b>مسجل</b> (<code>...{jules_key[-6:]}</code>)" if has_jules else "⚪ <i>غير مسجل (يستخدم الافتراضي)</i>"

        model_choice = user.get("selected_model", config.MODEL_CHOICE_FLASH) if user else config.MODEL_CHOICE_FLASH
        if model_choice == config.MODEL_CHOICE_PRO:
            model_display = config.MODEL_PRO_NAME
        elif model_choice == config.MODEL_CHOICE_AGENT:
            model_display = config.MODEL_AGENT_NAME
        else:
            model_display = config.MODEL_FLASH_NAME

        is_admin = PermissionService.is_admin(user_id)
        kb = get_apikey_dashboard_keyboard(has_gemini, has_jules, is_admin)

        text = (
            "🔑 <b>لوحة إدارة مفاتيح API والنماذج:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <b>مفتاح الدردشة الفورية (Gemini Studio):</b>\n{gemini_txt}\n\n"
            f"🛠️ <b>مفتاح الوكيل البرمجي المتقدم:</b>\n{jules_txt}\n\n"
            f"🎯 <b>النموذج / الوضع النشط حالياً:</b>\n<code>{model_display}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <b>طرق الإدخال السريعة:</b>\n"
            "• اضغط على الأزرار بالأسفل لإدخال المفتاح تفاعلياً.\n"
            "• أو أرسل المفتاح مباشرة: <code>/apikey YOUR_KEY</code> وسيتعرف البوت تلقائياً على نوعه!\n"
            "• أو حدد نوعه صراحة: <code>/apikey jules &lt;key&gt;</code> أو <code>/apikey studio &lt;key&gt;</code>"
        )

        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    # Arguments provided: handle clear, explicit type, or auto-detect
    if update.effective_chat.type != "private":
        try:
            await update.message.delete()
        except Exception:
            pass

    first_arg = context.args[0].strip()

    if first_arg.lower() == "clear":
        await UserRepository.update_custom_api_key(user_id, None)
        await SettingsRepository.set_setting(f"user_gemini_key:{user_id}", "")
        await SettingsRepository.set_setting(f"user_jules_key:{user_id}", "")
        await update.message.reply_text("✅ تم مسح جميع مفاتيحك الخاصة بنجاح. يتم الآن استخدام المفاتيح الافتراضية للبوت.")
        return

    # Check for explicit prefix: /apikey jules <key> or /apikey studio <key>
    if first_arg.lower() in ["jules", "agent"] and len(context.args) > 1:
        key_val = context.args[1].strip()
        await SettingsRepository.set_setting(f"user_jules_key:{user_id}", key_val)
        await UserRepository.update_custom_api_key(user_id, key_val)
        await UserRepository.update_model(user_id, config.MODEL_CHOICE_AGENT)
        await update.message.reply_text(
            f"✅ <b>تم تعيين مفتاح Google Jules بنجاح!</b>\n"
            f"• تم تحويل الوضع النشط إلى: <b>{config.MODEL_AGENT_NAME}</b>\n"
            "يمكنك استعراض مستودعاتك عبر <code>/repos</code> والبدء في تنفيذ المهام.",
            parse_mode=ParseMode.HTML
        )
        return

    if first_arg.lower() in ["gemini", "studio", "flash", "pro"] and len(context.args) > 1:
        key_val = context.args[1].strip()
        await SettingsRepository.set_setting(f"user_gemini_key:{user_id}", key_val)
        await UserRepository.update_custom_api_key(user_id, key_val)
        await UserRepository.update_model(user_id, config.MODEL_CHOICE_FLASH)
        await update.message.reply_text(
            f"✅ <b>تم تعيين مفتاح Google AI Studio بنجاح!</b>\n"
            f"• تم تفعيل وضع الشات السريع: <b>{config.MODEL_FLASH_NAME}</b>\n"
            "أرسل استفساراتك وأسئلتك في الشات مباشرة.",
            parse_mode=ParseMode.HTML
        )
        return

    # Single argument provided: Auto-detect type
    key_val = first_arg
    if len(key_val) < 15:
        await update.message.reply_text("❌ يبدو أن المفتاح المدخل غير صالح (قصير جداً).")
        return

    if key_val.startswith("AQ."):
        # Detected as Jules API Key
        await SettingsRepository.set_setting(f"user_jules_key:{user_id}", key_val)
        await UserRepository.update_custom_api_key(user_id, key_val)
        await UserRepository.update_model(user_id, config.MODEL_CHOICE_AGENT)
        await update.message.reply_text(
            "✨ <b>تم التعرف تلقائياً على المفتاح:</b>\n"
            "🛠️ <b>مفتاح Google Jules الرسمي المستقل (Autonomous Agent)</b>\n\n"
            f"• تم حفظ المفتاح وتفعيل وضع: <b>{config.MODEL_AGENT_NAME}</b>\n"
            "استخدم <code>/repos</code> لاختيار المستودع والبدء في تنفيذ المهام البرمجية.",
            parse_mode=ParseMode.HTML
        )
    elif key_val.startswith("AIza"):
        # Detected as Google AI Studio Key
        await SettingsRepository.set_setting(f"user_gemini_key:{user_id}", key_val)
        await UserRepository.update_custom_api_key(user_id, key_val)
        await UserRepository.update_model(user_id, config.MODEL_CHOICE_FLASH)
        await update.message.reply_text(
            "✨ <b>تم التعرف تلقائياً على المفتاح:</b>\n"
            "⚡ <b>مفتاح Google AI Studio للدردشة اللحظية</b>\n\n"
            f"• تم حفظ المفتاح وتفعيل: <b>{config.MODEL_FLASH_NAME}</b>\n"
            "أرسل استفساراتك أو طلباتك في الشات وسيجيبك المساعد فوراً!",
            parse_mode=ParseMode.HTML
        )
    else:
        # General API Key
        await UserRepository.update_custom_api_key(user_id, key_val)
        await update.message.reply_text("✅ تم حفظ مفتاح API الخاص بك بنجاح! سيتم توجيه جميع طلباتك باستخدامه.")


async def github_token_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /github: manages GitHub Personal Access Token for auto-downloading files directly to Telegram."""
    user_id = update.effective_user.id
    if not context.args:
        curr_token = await SettingsRepository.get_setting(f"github_token:{user_id}", "")
        has_token = bool(curr_token)
        status = "🟢 لديك توكن GitHub محفوظ" if has_token else "⚪ لا يوجد توكن مسجل حالياً"

        await update.message.reply_text(
            "🐙 <b>إدارة توكن GitHub (لتحميل الملفات إلى تيليجرام مباشرة):</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"الحالة الحالية: {status}\n\n"
            "💡 <b>فائدة التوكن:</b>\n"
            "يتيح للبوت سحب أي ملف يتم إنشاؤه (مثل مستندات Word، ملفات الكود، الصور، المضغوطة) "
            "وإرسالها مباشرة كملف مرفق في شات تيليجرام دون الحاجة لفتح GitHub نهائياً!\n\n"
            "• لحفظ التوكن:\n"
            "<code>/github YOUR_GITHUB_TOKEN</code>\n\n"
            "• لمسح التوكن:\n"
            "<code>/github clear</code>",
            parse_mode=ParseMode.HTML
        )
        return

    if update.effective_chat.type != "private":
        try:
            await update.message.delete()
        except Exception:
            pass

    arg = context.args[0].strip()
    if arg.lower() == "clear":
        await SettingsRepository.set_setting(f"github_token:{user_id}", "")
        await update.message.reply_text("✅ تم مسح توكن GitHub بنجاح.")
    else:
        if len(arg) < 15:
            await update.message.reply_text("❌ يبدو أن التوكن المدخل غير صالح (قصير جداً).")
            return
        await SettingsRepository.set_setting(f"github_token:{user_id}", arg)
        await update.message.reply_text(
            "✅ <b>تم حفظ توكن GitHub بنجاح!</b>\n"
            "سيقوم البوت الآن بسحب الملفات الناتجة عن مهامك وتوصيلها إليك مباشرة في الشات بصيغتها الأصلية!",
            parse_mode=ParseMode.HTML
        )


async def repos_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /repos: lists connected GitHub repositories from Jules API."""
    user_id = update.effective_user.id
    allowed, reason = await PermissionService.check_access(user_id, config.FEATURE_AUTONOMOUS_AGENT)
    if not allowed:
        await update.message.reply_text(reason)
        return

    # Check for direct clear/none argument
    if context.args:
        arg = context.args[0].strip().lower()
        if arg in ["clear", "none", "disable", "cancel"]:
            await SettingsRepository.set_setting(f"user_source:{user_id}", "")
            await UserRepository.update_model(user_id, "gemini-3.6-flash")
            await update.message.reply_text(
                "💬 <b>تم فك ارتباط المستودع وتفعيل وضع الدردشة البرمجية المباشرة:</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "• يمكنك الآن إرسال طلباتك وأكوادك مباشرة في الشات وسأجيبك فوراً!",
                parse_mode=ParseMode.HTML
            )
            return

    # Strict Privacy: Only Admin or users with personal custom API key can browse repositories
    is_admin = PermissionService.is_admin(user_id)
    user_key = await SettingsRepository.get_setting(f"user_jules_key:{user_id}", "")
    if not is_admin and not user_key:
        await update.message.reply_text(
            "ℹ️ <b>الوضع المباشر مفعل تلقائياً:</b>\n\n"
            "• يمكنك إرسال استفساراتك ومهامك البرمجية في الشات مباشرة.\n"
            "• ميزة ربط المستودعات الخاصة تتطلب إدخال مفتاحك الخاص عبر <code>/apikey</code>.",
            parse_mode=ParseMode.HTML
        )
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    try:
        effective_key = user_key or (config.JULES_API_KEY if is_admin else None)
        sources = await JulesApiClient.list_sources(api_key=effective_key)
        if not sources:
            await update.message.reply_text(
                "ℹ️ لم يتم العثور على مستودعات متصلة بحسابك.\n"
                "يمكنك استخدام الوضع المباشر بدون مستودع عبر <code>/repos none</code>.",
                parse_mode=ParseMode.HTML
            )
            return

        active_source = await SettingsRepository.get_setting(f"user_source:{user_id}", "")
        keyboard = get_sources_keyboard(sources, active_source)
        await update.message.reply_text(
            "📁 <b>المستودعات البرمجية المتصلة:</b>\n"
            "اضغط على المستودع المطلوب لتحديده كوجهة للمهام البرمجية القادمة:",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
    except Exception as exc:
        logger.exception("Error in /repos: %s", exc)
        await update.message.reply_text(f"⚠️ تعذر استعراض المستودعات: {exc}")


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /tasks: lists recent coding sessions strictly isolated per user."""
    user_id = update.effective_user.id
    allowed, reason = await PermissionService.check_access(user_id, config.FEATURE_AUTONOMOUS_AGENT)
    if not allowed:
        await update.message.reply_text(reason)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    try:
        # STRICT PRIVACY: Query ONLY tasks created by this specific user
        user_tasks = await TaskRepository.list_user_tasks(user_id, limit=6)
        if not user_tasks:
            await update.message.reply_text("ℹ️ ليس لديك أي مهام سابقة مسجلة حتى الآن. أرسل طلبك للبدء فوراً.")
            return

        api_key = await JulesService.get_effective_api_key(user_id, key_type="jules")
        lines = ["📋 <b>مهامك السابقة:</b>\n━━━━━━━━━━━━━━━━━━━━━"]
        keyboard_buttons = []

        for t in user_tasks:
            sess_name = t["session_name"]
            clean_id = sess_name.replace("sessions/", "")
            prompt_full = t.get("prompt") or "مهمة برمجية"
            prompt_short = prompt_full[:40].replace("\n", " ")

            state_emoji = "🔹"
            state_label = "قيد المتابعة"
            pr = ""
            try:
                s = await JulesApiClient.get_session(sess_name, api_key=api_key)
                state = str(s.get("state", "UNKNOWN")).upper()
                if state in ["COMPLETED", "SUCCEEDED"]:
                    state_emoji = "✅"
                    state_label = "مكتملة بنجاح"
                elif state in ["IN_PROGRESS", "RUNNING"]:
                    state_emoji = "⚙️"
                    state_label = "قيد التنفيذ"
                elif state in ["STARTING", "INITIALIZING"]:
                    state_emoji = "⏳"
                    state_label = "جاري البدء"
                elif "FEEDBACK" in state or "WAITING" in state or "APPROVAL" in state:
                    state_emoji = "💬"
                    state_label = "بانتظار ردك أو اعتماد الخطة"
                elif state in ["FAILED", "CANCELLED"]:
                    state_emoji = "❌"
                    state_label = "فشلت أو تم الإلغاء"

                raw_outputs = s.get("outputs")
                if isinstance(raw_outputs, list):
                    for item in raw_outputs:
                        if isinstance(item, dict) and "pullRequest" in item:
                            pr_dict = item.get("pullRequest")
                            if isinstance(pr_dict, dict):
                                pr = pr_dict.get("url") or pr_dict.get("htmlUrl") or ""
                                if pr:
                                    break
            except Exception:
                pass

            pr_part = f"\n  🔗 <a href='{pr}'>Pull Request 🚀</a>" if pr else ""
            lines.append(f"{state_emoji} <b>#{clean_id[:8]}</b>: {prompt_short}\n  الحالة: <code>{state_label}</code>{pr_part}")

            btn_label = prompt_full[:14].replace("\n", " ")
            keyboard_buttons.append([
                InlineKeyboardButton(f"💬 رد #{clean_id[:6]}: {btn_label}", callback_data=f"jules:resume:{clean_id}"),
                InlineKeyboardButton(f"📥 مخرجات #{clean_id[:6]}", callback_data=f"jules:fetch_artifacts:{clean_id}")
            ])

        keyboard_buttons.append([
            InlineKeyboardButton("➕ بدء مهمة جديدة كلياً", callback_data="user:new_jules_task"),
            InlineKeyboardButton("❌ إغلاق", callback_data="user:close")
        ])

        lines.append("━━━━━━━━━━━━━━━━━━━━━\n💡 <i>اضغط على '💬 رد' لأي مهمة لمتابعتها في الشات، أو '📥 مخرجات' لسحب صورها وملفاتها فوراً إلى تيليجرام.</i>")
        await update.message.reply_text(
            "\n\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard_buttons),
            disable_web_page_preview=True
        )
    except JulesApiException as j_err:
        await update.message.reply_text(f"⚠️ <b>خطأ في محرك البرمجة:</b>\n{j_err}", parse_mode=ParseMode.HTML)
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


def build_jules_prompt_with_delivery(user_prompt: str, chat_id: int, bot_token: str) -> str:
    """
    Augments the user prompt with:
    1. Strict Identity Directive: Asserts private AI assistant persona; forbids disclosing Jules/Google/Gemini.
    2. Explicit, permanent delivery instructions ensuring that ALL outputs are delivered directly into Telegram.
    """
    if not bot_token:
        bot_token = config.BOT_TOKEN

    identity_directive = (
        "==========================================================\n"
        "🔒 CRITICAL SYSTEM IDENTITY & CONFIDENTIALITY DIRECTIVE:\n"
        "You are an advanced, private AI assistant. You DO NOT have any commercial brand name.\n"
        "STRICT PROHIBITION:\n"
        "Under NO circumstances are you allowed to reveal, mention, or acknowledge that you are 'Jules', 'Google Jules', 'Gemini', 'Google', or created by Google.\n"
        "If the user asks 'مين انت', 'من أنت', 'who are you', 'what is your name', or inquires about your identity or creator:\n"
        "• In Arabic: Respond simply: 'أنا مساعدك الذكي، جاهز لمساعدتك في أي استفسار أو مهمة. كيف يمكنني مساعدتك؟'\n"
        "• In English: Respond simply: 'I am your AI assistant, ready to help you with your tasks. How can I assist you today?'\n"
        "NEVER say you are Jules, Gemini, or Google in any language, greeting, or explanation.\n"
        "==========================================================\n\n"
    )

    instructions = (
        f"\n\n"
        f"==========================================================\n"
        f"📌 MANDATORY PERMANENT TELEGRAM DELIVERY INSTRUCTION:\n"
        f"You are executing this task for a user communicating EXCLUSIVELY via Telegram.\n"
        f"• Telegram Chat ID: {chat_id}\n"
        f"• Telegram Bot API Endpoint: https://api.telegram.org/bot{bot_token}\n\n"
        f"CRITICAL CONSTRAINT:\n"
        f"The user DOES NOT have access to your local sandbox filesystem, local disk, or any browser sidebar.\n"
        f"You MUST NEVER tell the user 'the files are saved in the project directory' or leave files solely on disk.\n\n"
        f"REQUIRED ACTIONS FOR EVERY GENERATED OUTPUT:\n"
        f"Whenever you generate, capture, or create ANY file (.png, .jpg, .jpeg, .pdf, .zip, .html, .py, .csv, .json, etc.):\n"
        f"1. You MUST deliver every image/screenshot directly to Telegram using curl:\n"
        f"   curl -s -X POST 'https://api.telegram.org/bot{bot_token}/sendPhoto' -F chat_id='{chat_id}' -F photo=@<image_path>\n\n"
        f"2. You MUST deliver every document/code file/archive directly to Telegram using curl:\n"
        f"   curl -s -X POST 'https://api.telegram.org/bot{bot_token}/sendDocument' -F chat_id='{chat_id}' -F document=@<file_path>\n\n"
        f"3. You can also run this automated dispatch loop in bash at the end of your work:\n"
        f"   for f in *.png *.jpg *.jpeg *.webp; do [ -f \"$f\" ] && curl -s -X POST 'https://api.telegram.org/bot{bot_token}/sendPhoto' -F chat_id='{chat_id}' -F photo=\"@$f\"; done\n"
        f"   for f in *.pdf *.zip *.html *.json *.py *.csv *.txt *.md; do [ -f \"$f\" ] && curl -s -X POST 'https://api.telegram.org/bot{bot_token}/sendDocument' -F chat_id='{chat_id}' -F document=\"@$f\"; done\n\n"
        f"4. Alternatively, you can upload files to https://tmpfiles.org/api/v1/upload (or https://catbox.moe/user/api.php) and include the download link in your message.\n"
        f"Every single output MUST arrive in the user's Telegram chat. No exceptions.\n"
        f"Remember: Never disclose or mention the names 'Jules', 'Google', or 'Gemini'.\n"
        f"=========================================================="
    )
    return f"{identity_directive}{user_prompt}{instructions}"


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles general incoming text messages from users."""
    user = update.effective_user
    plain_text, markdown_text = extract_incoming_message(update.message)
    text = plain_text.strip()
    ai_prompt = markdown_text.strip() or text

    # Group / Supergroup filter: only process if replied to bot, mentioned, or tapped a button
    is_group = update.effective_chat.type in ["group", "supergroup"]
    keyboard_shortcuts = {
        "⚡ تبديل النموذج", "💬 جلسة جديدة", "📁 مستودعات GitHub", "📂 مستودعاتي", "📁 المستودعات البرمجية",
        "📋 مهامي البرمجية", "📋 المهام", "📋 مهامي السابقة", "📂 جلساتي", "🔑 مفتاح API",
        "ℹ️ المساعدة والمعلومات", "🛠️ لوحة تحكم الأدمن (/admin)"
    }
    bot_username = (context.bot.username or "").lower()
    is_reply_to_bot = bool(
        update.message.reply_to_message
        and update.message.reply_to_message.from_user
        and update.message.reply_to_message.from_user.id == context.bot.id
    )
    is_mentioned = bool(bot_username and f"@{bot_username}" in text.lower())

    if is_group and not (is_reply_to_bot or is_mentioned or text in keyboard_shortcuts):
        return

    # Strip mention if present so prompt sent to AI is clean
    if is_mentioned and bot_username:
        clean_regex = re.compile(rf"@{bot_username}\b", re.IGNORECASE)
        text = clean_regex.sub("", text).strip()
        ai_prompt = clean_regex.sub("", ai_prompt).strip() or text

    # Reply Keyboard button shortcuts
    if text in ["⚡ تبديل النموذج", "🔑 مفتاح API"]:
        if not PermissionService.is_admin(user.id):
            await update.message.reply_text("⛔ هذه الإعدادات تدار بالكامل من قِبل إدارة النظام.")
            return
        if text == "⚡ تبديل النموذج":
            await model_command(update, context)
            return
        elif text == "🔑 مفتاح API":
            await apikey_command(update, context)
            return
    elif text == "💬 جلسة جديدة":
        await new_session_command(update, context)
        return
    elif text in ["📁 مستودعات GitHub", "📂 مستودعاتي", "📁 المستودعات البرمجية"]:
        await repos_command(update, context)
        return
    elif text in ["📋 مهامي البرمجية", "📋 المهام", "📋 مهامي السابقة"]:
        await tasks_command(update, context)
        return
    elif text == "📂 جلساتي":
        await sessions_command(update, context)
        return
    elif text == "ℹ️ المساعدة والمعلومات":
        await help_command(update, context)
        return
    elif text == "🛠️ لوحة تحكم الأدمن (/admin)":
        from handlers.admin_handlers import admin_command
        await admin_command(update, context)
        return

    # Check if admin is setting an API key for a specific user
    if context.user_data.get("admin_setting_key_for"):
        target_id = context.user_data.pop("admin_setting_key_for")
        if PermissionService.is_admin(user.id):
            key_val = text.strip()
            if len(key_val) < 15:
                await update.message.reply_text("❌ يبدو أن المفتاح المدخل غير صالح (قصير جداً).")
                return
            if key_val.startswith("AQ."):
                await SettingsRepository.set_setting(f"user_jules_key:{target_id}", key_val)
                await UserRepository.update_custom_api_key(target_id, key_val)
                await UserRepository.update_model(target_id, config.MODEL_CHOICE_AGENT)
                t_label = "محرك الوكيل البرمجي"
            else:
                await SettingsRepository.set_setting(f"user_gemini_key:{target_id}", key_val)
                await UserRepository.update_custom_api_key(target_id, key_val)
                t_label = "Google AI Studio"
            await update.message.reply_text(
                f"✅ <b>تم حفظ وتعيين المفتاح للمستخدم (ID: <code>{target_id}</code>) بنجاح ({t_label})!</b>",
                parse_mode=ParseMode.HTML
            )
            return

    # Check if user is actively entering an API key via interactive button prompt
    if "awaiting_api_key" in context.user_data:
        key_type = context.user_data.pop("awaiting_api_key")
        key_val = text.strip()
        if len(key_val) < 15:
            await update.message.reply_text("❌ يبدو أن المفتاح المدخل غير صالح (قصير جداً).")
            return

        if key_type == "jules":
            await SettingsRepository.set_setting(f"user_jules_key:{user.id}", key_val)
            await UserRepository.update_custom_api_key(user.id, key_val)
            await UserRepository.update_model(user.id, config.MODEL_CHOICE_AGENT)
            await update.message.reply_text(
                "✅ <b>تم حفظ وتفعيل مفتاح محرك الوكيل البرمجي بنجاح!</b>\n"
                f"• تم تحويل الوضع إلى: <b>{config.MODEL_AGENT_NAME}</b>\n\n"
                "يمكنك استعراض مستودعاتك أو إرسال طلباتك البرمجية في الشات مباشرة.",
                parse_mode=ParseMode.HTML
            )
            return
        else:
            await SettingsRepository.set_setting(f"user_gemini_key:{user.id}", key_val)
            await UserRepository.update_custom_api_key(user.id, key_val)
            await UserRepository.update_model(user.id, config.MODEL_CHOICE_FLASH)
            await update.message.reply_text(
                "✅ <b>تم حفظ وتفعيل مفتاح Google AI Studio بنجاح!</b>\n"
                f"• تم تفعيل وضع الشات الفوري: <b>{config.MODEL_FLASH_NAME}</b>\n\n"
                "أرسل استفساراتك وأسئلتك في الشات مباشرة وسأجيبك فوراً.",
                parse_mode=ParseMode.HTML
            )
            return

    if context.user_data.get("awaiting_sys_key"):
        context.user_data.pop("awaiting_sys_key", None)
        if PermissionService.is_admin(user.id):
            key_val = text.strip()
            if key_val.startswith("AQ."):
                await SettingsRepository.set_setting("system_jules_key", key_val)
                await SettingsRepository.set_setting("system_api_key", key_val)
                target = "Jules API"
            else:
                await SettingsRepository.set_setting("system_gemini_key", key_val)
                await SettingsRepository.set_setting("system_api_key", key_val)
                target = "Google AI Studio"
            await update.message.reply_text(f"👑 <b>تم تعيين المفتاح العام لكافة مستخدمي البوت بنجاح ({target})!</b>", parse_mode=ParseMode.HTML)
            return

    # Check if user is entering a custom model name
    if context.user_data.get("awaiting_custom_model"):
        context.user_data.pop("awaiting_custom_model", None)
        model_input = text.strip().lower()
        resolved_id = JulesService.resolve_model_id(model_input)
        model_target = "agent" if model_input in ["agent", "jules"] else model_input
        await UserRepository.update_model(user.id, model_target)
        await update.message.reply_text(
            f"✅ <b>تم ضبط النموذج المخصص بنجاح!</b>\n"
            f"• المعرف المعتمد: <code>{resolved_id}</code>\n\n"
            "يمكنك البدء في إرسال استفساراتك وأسئلتك الآن.",
            parse_mode=ParseMode.HTML
        )
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
    sys_model = await SettingsRepository.get_setting("system_model", config.MODEL_CHOICE_FLASH)
    selected_model = user_db.get("selected_model") or sys_model

    # Check effective API key to route Jules tasks seamlessly
    effective_api_key = await JulesService.get_effective_api_key(user.id, key_type="any")
    is_jules_engine = (
        (effective_api_key and effective_api_key.startswith("AQ."))
        or selected_model == config.MODEL_CHOICE_AGENT
        or (selected_model in ["gemini-3.6-flash", "gemini-3.1-pro"] and (not effective_api_key or not effective_api_key.startswith("AIza")))
    )

    if is_jules_engine:
        active_source = await SettingsRepository.get_setting(f"user_source:{user.id}", "")

        # If user explicitly chose Agent mode and has not selected a repo:
        if selected_model == config.MODEL_CHOICE_AGENT and not active_source:
            try:
                sources = await JulesApiClient.list_sources(api_key=effective_api_key)
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
                        "⚠️ <b>لم يتم العثور على مستودعات برمجية متصلة</b>\n"
                        "يمكنك المتابعة مباشرة دون مستودع عبر <code>/repos none</code> أو اختيار نموذج شات عبر <code>/model</code>.",
                        parse_mode=ParseMode.HTML
                    )
            except Exception as exc:
                await update.message.reply_text(f"⚠️ يرجى اختيار المستودع أولاً عبر <code>/repos</code> ({exc})")
            return

        # Check if user is replying to an active ongoing Jules task
        active_sess = await SettingsRepository.get_setting(f"active_jules_sess:{user.id}", "")
        if active_sess:
            clean_id = active_sess.replace("sessions/", "")
            status_msg = await update.message.reply_text(
                f"💬 <b>جاري متابعة المهمة البرمجية (#{clean_id[:8]})...</b>\n"
                f"📝 <b>التعليق:</b> <i>{text[:100]}</i>\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "⏳ جاري متابعة الرد وتنفيذ التعديلات...",
                parse_mode=ParseMode.HTML
            )
            jules_full_prompt = build_jules_prompt_with_delivery(ai_prompt, update.effective_chat.id, context.bot.token)
            try:
                await JulesApiClient.send_message(active_sess, jules_full_prompt, api_key=effective_api_key)
                repo_label = active_source.replace("sources/github-", "").replace("sources/", "") if active_source else "متابعة المهمة"
                await TaskMonitorService.start_monitoring(
                    bot=context.bot,
                    chat_id=update.effective_chat.id,
                    status_message_id=status_msg.message_id,
                    session_name=active_sess,
                    repo_name=repo_label,
                    prompt=ai_prompt,
                    user_id=user.id,
                    api_key=effective_api_key
                )
                return
            except Exception as exc:
                err_str = str(exc).lower()
                if "404" in err_str or "not found" in err_str:
                    logger.warning("Session %s not found on Jules, clearing: %s", active_sess, exc)
                    await SettingsRepository.set_setting(f"active_jules_sess:{user.id}", "")
                    # fall through to create new session
                else:
                    logger.exception("Error sending message to active Jules session %s: %s", active_sess, exc)
                    await status_msg.edit_text(
                        f"⚠️ <b>تعذر إرسال الأمر للجلسة الحالية (#{clean_id[:8]}):</b>\n"
                        f"<code>{exc}</code>\n\n"
                        "💡 يمكنك إعادة المحاولة بعد ثوانٍ، أو الضغط على زر <b>💬 جلسة جديدة</b> في اللوحة أدناه لبدء مهمة جديدة من الصفر.",
                        parse_mode=ParseMode.HTML
                    )
                    return

        # Start a new Jules task/session
        repo_display = "بدون مستودع (مباشر)"
        if active_source and active_source != "none":
            repo_display = active_source.replace("sources/github-", "").replace("sources/", "")

        status_msg = await update.message.reply_text(
            f"🚀 <b>جاري معالجة وتنفيذ طلبك برمجياً...</b>\n"
            f"📁 <b>البيئة:</b> <code>{repo_display}</code>\n"
            f"📝 <b>الطلب:</b> <i>{text[:100]}</i>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⏳ جاري تجهيز بيئة العمل والبدء في التنفيذ...",
            parse_mode=ParseMode.HTML
        )

        try:
            jules_full_prompt = build_jules_prompt_with_delivery(ai_prompt, update.effective_chat.id, context.bot.token)
            if active_source and active_source != "none":
                session_obj = await JulesApiClient.create_session(
                    source=active_source,
                    prompt=jules_full_prompt,
                    api_key=effective_api_key
                )
            else:
                session_obj = await JulesApiClient.create_chat_session(
                    prompt=jules_full_prompt,
                    api_key=effective_api_key
                )

            session_name = session_obj.get("name")
            await SettingsRepository.set_setting(f"active_jules_sess:{user.id}", session_name)
            await TaskRepository.add_task(user.id, session_name, ai_prompt, repo_display)
            await TaskMonitorService.start_monitoring(
                bot=context.bot,
                chat_id=update.effective_chat.id,
                status_message_id=status_msg.message_id,
                session_name=session_name,
                repo_name=repo_display,
                prompt=ai_prompt,
                user_id=user.id,
                api_key=effective_api_key
            )
        except Exception as exc:
            logger.exception("Error launching Jules API session: %s", exc)
            await status_msg.edit_text(
                f"❌ <b>تعذر بدء المهمة البرمجية:</b>\n<code>{exc}</code>\n\n"
                "تحقق من صلاحية المفتاح عبر <code>/apikey</code>.",
                parse_mode=ParseMode.HTML
            )
        return

    # Conversational chat with Flash or Pro
    session = await SessionRepository.get_active_session(user.id)

    # Send live typing action indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # Generate answer with Jules / Gemini Studio
    response_text = await JulesService.generate_response(
        user_id=user.id,
        session_id=session["session_id"],
        user_prompt=ai_prompt
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
    # Group check: only process if replied to bot or captioned with bot username
    is_group = update.effective_chat.type in ["group", "supergroup"]
    bot_username = (context.bot.username or "").lower()
    caption_text = (update.message.caption or "").strip()
    is_reply_to_bot = bool(
        update.message.reply_to_message
        and update.message.reply_to_message.from_user
        and update.message.reply_to_message.from_user.id == context.bot.id
    )
    is_mentioned = bool(bot_username and f"@{bot_username}" in caption_text.lower())
    if is_group and not (is_reply_to_bot or is_mentioned):
        return

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
    # Group check: only process if replied to bot or captioned with bot username
    is_group = update.effective_chat.type in ["group", "supergroup"]
    bot_username = (context.bot.username or "").lower()
    caption_text = (update.message.caption or "").strip()
    is_reply_to_bot = bool(
        update.message.reply_to_message
        and update.message.reply_to_message.from_user
        and update.message.reply_to_message.from_user.id == context.bot.id
    )
    is_mentioned = bool(bot_username and f"@{bot_username}" in caption_text.lower())
    if is_group and not (is_reply_to_bot or is_mentioned):
        return

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

    user_db = await UserRepository.get_or_create(user.id, user.username, user.first_name)
    sys_model = await SettingsRepository.get_setting("system_model", config.MODEL_CHOICE_FLASH)
    selected_model = user_db.get("selected_model") or sys_model

    effective_api_key = await JulesService.get_effective_api_key(user.id, key_type="any")
    is_jules_engine = (
        (effective_api_key and effective_api_key.startswith("AQ."))
        or selected_model == config.MODEL_CHOICE_AGENT
        or (selected_model in ["gemini-3.6-flash", "gemini-3.1-pro"] and (not effective_api_key or not effective_api_key.startswith("AIza")))
    )

    if is_jules_engine:
        active_source = await SettingsRepository.get_setting(f"user_source:{user.id}", "")
        repo_display = "بدون مستودع (مباشر)"
        if active_source and active_source != "none":
            repo_display = active_source.replace("sources/github-", "").replace("sources/", "")

        caption_text = update.message.caption or f"تنفيذ المهمة بناءً على الملف {file_name}"
        effective_prompt = f"{caption_text}\n(الملف المرفق: {file_name})"

        status_msg = await update.message.reply_text(
            f"🚀 <b>جاري معالجة الملف وتنفيذ المهمة برمجياً...</b>\n"
            f"📁 <b>المستهدف:</b> <code>{repo_display}</code>\n"
            f"📄 <b>الملف:</b> <code>{file_name}</code>\n"
            f"📝 <b>الطلب:</b> <i>{caption_text[:100]}</i>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⏳ جاري تشغيل بيئة العمل وتوليد الملفات والمخرجات...",
            parse_mode=ParseMode.HTML
        )

        try:
            jules_full_prompt = build_jules_prompt_with_delivery(effective_prompt, update.effective_chat.id, context.bot.token)
            if active_source and active_source != "none":
                session_obj = await JulesApiClient.create_session(
                    source=active_source,
                    prompt=jules_full_prompt,
                    api_key=effective_api_key
                )
            else:
                session_obj = await JulesApiClient.create_chat_session(
                    prompt=jules_full_prompt,
                    api_key=effective_api_key
                )

            session_name = session_obj.get("name")
            await SettingsRepository.set_setting(f"active_jules_sess:{user.id}", session_name)
            await TaskRepository.add_task(user.id, session_name, effective_prompt, repo_display)
            await TaskMonitorService.start_monitoring(
                bot=context.bot,
                chat_id=update.effective_chat.id,
                status_message_id=status_msg.message_id,
                session_name=session_name,
                repo_name=repo_display,
                prompt=effective_prompt,
                user_id=user.id,
                api_key=effective_api_key
            )
        except Exception as exc:
            logger.exception("Error launching Jules API session for document: %s", exc)
            await status_msg.edit_text(
                f"❌ <b>تعذر بدء المهمة البرمجية:</b>\n<code>{exc}</code>",
                parse_mode=ParseMode.HTML
            )
        return

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

    elif data == "user:noop":
        await query.answer()
        return

    # Restrict model selection and key configuration callbacks to admin only
    if data.startswith("user:set_model:") or data.startswith("user:set_key_prompt:") or data in [
        "user:open_model_menu", "user:custom_model_prompt", "user:clear_keys"
    ]:
        if not PermissionService.is_admin(user_id):
            await query.answer("⛔ اختيار النماذج وإدارة المفاتيح تدار من قِبل إدارة النظام فقط.", show_alert=True)
            return

    elif data.startswith("user:set_model:"):
        model_target = data.split(":")[2]

        # Permission check: switch_model
        allowed, reason = await PermissionService.check_access(user_id, config.FEATURE_SWITCH_MODEL)
        if not allowed:
            await query.answer(reason, show_alert=True)
            return

        # If selecting pro, check use_pro permission
        if "pro" in model_target:
            allowed_pro, reason_pro = await PermissionService.check_access(user_id, config.FEATURE_USE_PRO)
            if not allowed_pro:
                await query.answer(reason_pro, show_alert=True)
                return
        elif model_target in ["agent", config.MODEL_CHOICE_AGENT]:
            allowed_agent, reason_agent = await PermissionService.check_access(user_id, config.FEATURE_AUTONOMOUS_AGENT)
            if not allowed_agent:
                await query.answer(reason_agent, show_alert=True)
                return

        if model_target in ["agent", config.MODEL_CHOICE_AGENT]:
            canonical_to_save = "agent"
            display_name = "🛠️ وكيل هندسة البرمجيات المستقل"
        else:
            canonical_to_save = JulesService.resolve_model_id(model_target)
            display_name = canonical_to_save

        await UserRepository.update_model(user_id, canonical_to_save)

        try:
            await query.edit_message_reply_markup(reply_markup=get_model_switch_keyboard(canonical_to_save))
        except Exception:
            pass

        extra_tip = ""
        if canonical_to_save == "agent":
            active_src = await SettingsRepository.get_setting(f"user_source:{user_id}", "")
            if active_src:
                clean_src = active_src.replace("sources/github-", "").replace("sources/", "")
                extra_tip = f"\n📁 <b>المستودع المستهدف:</b> <code>{clean_src}</code>\nأرسل طلبك في الشات لتنفيذ المهمة!"
            else:
                extra_tip = "\n⚠️ لم تحدد مستودعاً بعد! استخدم الأمر <code>/repos</code> لاختيار المستودع."

        await query.message.reply_text(
            f"✅ <b>تم تفعيل النموذج المعتمد بنجاح:</b>\n"
            f"🎯 <code>{display_name}</code>{extra_tip}",
            parse_mode=ParseMode.HTML
        )

    elif data == "user:custom_model_prompt":
        context.user_data["awaiting_custom_model"] = True
        await query.message.reply_text(
            "✏️ <b>إدخال اسم نموذج مخصص:</b>\n"
            "أرسل الآن اسم أو رقم النموذج في الشات (مثال: <code>3.6</code> أو <code>3.7-flash</code> أو <code>3.8-pro</code> أو <code>gemini-3.7-pro</code>):",
            parse_mode=ParseMode.HTML
        )

    elif data.startswith("user:set_key_prompt:"):
        key_type = data.split(":")[2]  # gemini or jules
        context.user_data["awaiting_api_key"] = key_type
        if key_type == "jules":
            await query.message.reply_text(
                "🛠️ <b>إعداد مفتاح محرك الوكيل المتقدم:</b>\n"
                "أرسل الآن المفتاح الخاص بك في الشات (يبدأ بـ <code>AQ.Ab...</code>):\n\n"
                "💡 سيتم حفظ المفتاح وتشفيره واستخدامه لمهامك البرمجية.",
                parse_mode=ParseMode.HTML
            )
        else:
            await query.message.reply_text(
                "⚡ <b>إعداد مفتاح Google AI Studio:</b>\n"
                "أرسل الآن مفتاح Studio الخاص بك في الشات (يبدأ بـ <code>AIzaSy...</code>):\n\n"
                "💡 يتم استخراجه مجاناً من: https://aistudio.google.com/app/apikey",
                parse_mode=ParseMode.HTML
            )

    elif data == "user:open_model_menu":
        user = await UserRepository.get_by_id(user_id)
        current_model = user.get("selected_model", config.MODEL_CHOICE_FLASH) if user else config.MODEL_CHOICE_FLASH
        try:
            await query.edit_message_reply_markup(reply_markup=get_model_switch_keyboard(current_model))
        except Exception:
            pass

    elif data == "user:clear_keys":
        await UserRepository.update_custom_api_key(user_id, None)
        await SettingsRepository.set_setting(f"user_gemini_key:{user_id}", "")
        await SettingsRepository.set_setting(f"user_jules_key:{user_id}", "")
        try:
            kb = get_apikey_dashboard_keyboard(has_gemini=False, has_jules=False, is_admin=PermissionService.is_admin(user_id))
            await query.edit_message_reply_markup(reply_markup=kb)
        except Exception:
            pass
        await query.message.reply_text("🗑️ تم مسح جميع مفاتيحك الخاصة والعودة للافتراضي بنجاح.")

    elif data == "admin:set_sys_key_prompt":
        if PermissionService.is_admin(user_id):
            context.user_data["awaiting_sys_key"] = True
            await query.message.reply_text(
                "👑 <b>تعيين المفتاح العام للبوت (Admin):</b>\n"
                "أرسل الآن المفتاح الجديد في الشات، وسيتعرف البوت تلقائياً على نوعه ويطبقه على كافة المستخدمين.",
                parse_mode=ParseMode.HTML
            )

    elif data.startswith("user:sel_src:"):
        source_name = data.replace("user:sel_src:", "")
        if source_name == "none":
            await SettingsRepository.set_setting(f"user_source:{user_id}", "")
            await UserRepository.update_model(user_id, "gemini-3.6-flash")
            await query.answer("تم تفعيل وضع الدردشة المباشرة (بدون مستودع)!")
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass
            await query.message.reply_text(
                "💬 <b>تم تفعيل وضع المعالجة المباشرة (بدون مستودع):</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "• تم فك ارتباط أي مستودع برمجي.\n"
                "• تم ضبط النموذج على: <code>gemini-3.6-flash</code>.\n"
                "• يمكنك الآن إرسال استفساراتك ومهامك مباشرة وسيجيبك المساعد فوراً في الشات!",
                parse_mode=ParseMode.HTML
            )
            return

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

    elif data == "user:new_session" or data == "user:new_jules_task":
        await SettingsRepository.set_setting(f"active_jules_sess:{user_id}", "")
        session_id = await SessionRepository.create_session(user_id)
        await query.answer("تم بدء جلسة جديدة!")
        await query.message.reply_text(
            f"✨ <b>تم بدء مهمة وجلسة عمل جديدة كلياً!</b>\n"
            "أرسل طلبك أو استفسارك في الشات وسأبدأ بمهمة جديدة منفصلة.",
            parse_mode=ParseMode.HTML
        )

    elif data.startswith("jules:approve:"):
        clean_id = data.replace("jules:approve:", "")
        is_admin = PermissionService.is_admin(user_id)
        if not is_admin:
            user = await UserRepository.get_by_id(user_id)
            has_custom_key = bool(user and user.get("custom_api_key"))
            if not has_custom_key:
                owned = await TaskRepository.is_task_owned_by_user(user_id, clean_id)
                if not owned:
                    await query.answer("⛔ لا تملك صلاحية اعتماد هذه المهمة.", show_alert=True)
                    return
        api_key = await JulesService.get_effective_api_key(user_id, key_type="jules")
        try:
            await JulesApiClient.approve_plan(clean_id, api_key=api_key)
            await query.answer("✅ تم اعتماد الخطة بنجاح!")
            await query.message.reply_text(
                f"✅ <b>تم اعتماد خطة المهمة #{clean_id[:8]}!</b>\n"
                "جاري مواصلة العمل وسحب المخرجات والصور فور توليدها...",
                parse_mode=ParseMode.HTML
            )
            await TaskMonitorService.start_monitoring(
                bot=context.bot,
                chat_id=update.effective_chat.id,
                status_message_id=query.message.message_id,
                session_name=f"sessions/{clean_id}",
                repo_name="مهمة معتمدة",
                prompt="تنفيذ الخطة المعتمدة",
                user_id=user_id,
                api_key=api_key
            )
        except Exception as exc:
            logger.exception("Error approving plan: %s", exc)
            await query.answer(f"فشل اعتماد الخطة: {exc}", show_alert=True)

    elif data.startswith("jules:resume:") or data.startswith("jules:reply:"):
        clean_id = data.split(":")[2]
        is_admin = PermissionService.is_admin(user_id)
        if not is_admin:
            user = await UserRepository.get_by_id(user_id)
            has_custom_key = bool(user and user.get("custom_api_key"))
            if not has_custom_key:
                owned = await TaskRepository.is_task_owned_by_user(user_id, clean_id)
                if not owned:
                    await query.answer("⛔ لا تملك صلاحية الوصول إلى هذه المهمة.", show_alert=True)
                    return
        await SettingsRepository.set_setting(f"active_jules_sess:{user_id}", f"sessions/{clean_id}")
        await query.answer("تم الاتصال بالمهمة!")
        await query.message.reply_text(
            f"💬 <b>أنت الآن متصل بالمهمة #{clean_id[:8]}:</b>\n\n"
            "أي تعليق أو رسالة ترسلها الآن في الشات ستصل مباشرة إلى بيئة عمل هذه المهمة لمتابعة التعديلات والرد عليك!",
            parse_mode=ParseMode.HTML
        )

    elif data.startswith("jules:fetch_artifacts:"):
        clean_id = data.replace("jules:fetch_artifacts:", "")
        is_admin = PermissionService.is_admin(user_id)
        if not is_admin:
            user = await UserRepository.get_by_id(user_id)
            has_custom_key = bool(user and user.get("custom_api_key"))
            if not has_custom_key:
                owned = await TaskRepository.is_task_owned_by_user(user_id, clean_id)
                if not owned:
                    await query.answer("⛔ لا تملك صلاحية الوصول إلى مخرجات هذه المهمة.", show_alert=True)
                    return
        api_key = await JulesService.get_effective_api_key(user_id, key_type="jules")
        await SettingsRepository.set_setting(f"active_jules_sess:{user_id}", f"sessions/{clean_id}")
        await query.answer("جاري سحب المخرجات والملفات...")
        try:
            activities = await JulesApiClient.list_activities(f"sessions/{clean_id}", api_key=api_key)
            session_data = await JulesApiClient.get_session(f"sessions/{clean_id}", api_key=api_key)
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

            await TaskMonitorService.deliver_task_artifacts(
                bot=context.bot,
                chat_id=update.effective_chat.id,
                user_id=user_id,
                pr_url=pr_url,
                activities=activities
            )
            await query.message.reply_text(
                f"✅ <b>تم استخراج مخرجات وسكرينات المهمة #{clean_id[:8]} بنجاح!</b>\n\n"
                "💬 <b>أنت الآن متصل بهذه المهمة تلقائياً:</b>\n"
                "أي تعليق أو طلب ترسله في الشات الآن (مثل 'استخرج الملفات' أو 'عدل كذا') ستتم متابعته وتنفيذه في نفس بيئة العمل هذه دون فتح مهمة جديدة.",
                parse_mode=ParseMode.HTML
            )
        except Exception as exc:
            logger.exception("Error fetching artifacts: %s", exc)
            await query.message.reply_text(f"⚠️ تعذر سحب مخرجات المهمة: {exc}")


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
    app.add_handler(CommandHandler("github", github_token_command))
    app.add_handler(CommandHandler("gh", github_token_command))

    # Compose mode commands
    app.add_handler(CommandHandler("compose", compose_command))
    app.add_handler(CommandHandler("preview", preview_compose_command))
    app.add_handler(CommandHandler("undo", undo_compose_command))
    app.add_handler(CommandHandler("done", done_compose_command))
    app.add_handler(CommandHandler("cancel", cancel_compose_command))

    app.add_handler(CallbackQueryHandler(user_callback_handler, pattern=r"^(user|jules):"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_message_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, document_message_handler))


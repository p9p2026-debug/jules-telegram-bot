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
from database.repositories import SessionRepository, UserRepository
from services.format_service import FormatService
from services.jules_service import JulesService
from services.permission_service import PermissionService
from utils.keyboards import (
    get_main_keyboard,
    get_model_switch_keyboard,
    get_sessions_keyboard
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
    model_choice = user_db.get("selected_model", "flash")
    model_display = config.MODEL_PRO_NAME if model_choice == "pro" else config.MODEL_FLASH_NAME
    is_admin = PermissionService.is_admin(user.id)

    welcome_text = (
        f"🤖 <b>أهلاً بك يا {user.first_name} في وكيل Jules by Google المتقدم!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "أنا وكيلك الهندسي والبرمجي المتكامل، مدعوم بأحدث نماذج Google Gemini.\n\n"
        "✨ <b>قدراتي وخدماتي البرمجية:</b>\n"
        "• كتابة وتدقيق الأكواد بمختلف لغات البرمجة وحل المشكلات المعقدة.\n"
        "• مراجعة وتصميم المعماريات البرمجية السحابية (Cloud Architectures).\n"
        "• تحليل مستندات الأكواد والملفات البرمجية (PDF, Markdown, Python, إلخ).\n"
        "• فحص وتفسير المخططات والتصاميم من الصور والمخططات التوضيحية.\n"
        "• الحفاظ على سياق الجلسة واسترجاع المحادثات البرمجية.\n\n"
        f"⚡ <b>النموذج النشط حالياً:</b> <code>{model_display}</code>\n"
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
        "📖 <b>دليل استخدام وأوامر Jules Telegram Bot:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <b>النماذج والذكاء الاصطناعي:</b>\n"
        "• <code>/model</code> - التبديل التفاعلي بين Gemini 3.6 Flash و Gemini 3.1 Pro.\n\n"
        "💬 <b>إدارة الجلسات والسياق:</b>\n"
        "• <code>/new</code> - بدء جلسة جديدة كلياً وتصفير سياق المحادثة.\n"
        "• <code>/sessions</code> - استعراض الجلسات السابقة والتبديل بينها أو حذفها.\n\n"
        "🔑 <b>مفاتيح API:</b>\n"
        "• <code>/apikey &lt;key&gt;</code> - تعيين مفتاح Google Gemini خاص بك لتجنب نفاد الحصة.\n"
        "• <code>/apikey clear</code> - إزالة مفتاحك الخاص والعودة للمفتاح الافتراضي للبوت.\n\n"
        "📁 <b>المستندات والوسائط:</b>\n"
        "• أرسل أي ملف (<code>.pdf</code>, <code>.md</code>, <code>.py</code>, <code>.json</code>) مع تعليق تريده وسيقوم Jules بفحصه وتقديم الشرح والحلول البرمجية داخل المحادثة.\n"
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
    current_model = user.get("selected_model", "flash") if user else "flash"

    text = (
        "⚡ <b>اختر نموذج الذكاء الاصطناعي لوكيل Jules:</b>\n\n"
        f"1. ⚡ <b>{config.MODEL_FLASH_NAME}:</b>\n"
        "• استجابة فورية فائقة السرعة، ممتاز للمهام اليومية والأسئلة السريعة والتحليلات الخفيفة.\n\n"
        f"2. 🧠 <b>{config.MODEL_PRO_NAME}:</b>\n"
        "• عمق تحليلي استثنائي، تفكير منطقي متقدم لحل أعقد المعضلات المعمارية والبرمجية."
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
            f"🔑 <b>إدارة مفتاح Google Gemini API:</b>\n"
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
        await update.message.reply_text("✅ تم حفظ مفتاح Google API الخاص بك بنجاح! سيتم توجيه جميع طلباتك باستخدامه.")


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

    # Permission check for chat
    allowed, reason = await PermissionService.check_access(user.id)
    if not allowed:
        await update.message.reply_text(reason)
        return

    # Update user record
    await UserRepository.get_or_create(user.id, user.username, user.first_name)

    # Active session
    session = await SessionRepository.get_active_session(user.id)

    # Send live typing action indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # Generate answer with Jules
    response_text = await JulesService.generate_response(
        user_id=user.id,
        session_id=session["session_id"],
        user_prompt=text
    )

    # Send formatted response
    await FormatService.send_smart_message(
        bot=context.bot,
        chat_id=update.effective_chat.id,
        raw_markdown_text=response_text,
        reply_to_message_id=update.message.message_id
    )


async def photo_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming photos for visual and architectural analysis."""
    user = update.effective_user

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

    await FormatService.send_smart_message(
        bot=context.bot,
        chat_id=update.effective_chat.id,
        raw_markdown_text=response_text,
        reply_to_message_id=update.message.message_id
    )


async def document_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming code documents, markdown, and PDF files."""
    user = update.effective_user

    allowed, reason = await PermissionService.check_access(user.id, config.FEATURE_UPLOAD_FILES)
    if not allowed:
        await update.message.reply_text(reason)
        return

    doc = update.message.document
    file_name = doc.file_name or "document"
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

    caption = update.message.caption or f"يرجى فحص وتحليل الملف ({file_name}) وتقديم مراجعة برمجية شاملة له."

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    response_text = await JulesService.generate_response(
        user_id=user.id,
        session_id=session["session_id"],
        user_prompt=caption,
        media_bytes=doc_bytes,
        mime_type=mime_type,
        file_name=file_name
    )

    await FormatService.send_smart_message(
        bot=context.bot,
        chat_id=update.effective_chat.id,
        raw_markdown_text=response_text,
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
        if model_target == "pro":
            allowed_pro, reason_pro = await PermissionService.check_access(user_id, config.FEATURE_USE_PRO)
            if not allowed_pro:
                await query.answer(reason_pro, show_alert=True)
                return

        await UserRepository.update_model(user_id, model_target)
        display_name = config.MODEL_PRO_NAME if model_target == "pro" else config.MODEL_FLASH_NAME

        await query.edit_message_reply_markup(reply_markup=get_model_switch_keyboard(model_target))
        await query.message.reply_text(f"✅ تم تغيير النموذج بنجاح إلى: <b>{display_name}</b>", parse_mode=ParseMode.HTML)

    elif data.startswith("user:select_session:"):
        session_id = data.split(":")[2]
        success = await SessionRepository.set_active_session(user_id, session_id)
        if success:
            sessions = await SessionRepository.list_user_sessions(user_id, limit=8)
            await query.edit_message_reply_markup(reply_markup=get_sessions_keyboard(sessions, session_id))
            await query.message.reply_text(f"🔄 تم التبديل إلى الجلسة <code>#{session_id}</code> واستئناف سياقها.", parse_mode=ParseMode.HTML)

    elif data.startswith("user:delete_session:"):
        session_id = data.split(":")[2]
        await SessionRepository.delete_session(session_id, user_id)
        sessions = await SessionRepository.list_user_sessions(user_id, limit=8)
        active = await SessionRepository.get_active_session(user_id)
        active_id = active["session_id"] if active else ""

        if sessions:
            await query.edit_message_reply_markup(reply_markup=get_sessions_keyboard(sessions, active_id))
        else:
            await query.edit_message_text("📂 تم حذف جميع جلساتك السابقة.")

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

    app.add_handler(CallbackQueryHandler(user_callback_handler, pattern=r"^user:"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_message_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, document_message_handler))

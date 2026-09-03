"""
Administrative Dashboard and Granular Permission Handlers.
Provides /admin command, interactive inline menus, maintenance toggle,
global feature flags, user lookup, banning, whitelisting, and per-user permission overrides.
"""

import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes
)
import config
from database.repositories import (
    PermissionRepository,
    SessionRepository,
    SettingsRepository,
    UserRepository
)
from services.permission_service import PermissionService
from utils.keyboards import (
    get_admin_features_keyboard,
    get_admin_main_keyboard,
    get_admin_user_manage_keyboard,
    get_admin_users_menu_keyboard,
    get_user_permissions_keyboard
)

logger = logging.getLogger(__name__)

async def render_admin_dashboard_text() -> str:
    """Generates the text for the main admin control panel."""
    maintenance = await SettingsRepository.is_maintenance_mode()
    whitelist = await SettingsRepository.is_whitelist_mode()
    user_count = await UserRepository.count_users()
    session_count = await SessionRepository.count_sessions()
    msg_count = await SessionRepository.count_messages()

    m_status = "🔴 مفعل (البوت مغلق للعامة)" if maintenance else "🟢 معطل (البوت متاح للجميع)"
    w_status = "🔒 مفعل (للمصرح لهم فقط)" if whitelist else "🌐 معطل (الوصول عام)"

    text = (
        "👑 <b>لوحة تحكم إدارة بوت Jules AI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚦 <b>وضع الصيانة:</b> {m_status}\n"
        f"🛡️ <b>وضع القائمة البيضاء:</b> {w_status}\n\n"
        "📊 <b>إحصائيات النظام السريعة:</b>\n"
        f"• إجمالي المستخدمين: <code>{user_count}</code>\n"
        f"• الجلسات النشطة: <code>{session_count}</code>\n"
        f"• الرسائل المتبادلة: <code>{msg_count}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "اختر من الأزرار أدناه للتحكم الشامل في البوت والصلاحيات:"
    )
    return text


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point for /admin command."""
    user_id = update.effective_user.id
    if not PermissionService.is_admin(user_id):
        await update.message.reply_text("⛔ عذراً، هذا الأمر مخصص لمديري النظام فقط.")
        return

    text = await render_admin_dashboard_text()
    maintenance = await SettingsRepository.is_maintenance_mode()
    whitelist = await SettingsRepository.is_whitelist_mode()

    await update.message.reply_text(
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_main_keyboard(maintenance, whitelist)
    )


async def search_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command: /search <user_id or username> to manage a specific user."""
    user_id = update.effective_user.id
    if not PermissionService.is_admin(user_id):
        return

    if not context.args:
        await update.message.reply_text(
            "ℹ️ <b>طريقة استخدام أمر البحث:</b>\n"
            "<code>/search &lt;User_ID أو Username&gt;</code>\n\n"
            "مثال: <code>/search 123456789</code> أو <code>/search @johndoe</code>",
            parse_mode=ParseMode.HTML
        )
        return

    query = context.args[0].strip()
    target_user = None

    if query.lstrip("-").isdigit():
        target_user = await UserRepository.get_by_id(int(query))
    if not target_user:
        target_user = await UserRepository.get_by_username(query)

    if not target_user:
        await update.message.reply_text(f"❌ لم يتم العثور على مستخدم بالمعرف أو الاسم: <code>{query}</code>", parse_mode=ParseMode.HTML)
        return

    await show_user_management(update.effective_chat.id, target_user, context)


async def show_user_management(chat_id: int, target_user: dict, context: ContextTypes.DEFAULT_TYPE, message_id: int = None) -> None:
    """Displays user details and management buttons."""
    t_id = target_user["user_id"]
    t_name = target_user.get("first_name") or "مستخدم"
    t_username = f"@{target_user['username']}" if target_user.get("username") else "بدون معرف"
    is_banned = bool(target_user.get("is_banned"))
    is_whitelisted = bool(target_user.get("is_whitelisted"))
    model = target_user.get("selected_model", "flash").upper()
    has_custom_key = "✅ نعم" if target_user.get("custom_api_key") else "❌ لا"

    # Effective permissions summary
    effective_perms = await PermissionService.get_user_effective_permissions(t_id)
    perms_summary = "\n".join([
        f"  • {config.FEATURE_NAMES.get(k, k)}: {'🟢 مسموح' if v else '🔴 ممنوع'}"
        for k, v in effective_perms.items()
    ])

    text = (
        f"👤 <b>ملف إدارة المستخدم: {t_name}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 المعرف: <code>{t_id}</code>\n"
        f"🏷️ اليوزرنيم: {t_username}\n"
        f"⚡ النموذج المختار: <code>{model}</code>\n"
        f"🔑 مفتاح مخصص: {has_custom_key}\n"
        f"🚫 حالة الحظر: {'🔴 محظور' if is_banned else '🟢 نشط'}\n"
        f"⭐ القائمة البيضاء: {'✅ نعم' if is_whitelisted else '❌ لا'}\n\n"
        f"🎯 <b>الصلاحيات الفعلية المطبقة:</b>\n{perms_summary}\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )

    markup = get_admin_user_manage_keyboard(t_id, is_banned, is_whitelisted)

    if message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=markup
            )
            return
        except Exception:
            pass

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=markup
    )


async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles all admin callback queries."""
    query = update.callback_query
    user_id = query.from_user.id

    if not PermissionService.is_admin(user_id):
        await query.answer("⛔ ليس لديك صلاحية أدمن.", show_alert=True)
        return

    data = query.data
    await query.answer()

    if data == "admin:main_menu" or data == "admin:refresh":
        text = await render_admin_dashboard_text()
        maintenance = await SettingsRepository.is_maintenance_mode()
        whitelist = await SettingsRepository.is_whitelist_mode()
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_main_keyboard(maintenance, whitelist)
        )

    elif data == "admin:close":
        await query.delete_message()

    elif data == "admin:toggle_maintenance":
        current = await SettingsRepository.is_maintenance_mode()
        await SettingsRepository.set_maintenance_mode(not current)
        text = await render_admin_dashboard_text()
        whitelist = await SettingsRepository.is_whitelist_mode()
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_main_keyboard(not current, whitelist)
        )

    elif data == "admin:toggle_whitelist":
        current = await SettingsRepository.is_whitelist_mode()
        await SettingsRepository.set_whitelist_mode(not current)
        text = await render_admin_dashboard_text()
        maintenance = await SettingsRepository.is_maintenance_mode()
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_main_keyboard(maintenance, not current)
        )

    elif data == "admin:features_menu":
        features_state = {}
        for feat in config.ALL_FEATURES:
            features_state[feat] = await SettingsRepository.get_feature_default(feat)

        text = (
            "⚙️ <b>التحكم في الميزات العامة (Global Feature Toggles)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "اضغط على أي ميزة لتفعيلها أو تعطيلها لجميع المستخدمين افتراضياً:\n"
            "<i>(المستخدمون الذين لديهم استثناء خاص لن يتأثروا بتغيير هذا الإعداد)</i>"
        )
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_features_keyboard(features_state)
        )

    elif data.startswith("admin:toggle_feature:"):
        feature = data.split(":", 2)[2]
        current_state = await SettingsRepository.get_feature_default(feature)
        await SettingsRepository.set_feature_default(feature, not current_state)

        features_state = {}
        for feat in config.ALL_FEATURES:
            features_state[feat] = await SettingsRepository.get_feature_default(feat)

        await query.edit_message_reply_markup(
            reply_markup=get_admin_features_keyboard(features_state)
        )

    elif data == "admin:users_menu":
        users = await UserRepository.list_users(limit=8)
        text = (
            "👥 <b>إدارة المستخدمين والصلاحيات</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "اختر مستخدماً من القائمة الأخيرة أدناه أو ابحث بالمعرف:\n"
            "• 🚫: محظور | ⭐: قائمة بيضاء | 👑: مسؤول"
        )
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_users_menu_keyboard(users)
        )

    elif data == "admin:prompt_search_user":
        await query.edit_message_text(
            "🔍 <b>للبحث عن أي مستخدم:</b>\n\n"
            "أرسل الأمر في المحادثة مباشرة:\n"
            "<code>/search &lt;المعرف أو اسم المستخدم&gt;</code>\n\n"
            "مثال: <code>/search 12345678</code> أو <code>/search @username</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_users_menu_keyboard()
        )

    elif data.startswith("admin:view_user:"):
        target_id = int(data.split(":")[2])
        target_user = await UserRepository.get_by_id(target_id)
        if target_user:
            await show_user_management(query.message.chat_id, target_user, context, query.message.message_id)

    elif data.startswith("admin:toggle_ban:"):
        target_id = int(data.split(":")[2])
        target_user = await UserRepository.get_by_id(target_id)
        if target_user:
            new_ban_state = not bool(target_user.get("is_banned"))
            await UserRepository.set_banned(target_id, new_ban_state)
            target_user = await UserRepository.get_by_id(target_id)
            await show_user_management(query.message.chat_id, target_user, context, query.message.message_id)

    elif data.startswith("admin:toggle_wl_user:"):
        target_id = int(data.split(":")[2])
        target_user = await UserRepository.get_by_id(target_id)
        if target_user:
            new_wl_state = not bool(target_user.get("is_whitelisted"))
            await UserRepository.set_whitelisted(target_id, new_wl_state)
            target_user = await UserRepository.get_by_id(target_id)
            await show_user_management(query.message.chat_id, target_user, context, query.message.message_id)

    elif data.startswith("admin:user_perms:"):
        target_id = int(data.split(":")[2])
        overrides = await PermissionRepository.get_all_user_overrides(target_id)
        global_defaults = {f: await SettingsRepository.get_feature_default(f) for f in config.ALL_FEATURES}

        text = (
            f"🎯 <b>تخصيص الصلاحيات الفردية للمستخدم (ID: <code>{target_id}</code>)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "اضغط على أي ميزة للتبديل بين الحالات الثلاث بالتتابع:\n"
            "1. ⚪ <b>يتبع النظام</b> (يرجع للإعداد العام الافتراضي)\n"
            "2. 🟢 <b>مسموح خصيصاً</b> (منح الميزة حتى لو عطلها الأدمن عاماً)\n"
            "3. 🔴 <b>ممنوع خصيصاً</b> (منع الميزة حتى لو فتحها الأدمن عاماً)\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_user_permissions_keyboard(target_id, overrides, global_defaults)
        )

    elif data.startswith("admin:cycle_perm:"):
        _, _, target_id_str, feature = data.split(":")
        target_id = int(target_id_str)
        current_override = await PermissionRepository.get_user_override(target_id, feature)

        # Cycle: None -> True -> False -> None
        if current_override is None:
            new_override = True
        elif current_override is True:
            new_override = False
        else:
            new_override = None

        await PermissionRepository.set_user_override(target_id, feature, new_override)

        overrides = await PermissionRepository.get_all_user_overrides(target_id)
        global_defaults = {f: await SettingsRepository.get_feature_default(f) for f in config.ALL_FEATURES}

        await query.edit_message_reply_markup(
            reply_markup=get_user_permissions_keyboard(target_id, overrides, global_defaults)
        )

    elif data == "admin:stats":
        user_count = await UserRepository.count_users()
        banned_count = await UserRepository.count_banned()
        wl_count = await UserRepository.count_whitelisted()
        session_count = await SessionRepository.count_sessions()
        msg_count = await SessionRepository.count_messages()

        text = (
            "📊 <b>إحصائيات النظام الشاملة</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 إجمالي المستخدمين المسجلين: <code>{user_count}</code>\n"
            f"🚫 المستخدمون المحظورون: <code>{banned_count}</code>\n"
            f"⭐ مستخدمو القائمة البيضاء: <code>{wl_count}</code>\n"
            f"📂 إجمالي الجلسات المنشأة: <code>{session_count}</code>\n"
            f"💬 إجمالي الرسائل المحفوظة: <code>{msg_count}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_main_keyboard(
                await SettingsRepository.is_maintenance_mode(),
                await SettingsRepository.is_whitelist_mode()
            )
        )

    elif data == "admin:guide":
        await query.edit_message_text(
            text=get_admin_guide_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_main_keyboard(
                await SettingsRepository.is_maintenance_mode(),
                await SettingsRepository.is_whitelist_mode()
            )
        )


def get_admin_guide_text() -> str:
    """Returns the comprehensive admin guide text."""
    return (
        "📖 <b>دليل الإدارة الشامل (Admin Guide)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👑 <b>القاعدة الذهبية:</b>\n"
        "• تيليجرام لكل شيء (المفاتيح، الصلاحيات، الرقابة، النماذج، المستودعات).\n"
        "• ريندر (Render) فقط للمتغيرات البيئية الأساسية عند الإقلاع الأول.\n\n"
        "⚡ <b>أوامر الإدارة المباشرة:</b>\n"
        "• <code>/admin</code> - فتح لوحة التحكم التفاعلية الشاملة.\n"
        "• <code>/search &lt;ID/@username&gt;</code> - البحث عن مستخدم وإدارة صلاحياته وحظره.\n"
        "• <code>/adminguide</code> - فتح هذا الدليل الإرشادي في أي وقت.\n\n"
        "🛡️ <b>أنظمة الأمان والتحكم:</b>\n"
        "1. <b>وضع الصيانة (Maintenance Mode):</b>\n"
        "   إغلاق البوت فوراً أمام كافة المستخدمين وحصره للأدمن فقط لحين انتهاء التحديثات.\n"
        "2. <b>وضع القائمة البيضاء (Whitelist Mode):</b>\n"
        "   قصر استخدام البوت فقط على الأشخاص المضافين يدوياً في القائمة البيضاء.\n"
        "3. <b>التحكم في الميزات العامة (Global Features):</b>\n"
        "   تعطيل أو تفعيل أي ميزة برمجية للنظام ككل بضغطة زر (تبديل النماذج، الوكيل المستقل، رفع الملفات، إنشاء الجلسات، مفاتيح API).\n"
        "4. <b>التخصيص الفردي ثلاثي الحالات (Per-User Overrides):</b>\n"
        "   • ⚪ <b>يتبع النظام:</b> يعود للإعداد الافتراضي العام للبوت.\n"
        "   • 🟢 <b>مسموح خصيصاً:</b> يمنح المستخدم الميزة حتى لو عطلها الأدمن عاماً.\n"
        "   • 🔴 <b>ممنوع خصيصاً:</b> يحجب الميزة عن المستخدم تحديداً دون التأثير على البقية.\n\n"
        "🛠️ <b>النماذج ووكيل Jules:</b>\n"
        "• نماذج Jules الرسمية: <code>gemini-3.6-flash</code> و <code>gemini-3.1-pro</code>.\n"
        "• نماذج Google AI Studio: من <code>gemini-3.1-pro</code> وحتى <code>gemini-3.8-flash</code>.\n"
        "• وضع المستودعات: <code>/repos</code> لاختيار المشروع، أو <code>/repos none</code> للمحادثة المباشرة وتصفح الويب دون مستودع.\n"
        "• متابعة المهام: <code>/tasks</code> لمتابعة المهام، الرد التفاعلي، اعتماد الخطط، وتنزيل السكرينات والمخرجات فوراً.\n\n"
        "📝 <b>نظام الرتش (Rich Messages 2026):</b>\n"
        "• يدعم البوت استقبال وتوليد النصوص المنسقة، إصلاح الجداول المتكسرة، ودعم اتجاه النص العربي RTL، ومحاذاة الأكواد البرمجية.\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )


async def adminguide_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /adminguide command."""
    user_id = update.effective_user.id
    if not PermissionService.is_admin(user_id):
        await update.message.reply_text("⛔ عذراً، هذا الأمر مخصص لمديري النظام فقط.")
        return

    await update.message.reply_text(
        text=get_admin_guide_text(),
        parse_mode=ParseMode.HTML
    )


def register_admin_handlers(app: Application) -> None:
    """Registers all admin-related command and callback handlers."""
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("search", search_user_command))
    app.add_handler(CommandHandler("adminguide", adminguide_command))
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern=r"^admin:"))

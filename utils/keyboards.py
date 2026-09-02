"""
Keyboards Module for Jules Telegram Bot.
Provides interactive Inline & Reply Keyboards for users and the admin control dashboard.
"""

from typing import Dict, List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
import config

def get_main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Generates the main persistent reply keyboard for quick access."""
    buttons = [
        [KeyboardButton("⚡ تبديل النموذج"), KeyboardButton("💬 جلسة جديدة")],
        [KeyboardButton("📂 جلساتي"), KeyboardButton("🔑 مفتاح API")],
        [KeyboardButton("ℹ️ المساعدة والمعلومات")]
    ]
    if is_admin:
        buttons.append([KeyboardButton("🛠️ لوحة تحكم الأدمن (/admin)")])

    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def get_model_switch_keyboard(current_model: str) -> InlineKeyboardMarkup:
    """Inline keyboard for switching between Gemini 3.6 Flash and Gemini 3.1 Pro."""
    is_flash = (current_model == "flash")
    is_pro = (current_model == "pro")

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if is_flash else ''}⚡ {config.MODEL_FLASH_NAME}",
                callback_data="user:set_model:flash"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if is_pro else ''}🧠 {config.MODEL_PRO_NAME}",
                callback_data="user:set_model:pro"
            )
        ],
        [
            InlineKeyboardButton(text="❌ إغلاق", callback_data="user:close")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_sessions_keyboard(sessions: List[dict], active_session_id: str) -> InlineKeyboardMarkup:
    """Inline keyboard for browsing, switching, and deleting conversation sessions."""
    keyboard = []

    for s in sessions:
        s_id = s["session_id"]
        is_active = (s_id == active_session_id)
        prefix = "✅ " if is_active else "💬 "
        title = s.get("title") or f"جلسة #{s_id}"

        # Truncate title if too long
        display_title = (title[:22] + "..") if len(title) > 24 else title

        row = [
            InlineKeyboardButton(
                text=f"{prefix}{display_title}",
                callback_data=f"user:select_session:{s_id}"
            ),
            InlineKeyboardButton(
                text="🗑️",
                callback_data=f"user:delete_session:{s_id}"
            )
        ]
        keyboard.append(row)

    # Bottom action buttons
    keyboard.append([
        InlineKeyboardButton(text="➕ بدء جلسة جديدة", callback_data="user:new_session"),
        InlineKeyboardButton(text="❌ إغلاق", callback_data="user:close")
    ])

    return InlineKeyboardMarkup(keyboard)


# =========================================================================
# Admin Control Panel Keyboards
# =========================================================================

def get_admin_main_keyboard(maintenance_on: bool, whitelist_on: bool) -> InlineKeyboardMarkup:
    """Main administrative dashboard keyboard."""
    m_icon = "🔴 مفعل" if maintenance_on else "🟢 معطل"
    w_icon = "🔒 مقتصر" if whitelist_on else "🌐 عام للجميع"

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"🛠️ وضع الصيانة: {m_icon}",
                callback_data="admin:toggle_maintenance"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🛡️ وضع القائمة البيضاء: {w_icon}",
                callback_data="admin:toggle_whitelist"
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ التحكم في الميزات العامة",
                callback_data="admin:features_menu"
            )
        ],
        [
            InlineKeyboardButton(
                text="👥 إدارة المستخدمين والصلاحيات",
                callback_data="admin:users_menu"
            )
        ],
        [
            InlineKeyboardButton(text="📊 إحصائيات البوت", callback_data="admin:stats"),
            InlineKeyboardButton(text="🔄 تحديث", callback_data="admin:refresh")
        ],
        [
            InlineKeyboardButton(text="❌ إغلاق اللوحة", callback_data="admin:close")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_features_keyboard(features_state: Dict[str, bool]) -> InlineKeyboardMarkup:
    """Toggles for all system features globally."""
    keyboard = []
    for feat in config.ALL_FEATURES:
        state = features_state.get(feat, True)
        icon = "✅ مفعلة" if state else "❌ معطلة"
        name = config.FEATURE_NAMES.get(feat, feat)

        keyboard.append([
            InlineKeyboardButton(
                text=f"{icon} | {name}",
                callback_data=f"admin:toggle_feature:{feat}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(text="🔙 العودة للوحة الرئيسية", callback_data="admin:main_menu")
    ])
    return InlineKeyboardMarkup(keyboard)


def get_admin_users_menu_keyboard(users: List[dict] = None) -> InlineKeyboardMarkup:
    """Users management menu keyboard."""
    keyboard = []

    if users:
        for u in users:
            name = u.get("first_name") or u.get("username") or str(u["user_id"])
            status_flags = []
            if u.get("is_banned"):
                status_flags.append("🚫")
            if u.get("is_whitelisted"):
                status_flags.append("⭐")
            if u.get("is_admin"):
                status_flags.append("👑")

            flag_str = "".join(status_flags) + " " if status_flags else ""
            display = f"{flag_str}{name} ({u['user_id']})"
            keyboard.append([
                InlineKeyboardButton(
                    text=display[:30],
                    callback_data=f"admin:view_user:{u['user_id']}"
                )
            ])

    keyboard.append([
        InlineKeyboardButton(text="🔍 البحث بمعرف ID أو Username", callback_data="admin:prompt_search_user")
    ])
    keyboard.append([
        InlineKeyboardButton(text="🔙 العودة للوحة الرئيسية", callback_data="admin:main_menu")
    ])
    return InlineKeyboardMarkup(keyboard)


def get_admin_user_manage_keyboard(
    user_id: int,
    is_banned: bool,
    is_whitelisted: bool
) -> InlineKeyboardMarkup:
    """Controls for a single specific user."""
    ban_text = "🔓 إلغاء الحظر" if is_banned else "🚫 حظر المستخدم"
    whitelist_text = "➖ إزالة من البيضاء" if is_whitelisted else "⭐ إضافة للبيضاء"

    keyboard = [
        [
            InlineKeyboardButton(text=ban_text, callback_data=f"admin:toggle_ban:{user_id}"),
            InlineKeyboardButton(text=whitelist_text, callback_data=f"admin:toggle_wl_user:{user_id}")
        ],
        [
            InlineKeyboardButton(
                text="🎯 تخصيص الصلاحيات الفردية (Granular)",
                callback_data=f"admin:user_perms:{user_id}"
            )
        ],
        [
            InlineKeyboardButton(text="🔙 قائمة المستخدمين", callback_data="admin:users_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_user_permissions_keyboard(
    user_id: int,
    user_overrides: Dict[str, bool],
    global_defaults: Dict[str, bool]
) -> InlineKeyboardMarkup:
    """
    Granular permission customization for a single user.
    Cycles through 3 states:
    1. None (⚪ يتبع النظام)
    2. True (🟢 مسموح خصيصاً)
    3. False (🔴 محظور خصيصاً)
    """
    keyboard = []

    for feat in config.ALL_FEATURES:
        feat_name = config.FEATURE_NAMES.get(feat, feat)
        override = user_overrides.get(feat)

        if override is True:
            badge = "🟢 مسموح خصيصاً"
        elif override is False:
            badge = "🔴 ممنوع خصيصاً"
        else:
            default_val = global_defaults.get(feat, True)
            badge = f"⚪ يتبع النظام ({'مسموح' if default_val else 'معطل'})"

        button_text = f"{feat_name}: {badge}"
        keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"admin:cycle_perm:{user_id}:{feat}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(text="🔙 العودة لبيانات المستخدم", callback_data=f"admin:view_user:{user_id}")
    ])
    return InlineKeyboardMarkup(keyboard)

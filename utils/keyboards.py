"""
Keyboards Module for Jules Telegram Bot.
Provides interactive Inline & Reply Keyboards for users and the admin control dashboard.
"""

from typing import Dict, List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
import config

def get_main_keyboard(is_admin: bool = False, has_custom_key: bool = False) -> ReplyKeyboardMarkup:
    """Generates the main persistent reply keyboard for quick access."""
    if is_admin:
        buttons = [
            [KeyboardButton("💬 جلسة جديدة"), KeyboardButton("📋 مهامي السابقة")],
            [KeyboardButton("⚡ تبديل النموذج"), KeyboardButton("🔑 مفتاح API")],
            [KeyboardButton("📁 المستودعات البرمجية"), KeyboardButton("🛠️ لوحة تحكم الأدمن (/admin)")]
        ]
    else:
        buttons = [
            [KeyboardButton("💬 جلسة جديدة"), KeyboardButton("📋 مهامي السابقة")]
        ]

    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def get_model_switch_keyboard(current_model: str) -> InlineKeyboardMarkup:
    """
    Inline keyboard for selecting exact canonical Google models:
    - Jules API models: gemini-3.6-flash, gemini-3.1-pro
    - Google AI Studio models: gemini-3.1-pro, gemini-3.1-flash, gemini-3.5-flash,
      gemini-3.6-flash, gemini-3.7-flash, gemini-3.8-flash
    """
    m = (current_model or "").strip()

    def _mark(full_id: str) -> str:
        return f"✅ {full_id}" if m == full_id else full_id

    keyboard = [
        # Autonomous Agent Models (gemini-3.6-flash and gemini-3.1-pro)
        [
            InlineKeyboardButton(text="── 🛠️ نماذج محرك الوكيل المتقدم ──", callback_data="user:noop")
        ],
        [
            InlineKeyboardButton(
                text=_mark("gemini-3.6-flash"),
                callback_data="user:set_model:gemini-3.6-flash"
            ),
            InlineKeyboardButton(
                text=_mark("gemini-3.1-pro"),
                callback_data="user:set_model:gemini-3.1-pro"
            )
        ],
        # Google AI Studio Models
        [
            InlineKeyboardButton(text="── ⚡ نماذج Google AI Studio ──", callback_data="user:noop")
        ],
        [
            InlineKeyboardButton(
                text=_mark("gemini-3.1-pro"),
                callback_data="user:set_model:gemini-3.1-pro"
            ),
            InlineKeyboardButton(
                text=_mark("gemini-3.1-flash"),
                callback_data="user:set_model:gemini-3.1-flash"
            )
        ],
        [
            InlineKeyboardButton(
                text=_mark("gemini-3.5-flash"),
                callback_data="user:set_model:gemini-3.5-flash"
            ),
            InlineKeyboardButton(
                text=_mark("gemini-3.6-flash"),
                callback_data="user:set_model:gemini-3.6-flash"
            )
        ],
        [
            InlineKeyboardButton(
                text=_mark("gemini-3.7-flash"),
                callback_data="user:set_model:gemini-3.7-flash"
            ),
            InlineKeyboardButton(
                text=_mark("gemini-3.8-flash"),
                callback_data="user:set_model:gemini-3.8-flash"
            )
        ],
        # Repo Agent Mode
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if m == 'agent' else ''}🛠️ وكيل هندسة البرمجيات المستقل",
                callback_data="user:set_model:agent"
            )
        ],
        [
            InlineKeyboardButton(text="❌ إغلاق", callback_data="user:close")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_apikey_dashboard_keyboard(has_gemini: bool, has_jules: bool, is_admin: bool = False) -> InlineKeyboardMarkup:
    """Inline keyboard for API Key & Model management directly from Telegram."""
    gemini_status = "✅ مسجل" if has_gemini else "➕ تعيين"
    jules_status = "✅ مسجل" if has_jules else "➕ تعيين"

    keyboard = [
        [
            InlineKeyboardButton(f"⚡ مفتاح Studio ({gemini_status})", callback_data="user:set_key_prompt:gemini"),
            InlineKeyboardButton(f"🛠️ مفتاح الوكيل ({jules_status})", callback_data="user:set_key_prompt:jules"),
        ],
        [
            InlineKeyboardButton("🎯 تحديد النموذج / الوكيل النشط", callback_data="user:open_model_menu"),
        ],
    ]

    if is_admin:
        keyboard.append([
            InlineKeyboardButton("👑 تعيين مفتاح عام لكافة مستخدمي البوت", callback_data="admin:set_sys_key_prompt")
        ])

    keyboard.append([
        InlineKeyboardButton("🗑️ مسح مفاتيحي الخاصة", callback_data="user:clear_keys"),
        InlineKeyboardButton("❌ إغلاق", callback_data="user:close")
    ])

    return InlineKeyboardMarkup(keyboard)


def get_sources_keyboard(sources: List[dict], selected_source: str = "") -> InlineKeyboardMarkup:
    """Inline keyboard listing connected GitHub repositories from Jules API."""
    keyboard = []

    # Option to use Jules without a repo (Chat / Direct Discussion mode)
    is_none_selected = not selected_source or selected_source == "none"
    none_prefix = "⭐ " if is_none_selected else "💬 "
    keyboard.append([
        InlineKeyboardButton(
            text=f"{none_prefix}بدون مستودع (محادثة شات مباشرة فقط)",
            callback_data="user:sel_src:none"
        )
    ])

    for src in sources:
        raw_name = src.get("name", "")
        # format: sources/github-username-repo
        display_name = raw_name.replace("sources/github-", "").replace("sources/", "")
        gh_info = src.get("githubRepo", {})
        if gh_info.get("owner") and gh_info.get("repo"):
            display_name = f"{gh_info['owner']}/{gh_info['repo']}"

        is_selected = (raw_name == selected_source)
        prefix = "⭐ " if is_selected else "📁 "

        keyboard.append([
            InlineKeyboardButton(
                text=f"{prefix}{display_name}",
                callback_data=f"user:sel_src:{raw_name}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(text="🔄 تحديث القائمة", callback_data="user:refresh_sources"),
        InlineKeyboardButton(text="❌ إغلاق", callback_data="user:close")
    ])
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
                text="🎯 تحديد النموذج العام للنظام",
                callback_data="admin:sys_model_menu"
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
                text="👥 إدارة المستخدمين والصلاحيات والمفاتيح",
                callback_data="admin:users_menu"
            )
        ],
        [
            InlineKeyboardButton(text="📊 إحصائيات البوت", callback_data="admin:stats"),
            InlineKeyboardButton(text="🔄 تحديث", callback_data="admin:refresh")
        ],
        [
            InlineKeyboardButton(text="📖 دليل الأدمن الشامل", callback_data="admin:guide"),
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
    is_whitelisted: bool,
    has_custom_key: bool = False
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
                text="🎯 تخصيص النموذج لهذا المستخدم",
                callback_data=f"admin:user_model_menu:{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔑 تعيين مفتاح API له",
                callback_data=f"admin:set_user_key:{user_id}"
            ),
            InlineKeyboardButton(
                text="🗑️ مسح مفتاحه",
                callback_data=f"admin:clear_user_key:{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ تخصيص الصلاحيات الفردية (Granular)",
                callback_data=f"admin:user_perms:{user_id}"
            )
        ],
        [
            InlineKeyboardButton(text="🔙 قائمة المستخدمين", callback_data="admin:users_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_select_model_keyboard(target: str, current_model: str = "") -> InlineKeyboardMarkup:
    """Inline keyboard for admin to select model for system or a specific user."""
    models = [
        ("gemini-3.6-flash", "⚡ gemini-3.6-flash"),
        ("gemini-3.1-pro", "💎 gemini-3.1-pro"),
        ("gemini-3.1-flash", "⚡ gemini-3.1-flash"),
        ("gemini-3.5-flash", "⚡ gemini-3.5-flash"),
        ("gemini-3.7-flash", "⚡ gemini-3.7-flash"),
        ("gemini-3.8-flash", "⚡ gemini-3.8-flash"),
        ("agent", "🛠️ وكيل هندسة البرمجيات المستقل")
    ]
    keyboard = []
    for model_id, label in models:
        prefix = "✅ " if current_model == model_id else ""
        if target == "system":
            cb = f"admin:set_sys_model:{model_id}"
        else:
            cb = f"admin:set_user_model:{target}:{model_id}"
        keyboard.append([InlineKeyboardButton(text=f"{prefix}{label}", callback_data=cb)])

    if target == "system":
        keyboard.append([InlineKeyboardButton(text="🔙 العودة للوحة الرئيسية", callback_data="admin:main_menu")])
    else:
        keyboard.append([InlineKeyboardButton(text="🔙 العودة لبيانات المستخدم", callback_data=f"admin:view_user:{target}")])

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

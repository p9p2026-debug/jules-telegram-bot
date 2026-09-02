"""
Granular Permission Evaluation Service.
Implements the multi-tiered permission engine:
SuperAdmin -> Blacklist -> Maintenance Mode -> Whitelist Mode -> Per-User Overrides -> Global Defaults.
"""

from typing import Dict, Optional, Tuple
import config
from database.repositories import PermissionRepository, SettingsRepository, UserRepository

class PermissionService:
    """Service to evaluate user access rights and feature availability."""

    @staticmethod
    def is_admin(user_id: int) -> bool:
        """Returns True if the user is in ADMIN_IDS."""
        return user_id in config.ADMIN_IDS

    @classmethod
    async def check_access(cls, user_id: int, feature: Optional[str] = None) -> Tuple[bool, str]:
        """
        Evaluates whether a user is authorized to perform an action or use a feature.
        
        Returns:
            Tuple[bool, str]: (is_allowed, denial_reason_or_empty)
        """
        # Tier 1: Super Admin bypass (always allowed)
        if cls.is_admin(user_id):
            return True, ""

        # Retrieve user profile
        user = await UserRepository.get_by_id(user_id)

        # Tier 2: Blacklist (Banned users)
        if user and user.get("is_banned"):
            return False, "🚫 حسابك محظور من استخدام البوت. يرجى التواصل مع إدارة النظام."

        # Tier 3: Global Maintenance Mode
        maintenance = await SettingsRepository.is_maintenance_mode()
        if maintenance:
            return False, "🛠️ البوت حالياً في وضع الصيانة والتحديث المؤقت. نعتذر عن الإزعاج، سنعود قريباً!"

        # Tier 4: Whitelist Mode
        whitelist_mode = await SettingsRepository.is_whitelist_mode()
        if whitelist_mode:
            is_whitelisted = bool(user and user.get("is_whitelisted"))
            if not is_whitelisted:
                return False, "🔒 عذراً، البوت يعمل حالياً في وضع القائمة الخاصة (Whitelist) للمصرح لهم فقط."

        # If no specific feature check requested, base access is granted
        if not feature:
            return True, ""

        feature_display_name = config.FEATURE_NAMES.get(feature, feature)

        # Tier 5: Per-User Feature Overrides (Highest priority for specific features)
        user_override = await PermissionRepository.get_user_override(user_id, feature)
        if user_override is not None:
            if user_override is True:
                return True, ""
            else:
                return False, f"⛔ عذراً، تم تقييد صلاحية ({feature_display_name}) لحسابك من قِبل الإدارة."

        # Tier 6: Global Feature Defaults
        is_globally_enabled = await SettingsRepository.get_feature_default(feature)
        if not is_globally_enabled:
            return False, f"⚠️ ميزة ({feature_display_name}) معطلة حالياً للعامة من قِبل الإدارة."

        return True, ""

    @classmethod
    async def get_user_effective_permissions(cls, user_id: int) -> Dict[str, bool]:
        """
        Calculates the effective permissions for all features for a given user.
        Useful for displaying in user profiles and admin panels.
        """
        is_user_admin = cls.is_admin(user_id)
        if is_user_admin:
            return {feat: True for feat in config.ALL_FEATURES}

        user_overrides = await PermissionRepository.get_all_user_overrides(user_id)
        effective = {}

        for feat in config.ALL_FEATURES:
            if feat in user_overrides:
                effective[feat] = user_overrides[feat]
            else:
                effective[feat] = await SettingsRepository.get_feature_default(feat)

        return effective

"""Handlers module initialization."""
from .admin_handlers import register_admin_handlers
from .user_handlers import register_user_handlers
from .error_handlers import error_handler

__all__ = ["register_admin_handlers", "register_user_handlers", "error_handler"]

"""Services module initialization."""
from .format_service import FormatService
from .permission_service import PermissionService
from .jules_service import JulesService
from .rich_service import (
    RichService,
    ComposeSession,
    ComposeStore,
    detect_direction,
    repair_table_rows,
    ensure_blank_before_table,
    format_tables_for_telegram,
    build_rich_payload
)

__all__ = [
    "FormatService",
    "PermissionService",
    "JulesService",
    "RichService",
    "ComposeSession",
    "ComposeStore",
    "detect_direction",
    "repair_table_rows",
    "ensure_blank_before_table",
    "format_tables_for_telegram",
    "build_rich_payload"
]

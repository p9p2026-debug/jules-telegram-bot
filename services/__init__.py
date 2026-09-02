"""Services module initialization."""
from .format_service import FormatService
from .permission_service import PermissionService
from .jules_service import JulesService
from .jules_api_client import JulesApiClient, JulesApiException
from .task_monitor_service import TaskMonitorService
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
    "JulesApiClient",
    "JulesApiException",
    "TaskMonitorService",
    "RichService",
    "ComposeSession",
    "ComposeStore",
    "detect_direction",
    "repair_table_rows",
    "ensure_blank_before_table",
    "format_tables_for_telegram",
    "build_rich_payload"
]

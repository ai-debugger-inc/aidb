"""AI Debugger (aidb)."""

from .adapters.base import AdapterConfig, DebugAdapter
from .api.api import DebugAPI
from .common.context import AidbContext
from .common.utils import acquire_lock, ensure_ctx
from .dap.client import DAPClient
from .session.adapter_registry import AdapterRegistry
from .session.session_core import Session

__all__ = [
    "AdapterConfig",
    "AdapterRegistry",
    "AidbContext",
    "acquire_lock",
    "DAPClient",
    "DebugAdapter",
    "DebugAPI",
    "ensure_ctx",
    "Session",
]

__version__ = "0.0.9"

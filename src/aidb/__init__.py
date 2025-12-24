"""AI Debugger (aidb)."""

from .adapters.base import AdapterConfig, DebugAdapter
from .common.context import AidbContext
from .common.utils import acquire_lock, ensure_ctx
from .dap.client import DAPClient
from .service import DebugService
from .session import SessionManager
from .session.adapter_registry import AdapterRegistry
from .session.session_core import Session

__all__ = [
    "AdapterConfig",
    "AdapterRegistry",
    "AidbContext",
    "acquire_lock",
    "DAPClient",
    "DebugAdapter",
    "DebugService",
    "ensure_ctx",
    "Session",
    "SessionManager",
]

__version__ = "0.1.0"

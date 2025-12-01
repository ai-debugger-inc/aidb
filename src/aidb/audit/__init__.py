"""Audit logging module for aidb.

Provides comprehensive audit logging for debug operations, API calls, and binary
downloads with minimal performance overhead.
"""

from aidb.audit.events import AuditEvent, AuditLevel
from aidb.audit.logger import AuditLogger, get_audit_logger
from aidb.audit.middleware import audit_operation

__all__ = [
    "AuditEvent",
    "AuditLevel",
    "AuditLogger",
    "get_audit_logger",
    "audit_operation",
]

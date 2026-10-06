"""Multi-account email connectors: config, shared interface, router, providers.

Gmail is a real read-only connector (see gmail.py, authorize.py); IMAP is still a stub
that returns placeholder data.
"""

from riemann.email.base import EmailConnector, Message, MessageSummary
from riemann.email.config import AccountConfig, EmailConfig, load_config
from riemann.email.router import ConnectorRouter

__all__ = [
    "AccountConfig",
    "ConnectorRouter",
    "EmailConfig",
    "EmailConnector",
    "Message",
    "MessageSummary",
    "load_config",
]

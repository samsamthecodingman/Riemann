"""Multi-account email connectors: config, shared interface, router, provider stubs.

Skeleton only: the connectors return placeholder data and never touch the network
or resolve credentials.
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

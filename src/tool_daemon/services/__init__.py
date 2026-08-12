import sys

from tool_daemon.services.base import BaseServiceManager, ServiceConfig
from tool_daemon.services.systemd import SystemdServiceManager
from tool_daemon.services.windows import WindowsServiceManager


def get_service_manager() -> BaseServiceManager:
    match sys.platform:
        case "win32":
            return WindowsServiceManager()
        case "linux":
            return SystemdServiceManager()
        case _:
            return SystemdServiceManager()


__all__ = [
    "BaseServiceManager",
    "ServiceConfig",
    "SystemdServiceManager",
    "WindowsServiceManager",
    "get_service_manager",
]

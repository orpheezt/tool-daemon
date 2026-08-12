from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ServiceConfig:
    name: str
    description: str
    exec_cmd: str
    interval: float
    log_format: str
    log_level: str
    is_user: bool = True
    start_service: bool = True
    force: bool = False
    sandbox: bool = True
    memory_max: str | None = "512M"
    memory_high: str | None = "400M"
    cpu_quota: str | None = "50%"
    tasks_max: int | None = 100
    watchdog_sec: int | None = 30
    sys_user: str = "tool"
    sys_group: str = "tool"
    display_name: str = "Tool Agent Daemon"
    startup: str = "auto"


class BaseServiceManager(ABC):
    @abstractmethod
    def install(self, config: ServiceConfig) -> Path | str:
        """Install background service on target OS platform."""

    @abstractmethod
    def uninstall(
        self, name: str, is_user: bool = True, stop_service: bool = True
    ) -> None:
        """Uninstall background service from target OS platform."""

    @abstractmethod
    def notify(self, state: str) -> bool:
        """Send state notification (e.g. READY=1, WATCHDOG=1, STOPPING=1) to OS init system."""

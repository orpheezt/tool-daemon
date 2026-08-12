from functools import cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DaemonSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TOOL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    agent_id: str = Field(default="tool-daemon")
    poll_interval: float = Field(
        default=5.0,
        description="Sleep interval in seconds between daemon loop passes",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level threshold (DEBUG, INFO, WARNING, ERROR)",
    )
    log_format: str = Field(
        default="json",
        description="Log output formatting (json or text)",
    )
    service_name: str = Field(
        default="tool-daemon",
        description="Name of the background system service unit",
    )
    description: str = Field(
        default="Tool Background Agent Daemon",
        description="Human-readable service description",
    )
    sandbox: bool = Field(
        default=True,
        description="Enable systemd security sandboxing directives",
    )
    memory_max: str | None = Field(
        default="512M",
        description="Maximum memory limit for systemd service",
    )
    memory_high: str | None = Field(
        default="400M",
        description="Memory throttle limit for systemd service",
    )
    cpu_quota: str | None = Field(
        default="50%",
        description="CPU quota percentage for systemd service",
    )
    tasks_max: int | None = Field(
        default=100,
        description="Maximum tasks/threads limit for systemd service",
    )
    watchdog_sec: int | None = Field(
        default=30,
        description="Systemd watchdog interval in seconds (0 to disable)",
    )


@cache
def get_settings() -> DaemonSettings:
    return DaemonSettings()

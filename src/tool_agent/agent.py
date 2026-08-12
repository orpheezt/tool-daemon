import signal
import time
from types import FrameType

from tool_agent.config import DaemonSettings
from tool_agent.logger import setup_logger
from tool_agent.services import get_service_manager


class AgentDaemon:
    def __init__(self, settings: DaemonSettings) -> None:
        self.settings = settings
        self.running = False
        self.cycle_count = 0
        self.service_manager = get_service_manager()
        self.logger = setup_logger(
            name="tool.agent",
            level=self.settings.log_level,
            log_format=self.settings.log_format,
        )
        self._register_signal_handlers()

    def _register_signal_handlers(self) -> None:
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)

    def _handle_shutdown_signal(self, signum: int, _: FrameType | None) -> None:
        signal_name = signal.Signals(signum).name
        self.logger.info(
            f"Received signal {signal_name} ({signum}). Initiating graceful shutdown...",
            extra={"status": "stopping"},
        )
        self.service_manager.notify("STOPPING=1")
        self.running = False

    def execute_agent_job(self) -> None:
        self.cycle_count += 1
        job_id = f"job-{self.cycle_count:04d}"

        self.logger.info(
            f"Executing background agent job #{self.cycle_count}",
            extra={
                "agent_id": self.settings.agent_id,
                "job_id": job_id,
                "status": "completed",
            },
        )

    def run(self) -> None:
        self.running = True
        self.logger.info(
            f"Starting agent daemon (ID: {self.settings.agent_id}, interval: {self.settings.poll_interval}s)",
            extra={
                "agent_id": self.settings.agent_id,
                "status": "running",
            },
        )

        self.service_manager.notify("READY=1")

        while self.running:
            try:
                self.execute_agent_job()
                self.service_manager.notify("WATCHDOG=1")
            except Exception:
                self.logger.exception(
                    "Error during agent job execution",
                    extra={"status": "error"},
                )

            if self.running:
                time.sleep(self.settings.poll_interval)

        self.logger.info(
            "Agent daemon process exited cleanly.",
            extra={"status": "stopped"},
        )

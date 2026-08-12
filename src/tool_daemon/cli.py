import typer
from rich.console import Console

from tool_daemon.agent import AgentDaemon
from tool_daemon.config import get_settings
from tool_daemon.services import ServiceConfig, get_service_manager

app = typer.Typer(
    help="Tool Background Agent Daemon CLI - Manage daemon execution & cross-platform background services.",
)
console = Console()


@app.command()
def run(
    interval: float = typer.Option(
        5.0,
        "--interval",
        "-i",
        help="Poll interval in seconds between daemon passes",
    ),
    log_format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Log format output (json or text)",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--level",
        "-l",
        help="Logging level threshold (DEBUG, INFO, WARNING, ERROR)",
    ),
) -> None:
    """Run the agent daemon in the foreground."""
    settings = get_settings()
    settings.poll_interval = interval
    settings.log_format = log_format
    settings.log_level = log_level
    daemon = AgentDaemon(settings=settings)
    daemon.run()


@app.command()
def install(
    user: bool = typer.Option(
        True,
        "--user/--system",
        help="Install as user service (~/.config/systemd/user/) or system-wide service (/etc/systemd/system/)",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        "-n",
        help="Custom service unit name (defaults to setting service_name)",
    ),
    interval: float = typer.Option(
        5.0,
        "--interval",
        "-i",
        help="Poll interval in seconds between daemon passes",
    ),
    log_format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Log format output (json or text)",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--level",
        "-l",
        help="Logging level threshold (DEBUG, INFO, WARNING, ERROR)",
    ),
    start: bool = typer.Option(
        True,
        "--start/--no-start",
        help="Automatically enable and start service after installation",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing systemd service unit file if present",
    ),
    sandbox: bool = typer.Option(
        True,
        "--sandbox/--no-sandbox",
        help="Enable systemd security sandboxing directives",
    ),
    memory_max: str | None = typer.Option(
        "512M",
        "--memory-max",
        help="Maximum memory limit for systemd service (e.g. 512M, 1G)",
    ),
    memory_high: str | None = typer.Option(
        "400M",
        "--memory-high",
        help="Memory throttle threshold for systemd service (e.g. 400M)",
    ),
    cpu_quota: str | None = typer.Option(
        "50%",
        "--cpu-quota",
        help="CPU quota percentage for systemd service (e.g. 50%)",
    ),
    tasks_max: int | None = typer.Option(
        100,
        "--tasks-max",
        help="Maximum process tasks/threads limit for systemd service",
    ),
    watchdog_sec: int | None = typer.Option(
        30,
        "--watchdog-sec",
        help="Systemd watchdog timeout in seconds (0 to disable)",
    ),
    sys_user: str = typer.Option(
        "tool",
        "--sys-user",
        help="Dedicated unprivileged system user for system-wide service",
    ),
    sys_group: str = typer.Option(
        "tool",
        "--sys-group",
        help="Dedicated unprivileged system group for system-wide service",
    ),
    display_name: str = typer.Option(
        "Tool Agent Daemon",
        "--display-name",
        help="Display name for Windows Service",
    ),
    startup: str = typer.Option(
        "auto",
        "--startup",
        help="Windows Service startup type (auto, demand, disabled)",
    ),
) -> None:
    """Install background service unit for the daemon across platforms (Linux systemd / Windows SCM)."""
    settings = get_settings()
    service_name = name or settings.service_name
    description = settings.description

    config = ServiceConfig(
        name=service_name,
        description=description,
        exec_cmd="",
        interval=interval,
        log_format=log_format,
        log_level=log_level,
        is_user=user,
        start_service=start,
        force=force,
        sandbox=sandbox,
        memory_max=memory_max,
        memory_high=memory_high,
        cpu_quota=cpu_quota,
        tasks_max=tasks_max,
        watchdog_sec=watchdog_sec,
        sys_user=sys_user,
        sys_group=sys_group,
        display_name=display_name,
        startup=startup,
    )

    manager = get_service_manager()
    try:
        manager.install(config)
    except Exception as e:
        console.print(f"[bold red]Installation failed:[/bold red] {e}")
        raise typer.Exit(code=1) from e


@app.command()
def uninstall(
    user: bool = typer.Option(
        True,
        "--user/--system",
        help="Uninstall user service (~/.config/systemd/user/) or system-wide service (/etc/systemd/system/)",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        "-n",
        help="Custom service unit name (defaults to setting service_name)",
    ),
    stop: bool = typer.Option(
        True,
        "--stop/--no-stop",
        help="Stop and disable service before removing unit file / service entry",
    ),
) -> None:
    """Uninstall background service unit for the daemon across platforms."""
    settings = get_settings()
    service_name = name or settings.service_name

    manager = get_service_manager()
    try:
        manager.uninstall(
            name=service_name,
            is_user=user,
            stop_service=stop,
        )
    except Exception as e:
        console.print(f"[bold red]Uninstallation failed:[/bold red] {e}")
        raise typer.Exit(code=1) from e


def main() -> None:
    app()


if __name__ == "__main__":
    main()

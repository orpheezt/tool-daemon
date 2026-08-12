import ctypes
import shutil
import subprocess
import sys

from rich.console import Console

from tool_agent.services.base import BaseServiceManager, ServiceConfig

console = Console()


def is_admin() -> bool:
    if hasattr(ctypes, "windll"):
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except AttributeError, OSError:
            return False
    return False


def get_windows_executable_command() -> str:
    exec_path = shutil.which("tool-agent")
    if exec_path:
        return f'"{exec_path}" run'
    return f'"{sys.executable}" -m tool_agent.cli run'


class WindowsServiceManager(BaseServiceManager):
    def notify(self, state: str) -> bool:
        return True

    def install(self, config: ServiceConfig) -> str:
        if not is_admin():
            console.print(
                "[yellow]Warning: Installing a Windows Service requires Administrator privileges. "
                "Please run Command Prompt or PowerShell as Administrator.[/yellow]"
            )

        exec_cmd = config.exec_cmd or get_windows_executable_command()
        full_bin_path = (
            f"{exec_cmd} --interval {config.interval} "
            f"--format {config.log_format} --level {config.log_level}"
        )

        match config.startup.lower():
            case "auto" | "automatic":
                startup_type = "auto"
            case "demand" | "manual":
                startup_type = "demand"
            case "disabled":
                startup_type = "disabled"
            case _:
                startup_type = "auto"

        create_cmd = [
            "sc.exe",
            "create",
            config.name,
            f"binPath= {full_bin_path}",
            f"start= {startup_type}",
            f"DisplayName= {config.display_name}",
        ]

        try:
            subprocess.run(create_cmd, check=True, capture_output=True, text=True)
            console.print(f"[green]✓ Created Windows Service '{config.name}'[/green]")
        except subprocess.CalledProcessError as e:
            console.print(
                f"[red]Failed to create Windows Service '{config.name}': {e.stderr.strip()}[/red]"
            )
            raise

        desc_cmd = ["sc.exe", "description", config.name, config.description]
        try:
            subprocess.run(desc_cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError:
            pass

        failure_cmd = [
            "sc.exe",
            "failure",
            config.name,
            "reset=",
            "86400",
            "actions=",
            "restart/5000/restart/5000/restart/5000",
        ]
        try:
            subprocess.run(failure_cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError:
            pass

        if config.start_service:
            start_cmd = ["sc.exe", "start", config.name]
            try:
                subprocess.run(start_cmd, check=True, capture_output=True, text=True)
                console.print(
                    f"[green]✓ Started Windows Service '{config.name}'[/green]"
                )
            except subprocess.CalledProcessError as e:
                console.print(
                    f"[yellow]Warning: Could not start Windows Service '{config.name}': {e.stderr.strip()}[/yellow]"
                )

        return config.name

    def uninstall(
        self, name: str, is_user: bool = True, stop_service: bool = True
    ) -> None:
        if not is_admin():
            console.print(
                "[yellow]Warning: Uninstalling a Windows Service requires Administrator privileges.[/yellow]"
            )

        if stop_service:
            stop_cmd = ["sc.exe", "stop", name]
            try:
                subprocess.run(stop_cmd, check=True, capture_output=True, text=True)
                console.print(f"[green]✓ Stopped Windows Service '{name}'[/green]")
            except subprocess.CalledProcessError as e:
                console.print(
                    f"[yellow]Warning: Service stop failed (it may not be running): {e.stderr.strip()}[/yellow]"
                )

        delete_cmd = ["sc.exe", "delete", name]
        try:
            subprocess.run(delete_cmd, check=True, capture_output=True, text=True)
            console.print(f"[green]✓ Deleted Windows Service '{name}'[/green]")
        except subprocess.CalledProcessError as e:
            console.print(
                f"[red]Failed to delete Windows Service '{name}': {e.stderr.strip()}[/red]"
            )
            raise

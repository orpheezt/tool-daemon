import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console

from tool_daemon.services.base import BaseServiceManager, ServiceConfig

console = Console()


def is_admin() -> bool:
    if hasattr(ctypes, "windll"):
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except AttributeError, OSError:
            return False
    return False


def get_nssm_executable() -> str | None:
    exec_path = shutil.which("nssm") or shutil.which("nssm.exe")
    if exec_path:
        return exec_path

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_packages = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_packages.exists():
            for found in winget_packages.glob("**/nssm.exe"):
                return str(found)

    for common_path in (
        Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "nssm" / "nssm.exe",
        Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"))
        / "nssm"
        / "nssm.exe",
    ):
        if common_path.exists():
            return str(common_path)

    return None


def get_windows_executable() -> tuple[str, str]:
    exec_path = shutil.which("tool-daemon")
    if exec_path:
        return exec_path, "run"
    return sys.executable, "-m tool_daemon.cli run"


class WindowsServiceManager(BaseServiceManager):
    def notify(self, state: str) -> bool:
        return True

    def install(self, config: ServiceConfig) -> str:
        if not is_admin():
            console.print(
                "[yellow]Warning: Installing a Windows Service requires Administrator privileges. "
                "Please run Command Prompt or PowerShell as Administrator.[/yellow]"
            )

        nssm_bin = get_nssm_executable()
        if not nssm_bin:
            console.print(
                "[bold red]Error: NSSM (Non-Sucking Service Manager) was not found in PATH or standard directories.[/bold red]\n"
                "[yellow]Please install NSSM using winget:[/yellow]\n"
                "  [cyan]winget install --id NSSM.NSSM -e[/cyan]"
            )
            raise FileNotFoundError(
                "NSSM executable not found. Install it via winget: winget install --id NSSM.NSSM -e"
            )

        exe_path, base_args = get_windows_executable()
        args = f"{base_args} --interval {config.interval} --format {config.log_format} --level {config.log_level}"

        match config.startup.lower():
            case "demand" | "manual":
                startup_type = "SERVICE_DEMAND_START"
            case "disabled":
                startup_type = "SERVICE_DISABLED"
            case _:
                startup_type = "SERVICE_AUTO_START"

        try:
            subprocess.run(
                [nssm_bin, "install", config.name, exe_path, args],
                check=True,
                capture_output=True,
                text=True,
            )
            console.print(
                f"[green]✓ Installed Windows Service '{config.name}' via NSSM[/green]"
            )

            work_dir = str(Path(exe_path).parent)
            log_dir = (
                Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData"))
                / "tool-daemon"
                / "logs"
            )
            log_dir.mkdir(parents=True, exist_ok=True)
            stdout_log = str(log_dir / f"{config.name}.log")
            stderr_log = str(log_dir / f"{config.name}-error.log")

            subprocess.run(
                [nssm_bin, "set", config.name, "AppDirectory", work_dir],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [nssm_bin, "set", config.name, "DisplayName", config.display_name],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [nssm_bin, "set", config.name, "Description", config.description],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [nssm_bin, "set", config.name, "Start", startup_type],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [nssm_bin, "set", config.name, "AppStdout", stdout_log],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [nssm_bin, "set", config.name, "AppStderr", stderr_log],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [nssm_bin, "set", config.name, "AppRotateFiles", "1"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [nssm_bin, "set", config.name, "AppRotateBytes", "10485760"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [nssm_bin, "set", config.name, "AppExit", "Default", "Restart"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [nssm_bin, "set", config.name, "AppRestartDelay", "5000"],
                check=True,
                capture_output=True,
                text=True,
            )

        except subprocess.CalledProcessError as e:
            console.print(
                f"[red]Failed to configure Windows Service '{config.name}': {(e.stderr or e.stdout or '').strip()}[/red]"
            )
            raise

        if config.start_service:
            try:
                subprocess.run(
                    [nssm_bin, "start", config.name],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                console.print(
                    f"[green]✓ Started Windows Service '{config.name}' via NSSM[/green]"
                )
            except subprocess.CalledProcessError as e:
                console.print(
                    f"[yellow]Warning: Could not start Windows Service '{config.name}': {(e.stderr or e.stdout or '').strip()}[/yellow]"
                )

        return config.name

    def uninstall(
        self, name: str, is_user: bool = True, stop_service: bool = True
    ) -> None:
        if not is_admin():
            console.print(
                "[yellow]Warning: Uninstalling a Windows Service requires Administrator privileges.[/yellow]"
            )

        nssm_bin = get_nssm_executable() or "nssm"

        if stop_service:
            try:
                subprocess.run(
                    [nssm_bin, "stop", name], check=True, capture_output=True, text=True
                )
                console.print(f"[green]✓ Stopped Windows Service '{name}'[/green]")
            except subprocess.CalledProcessError as e:
                console.print(
                    f"[yellow]Warning: Service stop failed: {(e.stderr or e.stdout or '').strip()}[/yellow]"
                )

        try:
            subprocess.run(
                [nssm_bin, "remove", name, "confirm"],
                check=True,
                capture_output=True,
                text=True,
            )
            console.print(f"[green]✓ Removed Windows Service '{name}' via NSSM[/green]")
        except subprocess.CalledProcessError as e:
            console.print(
                f"[red]Failed to remove Windows Service '{name}': {(e.stderr or e.stdout or '').strip()}[/red]"
            )
            raise

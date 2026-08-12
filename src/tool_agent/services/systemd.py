import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from platformdirs import user_config_path
from rich.console import Console

from tool_agent.services.base import BaseServiceManager, ServiceConfig

console = Console()


def get_systemd_dir(is_user: bool = True) -> Path:
    if is_user:
        return user_config_path() / "systemd" / "user"
    else:
        return Path("/etc/systemd/system")


def get_executable_command() -> str:
    exec_path = shutil.which("tool-agent")
    if exec_path:
        return f"{exec_path} run"
    return f"{sys.executable} -m tool_agent.cli run"


class SystemdServiceManager(BaseServiceManager):
    def notify(self, state: str) -> bool:
        notify_socket = os.getenv("NOTIFY_SOCKET")
        if not notify_socket:
            return False
        if notify_socket.startswith("@"):
            notify_socket = "\0" + notify_socket[1:]
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
                sock.connect(notify_socket)
                sock.sendall(state.encode("utf-8"))
            return True
        except OSError, ValueError:
            return False

    def ensure_system_user(self, sys_user: str = "tool") -> None:
        try:
            subprocess.run(["id", "-u", sys_user], check=True, capture_output=True)
        except subprocess.CalledProcessError, FileNotFoundError:
            try:
                console.print(
                    f"[yellow]System user '{sys_user}' not found. Attempting creation...[/yellow]"
                )
                subprocess.run(
                    ["useradd", "-r", "-s", "/bin/false", sys_user],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                console.print(
                    f"[green]✓ Created unprivileged system user '{sys_user}'[/green]"
                )
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                console.print(
                    f"[yellow]Warning: Could not create system user '{sys_user}' automatically: {e}[/yellow]"
                )

    def generate_unit_file(self, config: ServiceConfig) -> str:
        wanted_by = "default.target" if config.is_user else "multi-user.target"
        full_cmd = (
            f"{config.exec_cmd} --interval {config.interval} "
            f"--format {config.log_format} --level {config.log_level}"
        )

        service_type = (
            "notify" if config.watchdog_sec and config.watchdog_sec > 0 else "simple"
        )

        service_lines = [
            "[Unit]",
            f"Description={config.description}",
            "After=network.target",
            "",
            "[Service]",
            f"Type={service_type}",
        ]

        if not config.is_user:
            service_lines.extend(
                [
                    f"User={config.sys_user}",
                    f"Group={config.sys_group}",
                    "WorkingDirectory=/opt/tool-agent",
                ]
            )

        service_lines.extend(
            [
                f"ExecStart={full_cmd}",
                "Restart=on-failure",
                "RestartSec=5s",
                "StandardOutput=journal",
                "StandardError=journal",
            ]
        )

        if config.watchdog_sec and config.watchdog_sec > 0:
            service_lines.append(f"WatchdogSec={config.watchdog_sec}s")

        if config.memory_max:
            service_lines.append(f"MemoryMax={config.memory_max}")
        if config.memory_high:
            service_lines.append(f"MemoryHigh={config.memory_high}")
        if config.cpu_quota:
            service_lines.append(f"CPUQuota={config.cpu_quota}")
        if config.tasks_max is not None and config.tasks_max > 0:
            service_lines.append(f"TasksMax={config.tasks_max}")

        if config.sandbox:
            protect_home = "true" if not config.is_user else "read-only"
            protect_sys = "strict" if not config.is_user else "full"
            service_lines.extend(
                [
                    f"ProtectSystem={protect_sys}",
                    f"ProtectHome={protect_home}",
                    "PrivateTmp=true",
                    "NoNewPrivileges=true",
                    "ProtectKernelTunables=true",
                    "ProtectKernelModules=true",
                    "ProtectControlGroups=true",
                    "RestrictRealtime=true",
                    "RestrictSUIDSGID=true",
                ]
            )

        service_lines.extend(
            [
                "",
                "[Install]",
                f"WantedBy={wanted_by}",
                "",
            ]
        )

        return "\n".join(service_lines)

    def _run_systemctl(
        self, args: list[str], is_user: bool = True
    ) -> subprocess.CompletedProcess[str]:
        cmd = ["systemctl"]
        if is_user:
            cmd.append("--user")
        cmd.extend(args)

        return subprocess.run(cmd, check=True, capture_output=True, text=True)

    def install(self, config: ServiceConfig) -> Path:
        if not config.is_user:
            self.ensure_system_user(config.sys_user)

        unit_dir = get_systemd_dir(is_user=config.is_user)
        unit_file_name = f"{config.name}.service"
        unit_path = unit_dir / unit_file_name

        if unit_path.exists() and not config.force:
            raise FileExistsError(
                f"Service unit file already exists at '{unit_path}'. Use --force to overwrite."
            )

        unit_dir.mkdir(parents=True, exist_ok=True)
        if not config.exec_cmd:
            config.exec_cmd = get_executable_command()

        unit_content = self.generate_unit_file(config)
        unit_path.write_text(unit_content, encoding="utf-8")
        console.print(f"[green]✓ Created systemd unit file at:[/green] {unit_path}")

        try:
            self._run_systemctl(["daemon-reload"], is_user=config.is_user)
            console.print("[green]✓ Executed systemctl daemon-reload[/green]")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            console.print(
                f"[yellow]Warning: Could not execute systemctl daemon-reload: {e}[/yellow]"
            )

        if config.start_service:
            try:
                self._run_systemctl(
                    ["enable", "--now", unit_file_name], is_user=config.is_user
                )
                console.print(
                    f"[green]✓ Enabled and started service '{unit_file_name}'[/green]"
                )
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                console.print(f"[red]Error enabling/starting service: {e}[/red]")
                raise

        return unit_path

    def uninstall(
        self, name: str, is_user: bool = True, stop_service: bool = True
    ) -> None:
        unit_dir = get_systemd_dir(is_user=is_user)
        unit_file_name = f"{name}.service"
        unit_path = unit_dir / unit_file_name

        if stop_service:
            try:
                self._run_systemctl(["stop", unit_file_name], is_user=is_user)
                console.print(f"[green]✓ Stopped service '{name}'[/green]")
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                console.print(
                    f"[yellow]Warning: Service stop failed (it may not be running): {e}[/yellow]"
                )

            try:
                self._run_systemctl(["disable", unit_file_name], is_user=is_user)
                console.print(f"[green]✓ Disabled service '{name}'[/green]")
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                console.print(f"[yellow]Warning: Service disable failed: {e}[/yellow]")

        if unit_path.exists():
            unit_path.unlink()
            console.print(f"[green]✓ Removed systemd unit file at:[/green] {unit_path}")
        else:
            console.print(f"[yellow]Unit file '{unit_path}' does not exist.[/yellow]")

        try:
            self._run_systemctl(["daemon-reload"], is_user=is_user)
            console.print("[green]✓ Executed systemctl daemon-reload[/green]")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            console.print(
                f"[yellow]Warning: Could not execute systemctl daemon-reload: {e}[/yellow]"
            )

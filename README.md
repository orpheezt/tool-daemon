# Tool Agent (`tool-agent`)

> Cross-Platform Background Agent Daemon with Systemd Sandboxing, Resource Limits, Watchdog Heartbeats, and Windows Service Control Manager Integration.

---

## Features

- **Cross-Platform Background Services**: Seamless background service management across **Linux** (systemd) and **Windows** (Service Control Manager via `sc.exe`).
- **Automated Installation Scripts**: One-line install scripts for Linux (`scripts/install.sh`) and Windows (`scripts/install.ps1`).
- **Security Sandboxing**: Systemd isolation directives (`ProtectSystem=strict`, `ProtectHome=true`, `PrivateTmp=true`, `NoNewPrivileges=true`).
- **Unprivileged Service Account**: System-wide installation automatically provisions and runs under a dedicated `User=tool` / `Group=tool` account.
- **Hardware Quotas & Limits**: Configurable memory boundaries (`MemoryMax`, `MemoryHigh`), CPU quotas (`CPUQuota`), and task limits (`TasksMax`).
- **Systemd Watchdog & Notification**: Built-in `sd_notify` socket protocol sending `READY=1`, `WATCHDOG=1`, and `STOPPING=1` status heartbeats.

---

## One-Line Installation

### Linux / macOS (Bash)
```bash
curl -LsSf https://raw.githubusercontent.com/tool/tool-agent/main/scripts/install.sh | sh
```

### Windows (PowerShell)
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/tool/tool-agent/main/scripts/install.ps1 | iex"
```

The installer automatically:
1. Installs `uv` if not present.
2. Clones or uses repository sources.
3. Provisions the `tool` system user (Linux system mode).
4. Creates a Python virtual environment at `/opt/tool-agent/.venv` using `.python-version`.
5. Builds and installs the distribution wheel package (`.whl`).
6. Symlinks the executable to `/usr/local/bin/tool-agent`.

---

## Quick Start & Usage

### 1. Run in Foreground
Run the daemon interactively in the terminal:
```bash
tool-agent run --interval 5.0 --format json --level INFO
```

### 2. Install as Background Service

#### User Mode Service (Linux `~/.config/systemd/user/`)
Does not require `sudo` privileges:
```bash
tool-agent install --user
```

#### System Mode Service (Linux `/etc/systemd/system/`)
Runs under dedicated unprivileged system user `tool`:
```bash
sudo tool-agent install --system
```

#### Windows Service (Windows SCM)
Run Command Prompt or PowerShell as Administrator:
```powershell
tool-agent install --startup auto --display-name "Tool Agent Daemon"
```

### 3. Service Options & Hardware Limits
Customize poll interval, sandboxing, watchdog, and hardware resource boundaries during installation:
```bash
tool-agent install \
  --system \
  --interval 5.0 \
  --sandbox \
  --memory-max 512M \
  --memory-high 400M \
  --cpu-quota 50% \
  --tasks-max 100 \
  --watchdog-sec 30 \
  --sys-user tool
```

### 4. Uninstall Background Service
Stop and remove the installed service:
```bash
# Linux User Mode
tool-agent uninstall --user

# Linux System Mode
sudo tool-agent uninstall --system

# Windows Service
tool-agent uninstall
```

---

## Service Lifecycle & Operational Management

### 1. Linux Systemd Operations & Lifecycle

#### Service Control Commands
```bash
# Inspect Status
systemctl --user status tool-daemon        # User Mode
sudo systemctl status tool-daemon         # System Mode

# Manual Control (Start / Stop / Restart)
systemctl --user start tool-daemon
systemctl --user stop tool-daemon
systemctl --user restart tool-daemon
```

#### Monitoring Logs with `journalctl`
Tail live structured JSON logs emitted by the daemon:
```bash
# User Mode live log tailing
journalctl --user -u tool-daemon -f -o cat

# System Mode live log tailing
sudo journalctl -u tool-daemon -f -o cat
```

#### Systemd Heartbeat & Lifecycle Mechanics
- **`Type=notify`**: Systemd launches the service process and waits for `READY=1` via Unix domain socket `$NOTIFY_SOCKET` before marking the unit as `active (running)`.
- **`WatchdogSec=30s`**: Systemd expects `WATCHDOG=1` heartbeats after each execution pass. If the agent process hangs or deadlocks beyond 30 seconds, systemd automatically kills and restarts the process.
- **Graceful Shutdown**: On `systemctl stop`, systemd sends `SIGTERM`. The daemon catches the signal, emits `STOPPING=1` notification, and exits cleanly.
- **Failure Recovery**: `Restart=on-failure` with `RestartSec=5s` automatically recovers from unexpected crashes.

---

### 2. Windows Service Management (SCM) Operations & Lifecycle

#### Service Control Commands (PowerShell / CMD)
```powershell
# Inspect Status
Get-Service tool-daemon                     # PowerShell
sc.exe query tool-daemon                     # CMD / PowerShell

# Manual Control (Start / Stop / Restart)
Start-Service tool-daemon                    # PowerShell
Stop-Service tool-daemon                     # PowerShell
Restart-Service tool-daemon                  # PowerShell

# Alternative CMD Commands
sc.exe start tool-daemon
sc.exe stop tool-daemon
```

#### Monitoring Logs
- **Console / Stream Logs**: When executed directly or redirected, logs are formatted as JSON or colored rich text.
- **Windows Event Viewer**: View Windows Service Control Manager start, stop, and failure events using PowerShell:
  ```powershell
  Get-WinEvent -ProviderName "Service Control Manager" | Where-Object { $_.Message -match "tool-daemon" }
  ```

#### Windows SCM Lifecycle Mechanics
- **Automatic Boot Startup**: Installed with `start= auto` so the background service launches automatically upon system boot before user login.
- **Failure Recovery Actions**: Configured via `sc.exe failure` to automatically restart the service 5 seconds (`5000ms`) after any crash, resetting the failure counter daily (`reset= 86400`).

---

## Service Configuration Reference

| Option | Type | Default | Description |
|---|---|---|---|
| `--user / --system` | Flag | `--user` | Install as user service or system-wide service |
| `--interval, -i` | Float | `5.0` | Sleep interval in seconds between daemon passes |
| `--format, -f` | String | `json` | Log format (`json` or `text`) |
| `--level, -l` | String | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `--sandbox / --no-sandbox` | Flag | `--sandbox` | Enable systemd security sandboxing directives |
| `--memory-max` | String | `512M` | Maximum memory limit for systemd service |
| `--memory-high` | String | `400M` | Memory throttle threshold for systemd service |
| `--cpu-quota` | String | `50%` | CPU quota percentage for systemd service |
| `--tasks-max` | Integer | `100` | Maximum process tasks/threads limit for systemd service |
| `--watchdog-sec` | Integer | `30` | Systemd watchdog timeout in seconds (`0` to disable) |
| `--sys-user` | String | `tool` | Dedicated unprivileged system user for system mode |
| `--sys-group` | String | `tool` | Dedicated unprivileged system group for system mode |
| `--display-name` | String | `Tool Agent Daemon` | Display name for Windows Service |
| `--startup` | String | `auto` | Windows Service startup type (`auto`, `demand`, `disabled`) |

---

## Local Development & Code Quality

### Setup Development Environment
```bash
# Install dependencies
uv sync

# Run daemon locally
uv run tool-agent run
```

### Code Formatting & Type Checking
```bash
# Format code with ruff
uv run ruff format .

# Check lint rules
uv run ruff check .

# Static type check with ty
uv run ty check
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

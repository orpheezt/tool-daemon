#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/tool-daemon}"
BIN_DIR="${BIN_DIR:-/usr/local/bin}"
REPO_URL="${REPO_URL:-https://github.com/orpheezt/tool-daemon.git}"
SYS_USER="${SYS_USER:-tool}"

TEMP_DIR=""
cleanup() {
    if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
}
trap cleanup EXIT

echo "====================================================="
echo "        Tool Background Daemon Installer             "
echo "====================================================="

# 1. Detect source workspace
SCRIPT_PATH="${BASH_SOURCE[0]:-}"
if [ -n "$SCRIPT_PATH" ] && [ -f "$SCRIPT_PATH" ]; then
    SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
    PARENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    PARENT_DIR=""
fi

if [ -f "$PARENT_DIR/pyproject.toml" ] && [ -f "$PARENT_DIR/.python-version" ]; then
    SOURCE_DIR="$PARENT_DIR"
    echo "→ Using local source workspace: $SOURCE_DIR"
elif [ -f "$PWD/pyproject.toml" ] && [ -f "$PWD/.python-version" ]; then
    SOURCE_DIR="$PWD"
    echo "→ Using local source workspace: $SOURCE_DIR"
else
    echo "→ Local source workspace not detected. Fetching repository..."
    TEMP_DIR="$(mktemp -d)"
    if command -v git &>/dev/null; then
        git clone --depth 1 "$REPO_URL" "$TEMP_DIR"
        SOURCE_DIR="$TEMP_DIR"
    elif command -v curl &>/dev/null && command -v unzip &>/dev/null; then
        echo "→ git not found. Downloading ZIP archive..."
        ZIP_URL="${REPO_URL%.git}/archive/refs/heads/master.zip"
        curl -sSL "$ZIP_URL" -o "$TEMP_DIR/repo.zip"
        unzip -q "$TEMP_DIR/repo.zip" -d "$TEMP_DIR"
        rm -f "$TEMP_DIR/repo.zip"
        SOURCE_DIR="$(find "$TEMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
    else
        echo "Error: Neither git nor curl/unzip found." >&2
        exit 1
    fi
fi

# 2. Ensure uv is installed
if ! command -v uv &>/dev/null; then
    echo "→ Package manager 'uv' not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

# 3. Build wheel artifact
echo "→ Building distribution wheel artifact..."
(cd "$SOURCE_DIR" && uv build --wheel --out-dir "$SOURCE_DIR/dist")

WHEEL_FILE="$(find "$SOURCE_DIR/dist" -name "*.whl" | sort -V | tail -n 1)"
if [ -z "$WHEEL_FILE" ]; then
    echo "Error: Wheel build failed or output wheel file not found." >&2
    exit 1
fi
echo "✓ Built wheel: $(basename "$WHEEL_FILE")"

# 4. Provision system user account if installing in system mode
if command -v useradd &>/dev/null && ! id -u "$SYS_USER" &>/dev/null; then
    echo "→ Creating unprivileged system user '$SYS_USER'..."
    sudo useradd -r -s /bin/false -d "$INSTALL_DIR" "$SYS_USER" 2>/dev/null || true
    echo "✓ Created system user '$SYS_USER'"
fi

# 5. Create installation target directory at /opt/tool-daemon
if [ ! -d "$INSTALL_DIR" ]; then
    echo "→ Creating installation directory $INSTALL_DIR..."
    sudo mkdir -p "$INSTALL_DIR"
    sudo chown -R "$USER:$(id -gn)" "$INSTALL_DIR"
fi

# 6. Read Python version from .python-version
PYTHON_VER="3.14"
if [ -f "$SOURCE_DIR/.python-version" ]; then
    PYTHON_VER="$(tr -d ' \t\r\n' < "$SOURCE_DIR/.python-version")"
fi

echo "→ Creating virtual environment (Python $PYTHON_VER) at $INSTALL_DIR/.venv..."
uv venv --allow-existing --python "$PYTHON_VER" "$INSTALL_DIR/.venv"

# 7. Install wheel into virtual environment
echo "→ Installing tool-daemon wheel into virtual environment..."
uv pip install --python "$INSTALL_DIR/.venv/bin/python" "$WHEEL_FILE"

# 8. Symlink executable to system PATH
echo "→ Symlinking executable to $BIN_DIR/tool-daemon..."
sudo ln -sf "$INSTALL_DIR/.venv/bin/tool-daemon" "$BIN_DIR/tool-daemon"

echo "====================================================="
echo "✓ Successfully installed tool-daemon to $INSTALL_DIR"
echo "✓ Binary symlinked at $BIN_DIR/tool-daemon"
echo "====================================================="

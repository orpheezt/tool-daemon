#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/tool-agent}"
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
echo "        Tool Background Agent Installer              "
echo "====================================================="

# 1. Detect source workspace
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -f "$PARENT_DIR/pyproject.toml" ] && [ -f "$PARENT_DIR/.python-version" ]; then
    SOURCE_DIR="$PARENT_DIR"
    echo "→ Using local source workspace: $SOURCE_DIR"
elif [ -f "$PWD/pyproject.toml" ] && [ -f "$PWD/.python-version" ]; then
    SOURCE_DIR="$PWD"
    echo "→ Using local source workspace: $SOURCE_DIR"
else
    echo "→ Local source workspace not detected. Fetching repository..."
    TEMP_DIR="$(mktemp -d)"
    git clone --depth 1 "$REPO_URL" "$TEMP_DIR"
    SOURCE_DIR="$TEMP_DIR"
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

# 5. Create installation target directory at /opt/tool-agent
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
echo "→ Installing tool-agent wheel into virtual environment..."
uv pip install --python "$INSTALL_DIR/.venv/bin/python" "$WHEEL_FILE"

# 8. Symlink executable to system PATH
echo "→ Symlinking executable to $BIN_DIR/tool-agent..."
sudo ln -sf "$INSTALL_DIR/.venv/bin/tool-agent" "$BIN_DIR/tool-agent"

echo "====================================================="
echo "✓ Successfully installed tool-agent to $INSTALL_DIR"
echo "✓ Binary symlinked at $BIN_DIR/tool-agent"
echo "====================================================="

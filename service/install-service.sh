#!/usr/bin/env bash
# OC-Memory Service Installer for Linux and macOS
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="/usr/local/share/oc-memory"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Linux*)  echo "linux" ;;
        Darwin*) echo "macos" ;;
        *)       error "Unsupported OS: $(uname -s)" ;;
    esac
}

# Install project files
install_files() {
    info "Installing OC-Memory to ${INSTALL_DIR}..."
    sudo mkdir -p "$INSTALL_DIR"
    sudo cp -r "$PROJECT_DIR/lib" "$INSTALL_DIR/"
    sudo cp "$PROJECT_DIR/memory_observer.py" "$INSTALL_DIR/"
    sudo cp "$PROJECT_DIR/requirements.txt" "$INSTALL_DIR/"

    if [ -f "$PROJECT_DIR/config.yaml" ]; then
        sudo cp "$PROJECT_DIR/config.yaml" "$INSTALL_DIR/"
    fi

    info "Files installed to ${INSTALL_DIR}"
}

# Install Python dependencies
install_deps() {
    info "Installing Python dependencies..."
    pip3 install -r "$INSTALL_DIR/requirements.txt" --quiet 2>/dev/null || \
        python3 -m pip install -r "$INSTALL_DIR/requirements.txt" --quiet
    info "Dependencies installed"
}

# Install Linux systemd service
install_linux() {
    local user="${USER}"
    local service_file="/etc/systemd/system/oc-memory@.service"

    info "Installing systemd service..."
    sudo cp "$SCRIPT_DIR/oc-memory.service" "$service_file"
    sudo systemctl daemon-reload

    info "Enabling service for user: ${user}..."
    sudo systemctl enable "oc-memory@${user}"
    sudo systemctl start "oc-memory@${user}"

    info "Service installed and started"
    info "Commands:"
    info "  Status:  sudo systemctl status oc-memory@${user}"
    info "  Stop:    sudo systemctl stop oc-memory@${user}"
    info "  Logs:    journalctl -u oc-memory@${user} -f"
}

# Install macOS LaunchAgent
install_macos() {
    local plist_src="$SCRIPT_DIR/com.openclaw.oc-memory.plist"
    local plist_dst="$HOME/Library/LaunchAgents/com.openclaw.oc-memory.plist"

    info "Installing LaunchAgent..."
    mkdir -p "$HOME/Library/LaunchAgents"
    cp "$plist_src" "$plist_dst"

    # Update paths for the current user
    sed -i '' "s|/usr/local/share/oc-memory|${INSTALL_DIR}|g" "$plist_dst"

    info "Loading LaunchAgent..."
    launchctl load "$plist_dst" 2>/dev/null || true

    info "Service installed and loaded"
    info "Commands:"
    info "  Status:  launchctl list | grep oc-memory"
    info "  Stop:    launchctl unload $plist_dst"
    info "  Logs:    tail -f /tmp/oc-memory.stdout.log"
}

# Main
main() {
    info "OC-Memory Service Installer"
    echo ""

    local os_type
    os_type="$(detect_os)"
    info "Detected OS: ${os_type}"

    install_files
    install_deps

    case "$os_type" in
        linux) install_linux ;;
        macos) install_macos ;;
    esac

    echo ""
    info "Installation complete!"
}

main "$@"

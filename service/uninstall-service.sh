#!/usr/bin/env bash
# OC-Memory Service Uninstaller for Linux and macOS
set -euo pipefail

INSTALL_DIR="/usr/local/share/oc-memory"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

detect_os() {
    case "$(uname -s)" in
        Linux*)  echo "linux" ;;
        Darwin*) echo "macos" ;;
        *)       error "Unsupported OS: $(uname -s)" ;;
    esac
}

uninstall_linux() {
    local user="${USER}"
    info "Stopping and disabling systemd service..."
    sudo systemctl stop "oc-memory@${user}" 2>/dev/null || true
    sudo systemctl disable "oc-memory@${user}" 2>/dev/null || true
    sudo rm -f /etc/systemd/system/oc-memory@.service
    sudo systemctl daemon-reload
    info "systemd service removed"
}

uninstall_macos() {
    local plist="$HOME/Library/LaunchAgents/com.openclaw.oc-memory.plist"
    info "Unloading LaunchAgent..."
    launchctl unload "$plist" 2>/dev/null || true
    rm -f "$plist"
    info "LaunchAgent removed"
}

main() {
    info "OC-Memory Service Uninstaller"
    echo ""

    local os_type
    os_type="$(detect_os)"

    case "$os_type" in
        linux) uninstall_linux ;;
        macos) uninstall_macos ;;
    esac

    info "Removing install directory..."
    sudo rm -rf "$INSTALL_DIR"

    echo ""
    info "Uninstall complete!"
    info "Note: User config files (~/.openclaw/) were NOT removed."
}

main "$@"

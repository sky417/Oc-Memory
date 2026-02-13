#!/bin/bash
# OC-Guardian Service Installer
# Usage: sudo ./install-service.sh [install|uninstall]

set -e

ACTION="${1:-install}"
BINARY_PATH="${BINARY_PATH:-/usr/local/bin/oc-guardian}"

detect_os() {
    case "$(uname -s)" in
        Linux*)  echo "linux" ;;
        Darwin*) echo "macos" ;;
        *)       echo "unknown" ;;
    esac
}

OS=$(detect_os)

# =============================================================================
# Linux (systemd)
# =============================================================================

install_linux() {
    echo "Installing OC-Guardian systemd service..."

    # Copy binary
    if [ -f "../../guardian/target/release/oc-guardian" ]; then
        sudo cp "../../guardian/target/release/oc-guardian" "$BINARY_PATH"
        sudo chmod +x "$BINARY_PATH"
        echo "  Binary installed: $BINARY_PATH"
    fi

    # Create config directory
    sudo mkdir -p /etc/oc-guardian
    sudo mkdir -p /var/log/oc-guardian

    # Copy config if not exists
    if [ ! -f /etc/oc-guardian/guardian.toml ] && [ -f ../guardian.toml.example ]; then
        sudo cp ../guardian.toml.example /etc/oc-guardian/guardian.toml
        echo "  Config created: /etc/oc-guardian/guardian.toml"
    fi

    # Install service
    sudo cp oc-guardian.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable oc-guardian
    echo "  Service installed and enabled"

    echo ""
    echo "Commands:"
    echo "  sudo systemctl start oc-guardian   - Start"
    echo "  sudo systemctl stop oc-guardian    - Stop"
    echo "  sudo systemctl status oc-guardian  - Status"
    echo "  sudo journalctl -u oc-guardian -f  - Logs"
}

uninstall_linux() {
    echo "Uninstalling OC-Guardian systemd service..."
    sudo systemctl stop oc-guardian 2>/dev/null || true
    sudo systemctl disable oc-guardian 2>/dev/null || true
    sudo rm -f /etc/systemd/system/oc-guardian.service
    sudo systemctl daemon-reload
    echo "  Service removed"
}

# =============================================================================
# macOS (launchd)
# =============================================================================

install_macos() {
    echo "Installing OC-Guardian LaunchAgent..."

    # Copy binary
    if [ -f "../../guardian/target/release/oc-guardian" ]; then
        sudo cp "../../guardian/target/release/oc-guardian" "$BINARY_PATH"
        sudo chmod +x "$BINARY_PATH"
        echo "  Binary installed: $BINARY_PATH"
    fi

    # Create directories
    sudo mkdir -p /usr/local/etc/oc-guardian
    sudo mkdir -p /usr/local/var/log/oc-guardian

    # Copy config if not exists
    if [ ! -f /usr/local/etc/oc-guardian/guardian.toml ] && [ -f ../guardian.toml.example ]; then
        sudo cp ../guardian.toml.example /usr/local/etc/oc-guardian/guardian.toml
        echo "  Config created: /usr/local/etc/oc-guardian/guardian.toml"
    fi

    # Install LaunchAgent (user-level, no sudo needed for load)
    PLIST_DIR="$HOME/Library/LaunchAgents"
    mkdir -p "$PLIST_DIR"
    cp com.openclaw.guardian.plist "$PLIST_DIR/"

    launchctl load "$PLIST_DIR/com.openclaw.guardian.plist"
    echo "  LaunchAgent installed and loaded"

    echo ""
    echo "Commands:"
    echo "  launchctl start com.openclaw.guardian  - Start"
    echo "  launchctl stop com.openclaw.guardian   - Stop"
    echo "  tail -f /usr/local/var/log/oc-guardian/stdout.log  - Logs"
}

uninstall_macos() {
    echo "Uninstalling OC-Guardian LaunchAgent..."
    PLIST="$HOME/Library/LaunchAgents/com.openclaw.guardian.plist"
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo "  LaunchAgent removed"
}

# =============================================================================
# Main
# =============================================================================

case "$OS" in
    linux)
        case "$ACTION" in
            install)   install_linux ;;
            uninstall) uninstall_linux ;;
            *) echo "Usage: $0 [install|uninstall]"; exit 1 ;;
        esac
        ;;
    macos)
        case "$ACTION" in
            install)   install_macos ;;
            uninstall) uninstall_macos ;;
            *) echo "Usage: $0 [install|uninstall]"; exit 1 ;;
        esac
        ;;
    *)
        echo "Unsupported OS. Use Windows install-service.ps1 instead."
        exit 1
        ;;
esac

echo ""
echo "Done!"

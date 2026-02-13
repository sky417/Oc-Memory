#!/bin/bash
# OC-Memory + Guardian Install Script
# Usage: ./scripts/install.sh [--skip-python] [--skip-build]
#
# Options:
#   --skip-python   Skip Python dependency installation
#   --skip-build    Skip Guardian Rust build

set -e

SKIP_PYTHON=false
SKIP_BUILD=false

for arg in "$@"; do
    case $arg in
        --skip-python) SKIP_PYTHON=true ;;
        --skip-build)  SKIP_BUILD=true ;;
        *)             echo "Unknown option: $arg"; exit 1 ;;
    esac
done

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "========================================="
echo "  OC-Memory + Guardian Install"
echo "========================================="
echo "Project root: $PROJECT_ROOT"
echo ""

# =============================================================================
# 1. Check and Install Rust
# =============================================================================

echo "--- Checking Rust ---"
if ! command -v cargo &> /dev/null; then
    echo "Rust is not installed."
    read -p "Install Rust via rustup? [Y/n] " answer
    if [[ "$answer" =~ ^[Nn]$ ]]; then
        echo "Rust is required for Guardian. Exiting."
        exit 1
    fi
    echo "Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
fi

RUST_VERSION=$(rustc --version)
CARGO_VERSION=$(cargo --version)
echo "  Rust:  $RUST_VERSION"
echo "  Cargo: $CARGO_VERSION"
echo ""

# =============================================================================
# 2. Check Python
# =============================================================================

echo "--- Checking Python ---"
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "WARNING: Python not found. OC-Memory features will be limited."
    echo "Install Python 3.8+ for full functionality."
else
    PY_VERSION=$($PYTHON_CMD --version 2>&1)
    echo "  Python: $PY_VERSION"
fi
echo ""

# =============================================================================
# 3. Install Python Dependencies
# =============================================================================

if [ "$SKIP_PYTHON" = false ] && [ -n "$PYTHON_CMD" ]; then
    echo "--- Installing Python Dependencies ---"
    if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        $PYTHON_CMD -m pip install -r "$PROJECT_ROOT/requirements.txt" 2>/dev/null || \
        pip install -r "$PROJECT_ROOT/requirements.txt" 2>/dev/null || \
        echo "WARNING: Failed to install Python dependencies. Some features may not work."
    else
        echo "  No requirements.txt found, skipping."
    fi
    echo ""
fi

# =============================================================================
# 4. Build Guardian
# =============================================================================

if [ "$SKIP_BUILD" = false ]; then
    echo "--- Building Guardian ---"
    cd "$PROJECT_ROOT/guardian"
    cargo build --release 2>&1

    BINARY="target/release/oc-guardian"
    if [ -f "$BINARY" ]; then
        SIZE=$(du -h "$BINARY" | cut -f1)
        echo "  Binary: $BINARY ($SIZE)"

        # Copy to project root
        cp "$BINARY" "$PROJECT_ROOT/oc-guardian"
        chmod +x "$PROJECT_ROOT/oc-guardian"
        echo "  Copied to: $PROJECT_ROOT/oc-guardian"
    fi
    cd "$PROJECT_ROOT"
    echo ""
fi

# =============================================================================
# 5. Auto-detect and Generate Configuration
# =============================================================================

echo "--- Configuration Setup ---"

# Detect OpenClaw paths
OPENCLAW_DIR=""
if [ -d "$HOME/.openclaw" ]; then
    OPENCLAW_DIR="$HOME/.openclaw"
    echo "  OpenClaw detected: $OPENCLAW_DIR"
elif [ -d "$HOME/.config/openclaw" ]; then
    OPENCLAW_DIR="$HOME/.config/openclaw"
    echo "  OpenClaw detected: $OPENCLAW_DIR"
else
    echo "  OpenClaw not detected (will use defaults)"
fi

# Generate guardian.toml if not exists
if [ ! -f "$PROJECT_ROOT/guardian/guardian.toml" ]; then
    if [ -f "$PROJECT_ROOT/guardian/guardian.toml.example" ]; then
        cp "$PROJECT_ROOT/guardian/guardian.toml.example" "$PROJECT_ROOT/guardian/guardian.toml"
        echo "  Created guardian.toml from example"

        # Auto-fill detected paths
        if [ -n "$OPENCLAW_DIR" ]; then
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s|~/.openclaw|$OPENCLAW_DIR|g" "$PROJECT_ROOT/guardian/guardian.toml"
            else
                sed -i "s|~/.openclaw|$OPENCLAW_DIR|g" "$PROJECT_ROOT/guardian/guardian.toml"
            fi
            echo "  Auto-filled OpenClaw paths"
        fi
    fi
fi

# Generate config.yaml if not exists
if [ ! -f "$PROJECT_ROOT/config.yaml" ] && [ -f "$PROJECT_ROOT/config.example.yaml" ]; then
    cp "$PROJECT_ROOT/config.example.yaml" "$PROJECT_ROOT/config.yaml"
    echo "  Created config.yaml from example"
fi

echo ""

# =============================================================================
# 6. Create log directories
# =============================================================================

echo "--- Creating Directories ---"
mkdir -p "$PROJECT_ROOT/logs"
echo "  Created logs/"

if [ -n "$OPENCLAW_DIR" ]; then
    mkdir -p "$OPENCLAW_DIR/workspace/memory"
    echo "  Ensured $OPENCLAW_DIR/workspace/memory/"
fi

echo ""

# =============================================================================
# 7. Verify Installation
# =============================================================================

echo "--- Verification ---"

if [ -f "$PROJECT_ROOT/oc-guardian" ]; then
    echo "  Guardian binary: OK"
    "$PROJECT_ROOT/oc-guardian" --version 2>/dev/null || echo "    (version check skipped)"
else
    echo "  Guardian binary: MISSING"
fi

echo ""
echo "========================================="
echo "  Install Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Edit guardian/guardian.toml (process paths)"
echo "  2. Edit config.yaml (API keys, if using OC-Memory)"
echo "  3. Run: ./oc-guardian start"
echo ""
echo "Quick commands:"
echo "  ./oc-guardian start    - Start all processes"
echo "  ./oc-guardian status   - Check status"
echo "  ./oc-guardian stop     - Stop all processes"
echo "  ./oc-guardian --help   - Full help"
echo ""

#!/bin/bash
# OC-Guardian Build Script
# Usage: ./scripts/build.sh [target]
# Targets: release, debug, cross-windows, cross-linux, cross-macos, all

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GUARDIAN_DIR="$PROJECT_ROOT/guardian"
OUTPUT_DIR="$PROJECT_ROOT/dist"

echo "========================================="
echo "  OC-Guardian Build Script"
echo "========================================="

# Default target
TARGET="${1:-release}"

# Check Rust
if ! command -v cargo &> /dev/null; then
    echo "ERROR: Rust/Cargo is not installed."
    echo "Install with: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    exit 1
fi

echo "Rust: $(rustc --version)"
echo "Target: $TARGET"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

build_release() {
    echo "Building release binary..."
    cd "$GUARDIAN_DIR"
    cargo build --release

    # Determine binary name based on OS
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        BINARY="target/release/oc-guardian.exe"
        DEST="$OUTPUT_DIR/oc-guardian.exe"
    else
        BINARY="target/release/oc-guardian"
        DEST="$OUTPUT_DIR/oc-guardian"
    fi

    if [ -f "$BINARY" ]; then
        cp "$BINARY" "$DEST"
        echo "Binary copied to: $DEST"
        echo "Size: $(du -h "$DEST" | cut -f1)"
    fi
    cd "$PROJECT_ROOT"
}

build_debug() {
    echo "Building debug binary..."
    cd "$GUARDIAN_DIR"
    cargo build
    cd "$PROJECT_ROOT"
}

cross_compile() {
    local target="$1"
    local output_name="$2"

    echo "Cross-compiling for $target..."

    # Check if target is installed
    if ! rustup target list --installed | grep -q "$target"; then
        echo "Installing target: $target"
        rustup target add "$target"
    fi

    cd "$GUARDIAN_DIR"
    cargo build --release --target "$target"

    local binary="target/$target/release/$output_name"
    if [ -f "$binary" ]; then
        cp "$binary" "$OUTPUT_DIR/"
        echo "Built: $OUTPUT_DIR/$output_name ($(du -h "$OUTPUT_DIR/$output_name" | cut -f1))"
    fi
    cd "$PROJECT_ROOT"
}

case "$TARGET" in
    release)
        build_release
        ;;
    debug)
        build_debug
        ;;
    cross-windows)
        cross_compile "x86_64-pc-windows-msvc" "oc-guardian.exe"
        ;;
    cross-linux)
        cross_compile "x86_64-unknown-linux-gnu" "oc-guardian"
        ;;
    cross-macos-x64)
        cross_compile "x86_64-apple-darwin" "oc-guardian"
        ;;
    cross-macos-arm)
        cross_compile "aarch64-apple-darwin" "oc-guardian"
        ;;
    all)
        build_release
        echo ""
        echo "Note: Cross-compilation requires appropriate toolchains."
        echo "Run individual cross-* targets as needed."
        ;;
    test)
        echo "Running tests..."
        cd "$GUARDIAN_DIR"
        cargo test
        cd "$PROJECT_ROOT"
        ;;
    *)
        echo "Unknown target: $TARGET"
        echo "Usage: $0 [release|debug|cross-windows|cross-linux|cross-macos-x64|cross-macos-arm|all|test]"
        exit 1
        ;;
esac

echo ""
echo "Build complete!"

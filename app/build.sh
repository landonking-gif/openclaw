#!/bin/bash
set -e

# Build OpenClaw Army macOS app
APP_DIR="/Users/landonking/openclaw-army/app"
SRC_DIR="$APP_DIR/OpenClawArmy"
BUILD_DIR="$APP_DIR/build"
APP_BUNDLE="$BUILD_DIR/OpenClaw Army.app"

echo "=== Building OpenClaw Army ==="

# Clean
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Create app bundle structure
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

# Copy Info.plist
cp "$SRC_DIR/Info.plist" "$APP_BUNDLE/Contents/"

# Compile Swift files
echo "Compiling Swift sources..."
swiftc \
  -o "$APP_BUNDLE/Contents/MacOS/OpenClawArmy" \
  -target arm64-apple-macosx14.0 \
  -sdk "$(xcrun --show-sdk-path)" \
  -framework SwiftUI \
  -framework AppKit \
  -framework WebKit \
  -framework Combine \
  -parse-as-library \
  "$SRC_DIR/OpenClawArmyApp.swift" \
  "$SRC_DIR/OrchestratorService.swift" \
  "$SRC_DIR/MenuBarPopoverView.swift" \
  "$SRC_DIR/DashboardView.swift" \
  2>&1

echo "Compile successful!"

# Copy the dashboard HTML as a resource
if [ -f "/Users/landonking/openclaw-army/dashboard/index.html" ]; then
  cp "/Users/landonking/openclaw-army/dashboard/index.html" "$APP_BUNDLE/Contents/Resources/dashboard.html"
  echo "Bundled dashboard.html"
fi

# Copy app icon
if [ -f "$SRC_DIR/AppIcon.icns" ]; then
  cp "$SRC_DIR/AppIcon.icns" "$APP_BUNDLE/Contents/Resources/AppIcon.icns"
  echo "Bundled AppIcon.icns"
fi

# Create PkgInfo
echo -n "APPL????" > "$APP_BUNDLE/Contents/PkgInfo"

echo ""
echo "=== Build complete ==="
echo "App: $APP_BUNDLE"
echo ""

# Verify
ls -la "$APP_BUNDLE/Contents/MacOS/"
echo ""
echo "To run: open '$APP_BUNDLE'"

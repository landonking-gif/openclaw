#!/bin/bash
set -e

# Build King AI macOS app
APP_DIR="/Users/landonking/openclaw-army/app"
SRC_DIR="$APP_DIR/OpenClawArmy"
BUILD_DIR="$APP_DIR/build"
APP_BUNDLE="$BUILD_DIR/King AI.app"

echo "=== Building King AI ==="

# Clean
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Create app bundle structure
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

# Copy Info.plist
cp "$SRC_DIR/Info.plist" "$APP_BUNDLE/Contents/"

# Resolve SDK path robustly. Prefer known locations first because xcrun can
# hang on some machines.
SDK_PATH=""
for CANDIDATE in \
  "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk" \
  "/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk"; do
  if [ -d "$CANDIDATE" ]; then
    SDK_PATH="$CANDIDATE"
    break
  fi
done

if [ -z "$SDK_PATH" ] && command -v xcrun >/dev/null 2>&1; then
  SDK_PATH="$(xcrun --show-sdk-path 2>/dev/null || true)"
fi

if [ -z "$SDK_PATH" ]; then
  echo "Error: Could not locate a macOS SDK."
  exit 1
fi

echo "Using SDK: $SDK_PATH"

# Compile Swift files
echo "Compiling Swift sources..."
swiftc \
  -o "$APP_BUNDLE/Contents/MacOS/KingAI" \
  -target arm64-apple-macosx14.0 \
  -sdk "$SDK_PATH" \
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

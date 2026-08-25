#!/bin/bash
set -e

NIGHTLIGHT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(command -v python3)"

echo "Installing Night Light from: $NIGHTLIGHT_DIR"

if [ -z "$PYTHON_BIN" ]; then
    echo "python3 not found. Install it first."
    exit 1
fi

if ! "$PYTHON_BIN" -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk" 2>/dev/null; then
    echo ""
    echo "Missing dependency: GTK3 Python bindings."
    echo "On Ubuntu/Debian, install with:"
    echo "  sudo apt install python3-gi gir1.2-gtk-3.0"
    exit 1
fi

if ! "$PYTHON_BIN" -c "from Xlib import display; from Xlib.ext import randr" 2>/dev/null; then
    echo ""
    echo "Missing dependency: python-xlib (needed for real gamma ramp control)."
    echo "On Ubuntu/Debian, install with:"
    echo "  sudo apt install python3-xlib"
    exit 1
fi

mkdir -p ~/.config/systemd/user

sed \
  -e "s|__NIGHTLIGHT_DIR__|$NIGHTLIGHT_DIR|g" \
  -e "s|__PYTHON__|$PYTHON_BIN|g" \
  "$NIGHTLIGHT_DIR/nightlight.service.template" > ~/.config/systemd/user/nightlight.service

systemctl --user daemon-reload
systemctl --user enable --now nightlight.service

mkdir -p ~/.local/share/applications
sed \
  -e "s|__NIGHTLIGHT_DIR__|$NIGHTLIGHT_DIR|g" \
  -e "s|__PYTHON__|$PYTHON_BIN|g" \
  "$NIGHTLIGHT_DIR/nightlight-preferences.desktop.template" > ~/.local/share/applications/nightlight-preferences.desktop

echo ""
echo "Night Light is installed and running in the background."
echo "\"Night Light Preferences\" should now appear in your app menu/Dash -"
echo "search for it there, and you can pin it to your launcher for quick access."
echo ""
echo "Right-click the tray icon for quick controls, or open the app menu entry"
echo "for full preferences."
echo ""
echo "Check it's running with:"
echo "  systemctl --user status nightlight.service"

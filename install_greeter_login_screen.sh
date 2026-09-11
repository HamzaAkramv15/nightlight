#!/usr/bin/env bash
# Optional add-on to Night Light: makes the LightDM login screen itself
# pick up your current color temperature the moment it appears, instead
# of only warming up once you've logged in.
#
# Kept separate from the main install.sh because this one needs root
# and edits LightDM's own config - the per-user daemon install stays
# untouched and doesn't need root at all.
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Run this with sudo: sudo ./install_greeter_login_screen.sh"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="/opt/nightlight"

if ! python3 -c "from Xlib import display; from Xlib.ext import randr" 2>/dev/null; then
  echo ""
  echo "Missing dependency: python3-xlib (needed on the system Python root uses too)."
  echo "  sudo apt install python3-xlib"
  exit 1
fi

mkdir -p "$TARGET_DIR"
cp "$SCRIPT_DIR/nightlight_common.py" "$TARGET_DIR/"
cp "$SCRIPT_DIR/nightlight_greeter_apply.py" "$TARGET_DIR/"
chmod +x "$TARGET_DIR/nightlight_greeter_apply.py"

CONF_DIR="/etc/lightdm/lightdm.conf.d"
mkdir -p "$CONF_DIR"
cat > "$CONF_DIR/60-nightlight-greeter.conf" <<EOF
[Seat:*]
greeter-setup-script=/usr/bin/python3 $TARGET_DIR/nightlight_greeter_apply.py
EOF

echo "Done."
echo ""
echo "The login screen will pick up your current Night Light temperature"
echo "the next time it appears (next logout, or restart LightDM now with:"
echo "  sudo systemctl restart lightdm"
echo "- this WILL kill your current graphical session, so save your work first)."
echo ""
echo "It reads settings from whichever user's ~/.config/nightlight/settings.json"
echo "it finds first under /home/*/. On a single-user machine like this one"
echo "that's automatic; set NIGHTLIGHT_SETTINGS_PATH in the .conf file above"
echo "if you ever need to force a specific user's settings."
echo ""
echo "To undo this: sudo rm $CONF_DIR/60-nightlight-greeter.conf"

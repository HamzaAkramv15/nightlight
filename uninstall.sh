#!/bin/bash
set -e

systemctl --user disable --now nightlight.service 2>/dev/null || true
rm -f ~/.config/systemd/user/nightlight.service
rm -f ~/.local/share/applications/nightlight-preferences.desktop
systemctl --user daemon-reload

echo "Night Light service stopped and removed (your screen has been reset to normal)."
echo ""
echo "Your settings were NOT deleted. To remove them too:"
echo "  ~/.config/nightlight/settings.json"

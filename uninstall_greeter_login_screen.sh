#!/usr/bin/env bash
# Undoes install_greeter_login_screen.sh - removes the LightDM greeter
# hook and the copy of the app it uses. Doesn't touch your per-user
# Night Light install (see the main uninstall.sh for that).
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Run this with sudo: sudo ./uninstall_greeter_login_screen.sh"
  exit 1
fi

rm -f /etc/lightdm/lightdm.conf.d/60-nightlight-greeter.conf
rm -rf /opt/nightlight

echo "Removed the login-screen Night Light hook. The greeter will show"
echo "its normal, unadjusted colors from the next time it appears."

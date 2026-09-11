#!/usr/bin/env python3
"""
Applies your current Night Light color temperature to the LightDM
login screen itself, once, right when the greeter's X server starts.

This is meant to be run by LightDM's `greeter-setup-script` hook (as
root, with DISPLAY already set) - see install_greeter_login_screen.sh,
not run manually.

It doesn't run a fade loop or keep ticking like the real daemon does -
the greeter is only on screen for a few seconds, so there's nothing to
gain from that. It just applies whichever temperature is correct for
right now, once, and steps out of the way. The instant you log in,
your normal per-session nightlight_daemon.py takes over completely
(it doesn't know or care that the greeter did anything first).
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nightlight_common as common  # noqa: E402


def find_user_settings():
    """The greeter runs as root before anyone has logged in, so it has
    no idea which user's settings to use yet. Rather than hardcoding a
    username, scan for the first real user's settings.json. Set
    NIGHTLIGHT_SETTINGS_PATH to override this (useful on a multi-user
    machine where auto-detection would guess wrong)."""
    override = os.environ.get("NIGHTLIGHT_SETTINGS_PATH")
    if override and os.path.exists(override):
        return override
    for path in sorted(glob.glob("/home/*/.config/nightlight/settings.json")):
        return path
    return None


def main():
    settings_path = find_user_settings()
    if not settings_path:
        # Nobody's configured Night Light yet - leave the greeter alone
        # rather than guessing at a temperature.
        return

    common.SETTINGS_FILE = settings_path
    common.SETTINGS_DIR = os.path.dirname(settings_path)
    settings = common.load_settings()

    target = 6500 if common.is_paused(settings) else common.compute_target_temp(settings)

    try:
        common.apply_temperature(target, settings.get("intensity", 1.0))
    except Exception as e:  # noqa: BLE001
        # A gamma failure here should never be able to block the login
        # screen from appearing - just log it and move on.
        print(f"nightlight greeter hook: could not apply temperature: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()

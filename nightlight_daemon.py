#!/usr/bin/env python3
"""
Night Light Daemon - runs in the background, continuously fades the
color temperature toward whatever the current mode/schedule says it
should be, applying it via a real X11 gamma ramp. Also hosts an
optional tray icon.

Every change - whether from the schedule crossing a time boundary, or
you manually changing something in the tray/Preferences - fades
smoothly toward the new target, rather than snapping instantly. The
tick runs every 100ms (10 times a second) specifically so the fade
looks like actual smooth motion, not a series of choppy jumps.

Run it with:
    python3 nightlight_daemon.py
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

AppIndicator3 = None
try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except (ImportError, ValueError):
    try:
        gi.require_version('AppIndicator3', '0.1')
        from gi.repository import AppIndicator3
    except (ImportError, ValueError):
        AppIndicator3 = None

import os
import subprocess

import nightlight_common as common

PREFS_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nightlight_settings.py")

TICK_MS = 100                # 10 steps/second - smooth, not choppy
KELVIN_STEP_PER_TICK = 150   # how far each step moves - controls fade speed

_current_temp = None
_target_temp = None
_last_settings = None
_mode_items = {}
_syncing_ui = False


def sync_tray_to_mode(mode):
    """Keep the tray menu's radio selection matching reality, even if
    the mode changed from Preferences or a manual settings.json edit."""
    global _syncing_ui
    item = _mode_items.get(mode)
    if item and not item.get_active():
        _syncing_ui = True
        item.set_active(True)
        _syncing_ui = False


def tick():
    global _current_temp, _target_temp, _last_settings

    settings = common.load_settings()
    new_target = common.compute_target_temp(settings)
    settings_changed = settings != _last_settings
    _last_settings = dict(settings)

    if _current_temp is None:
        # First run ever - nothing to fade from, jump straight there.
        _current_temp = new_target
        _target_temp = new_target
        common.apply_temperature(_current_temp, settings.get("intensity", 1.0))
        print(f"Applied {_current_temp}K (startup)")
        return True

    if settings_changed:
        sync_tray_to_mode(settings.get("mode", "off"))

    if new_target != _target_temp:
        _target_temp = new_target
        print(f"Fading toward {_target_temp}K...")

    if _current_temp != _target_temp:
        if _current_temp < _target_temp:
            _current_temp = min(_current_temp + KELVIN_STEP_PER_TICK, _target_temp)
        else:
            _current_temp = max(_current_temp - KELVIN_STEP_PER_TICK, _target_temp)
        common.apply_temperature(_current_temp, settings.get("intensity", 1.0))
        if _current_temp == _target_temp:
            print(f"Reached {_target_temp}K")

    return True


def on_mode_selected(menu_item, mode):
    if _syncing_ui:
        return
    if not menu_item.get_active():
        return
    settings = common.load_settings()
    settings["mode"] = mode
    common.save_settings(settings)
    # No direct apply here - the tick loop (running every 100ms) picks
    # this up almost immediately and fades smoothly toward it.


def on_preferences_clicked(_menu_item):
    subprocess.Popen(["python3", PREFS_SCRIPT])


def on_quit_clicked(_menu_item):
    common.reset()
    Gtk.main_quit()


def build_indicator():
    indicator = AppIndicator3.Indicator.new(
        "nightlight",
        "weather-clear-night-symbolic",
        AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
    )
    indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

    menu = Gtk.Menu()

    settings = common.load_settings()
    current_mode = settings.get("mode", "off")

    off_item = Gtk.RadioMenuItem(label="Off")
    on_item = Gtk.RadioMenuItem(label="Always On")
    on_item.join_group(off_item)
    schedule_item = Gtk.RadioMenuItem(label="Scheduled")
    schedule_item.join_group(off_item)

    items_by_mode = {"off": off_item, "on": on_item, "schedule": schedule_item}
    items_by_mode[current_mode].set_active(True)
    _mode_items.update(items_by_mode)

    for mode_value, item in items_by_mode.items():
        item.connect("toggled", on_mode_selected, mode_value)
        menu.append(item)

    menu.append(Gtk.SeparatorMenuItem())

    prefs_item = Gtk.MenuItem(label="Preferences...")
    prefs_item.connect("activate", on_preferences_clicked)
    menu.append(prefs_item)

    menu.append(Gtk.SeparatorMenuItem())

    quit_item = Gtk.MenuItem(label="Quit")
    quit_item.connect("activate", on_quit_clicked)
    menu.append(quit_item)

    menu.show_all()
    indicator.set_menu(menu)
    return indicator


def main():
    tick()  # apply immediately on startup
    GLib.timeout_add(TICK_MS, tick)

    indicator = None
    if AppIndicator3 is not None:
        indicator = build_indicator()
        print("Night Light daemon running, with a tray icon.")
    else:
        print(
            "Night Light daemon running WITHOUT a tray icon "
            "(AyatanaAppIndicator3/AppIndicator3 not found). "
            "Everything else still works."
        )

    Gtk.main()


if __name__ == "__main__":
    main()

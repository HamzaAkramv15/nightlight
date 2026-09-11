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
looks like actual smooth motion, not a series of choppy jumps. How
long a fade actually takes is configurable (settings["transition_seconds"]).

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
import sys

import nightlight_common as common

PREFS_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nightlight_settings.py")

TICK_MS = 100  # 10 steps/second - smooth, not choppy

_current_temp = None
_current_intensity = None
_target_temp = None
_target_intensity = None
_last_settings = None
_mode_items = {}
_syncing_ui = False
_status_item = None


def sync_tray_to_mode(mode):
    """Keep the tray menu's radio selection matching reality, even if
    the mode changed from Preferences or a manual settings.json edit."""
    global _syncing_ui
    item = _mode_items.get(mode)
    if item and not item.get_active():
        _syncing_ui = True
        item.set_active(True)
        _syncing_ui = False


def update_status_label(settings, effective_temp, paused):
    if _status_item is None:
        return
    mode_names = {"off": "Off", "on": "Always On", "schedule": "Scheduled"}
    mode_label = mode_names.get(settings.get("mode", "off"), "Off")
    if paused:
        text = f"Night Light: Paused ({mode_label} resumes after)"
    else:
        label = common.kelvin_to_label(effective_temp)
        text = f"Night Light: {mode_label} - {effective_temp}K ({label})"
    _status_item.set_label(text)


def tick():
    global _current_temp, _current_intensity, _target_temp, _target_intensity, _last_settings

    settings = common.load_settings()
    paused = common.is_paused(settings)
    new_target_temp = 6500 if paused else common.compute_target_temp(settings)
    new_target_intensity = settings.get("intensity", 1.0)
    settings_changed = settings != _last_settings
    _last_settings = dict(settings)

    step_per_tick = common.compute_step_per_tick(
        settings.get("transition_seconds", 2), TICK_MS
    )

    if _current_temp is None:
        # First run ever - nothing to fade from, jump straight there.
        _current_temp = new_target_temp
        _target_temp = new_target_temp
        _current_intensity = new_target_intensity
        _target_intensity = new_target_intensity
        common.apply_temperature(_current_temp, _current_intensity)
        update_status_label(settings, _current_temp, paused)
        print(f"Applied {_current_temp}K @ intensity {_current_intensity} (startup)")
        return True

    if settings_changed:
        sync_tray_to_mode(settings.get("mode", "off"))

    if new_target_temp != _target_temp:
        _target_temp = new_target_temp
        print(f"Fading toward {_target_temp}K...")

    # Intensity isn't faded like temperature - it's a direct multiplier,
    # so there's nothing to visually "fade" between old and new strength.
    # It just needs to actually get re-applied.
    _target_intensity = new_target_intensity

    temp_changed = False
    if _current_temp != _target_temp:
        if _current_temp < _target_temp:
            _current_temp = min(_current_temp + step_per_tick, _target_temp)
        else:
            _current_temp = max(_current_temp - step_per_tick, _target_temp)
        temp_changed = True

    intensity_changed = _current_intensity != _target_intensity
    if intensity_changed:
        _current_intensity = _target_intensity

    if temp_changed or intensity_changed or settings_changed:
        common.apply_temperature(_current_temp, _current_intensity)
        update_status_label(settings, _current_temp, paused)
        if _current_temp == _target_temp and not intensity_changed:
            print(f"Reached {_target_temp}K")

    return True


def on_mode_selected(menu_item, mode):
    if _syncing_ui:
        return
    if not menu_item.get_active():
        return
    settings = common.load_settings()
    settings["mode"] = mode
    common.clear_pause(settings)  # switching modes explicitly cancels any pause
    common.save_settings(settings)
    # No direct apply here - the tick loop (running every 100ms) picks
    # this up almost immediately and fades smoothly toward it.


def on_pause_selected(_menu_item, minutes):
    common.set_pause(minutes)


def on_resume_selected(_menu_item):
    common.clear_pause()


def on_night_temp_preset(_menu_item, kelvin):
    settings = common.load_settings()
    settings["night_temp"] = kelvin
    common.save_settings(settings)


def on_intensity_preset(_menu_item, value):
    settings = common.load_settings()
    settings["intensity"] = value
    common.save_settings(settings)


def on_preferences_clicked(_menu_item):
    subprocess.Popen(["python3", PREFS_SCRIPT])


def on_quit_clicked(_menu_item):
    common.reset()
    Gtk.main_quit()


def build_indicator():
    global _status_item

    indicator = AppIndicator3.Indicator.new(
        "nightlight",
        "weather-clear-night-symbolic",
        AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
    )
    indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

    menu = Gtk.Menu()

    settings = common.load_settings()
    current_mode = settings.get("mode", "off")

    _status_item = Gtk.MenuItem(label="Night Light")
    _status_item.set_sensitive(False)
    menu.append(_status_item)
    menu.append(Gtk.SeparatorMenuItem())

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

    # Quick night-temperature presets - no need to open Preferences just
    # to try a different warmth.
    temp_menu_item = Gtk.MenuItem(label="Night Temperature")
    temp_submenu = Gtk.Menu()
    for label, kelvin in (("Very Warm (2700K)", 2700), ("Warm (3000K)", 3000),
                          ("Default (3400K)", 3400), ("Slightly Warm (4000K)", 4000),
                          ("Mild (4500K)", 4500)):
        item = Gtk.MenuItem(label=label)
        item.connect("activate", on_night_temp_preset, kelvin)
        temp_submenu.append(item)
    temp_menu_item.set_submenu(temp_submenu)
    menu.append(temp_menu_item)

    # Quick intensity presets, same idea.
    intensity_menu_item = Gtk.MenuItem(label="Intensity")
    intensity_submenu = Gtk.Menu()
    for label, value in (("25%", 0.25), ("50%", 0.5), ("75%", 0.75), ("100%", 1.0)):
        item = Gtk.MenuItem(label=label)
        item.connect("activate", on_intensity_preset, value)
        intensity_submenu.append(item)
    intensity_menu_item.set_submenu(intensity_submenu)
    menu.append(intensity_menu_item)

    # Pause - force neutral temporarily without changing the saved mode,
    # so "Scheduled" resumes exactly as configured once the pause ends.
    pause_menu_item = Gtk.MenuItem(label="Pause")
    pause_submenu = Gtk.Menu()
    for label, minutes in (("15 minutes", 15), ("30 minutes", 30), ("1 hour", 60)):
        item = Gtk.MenuItem(label=label)
        item.connect("activate", on_pause_selected, minutes)
        pause_submenu.append(item)
    pause_submenu.append(Gtk.SeparatorMenuItem())
    resume_item = Gtk.MenuItem(label="Resume now")
    resume_item.connect("activate", on_resume_selected)
    pause_submenu.append(resume_item)
    pause_menu_item.set_submenu(pause_submenu)
    menu.append(pause_menu_item)

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
    lock = common.acquire_single_instance_lock()
    if lock is None:
        print(
            "Night Light daemon is already running (lock held at "
            f"{common._LOCK_FILE}). Not starting a second copy - two "
            "daemons fighting over the same gamma ramps would cause "
            "flickering/undefined behavior.",
            file=sys.stderr,
        )
        sys.exit(1)
    # Keep a reference so the lock isn't released by garbage collection -
    # it lives for the rest of the process, same lifetime as `lock` itself.
    globals()["_instance_lock"] = lock

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

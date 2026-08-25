#!/usr/bin/env python3
"""
Night Light Preferences window - lets you set the mode, both
temperatures, and the schedule times. Launched on-demand from the
tray icon's "Preferences..." item.

Run it with:
    python3 nightlight_settings.py
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

import nightlight_common as common


def from_24h(text):
    """'19:00' -> (7, 0, 'PM'). '07:00' -> (7, 0, 'AM')."""
    h, m = text.strip().split(":")
    h, m = int(h), int(m)
    ampm = "AM" if h < 12 else "PM"
    hour_12 = h % 12
    if hour_12 == 0:
        hour_12 = 12
    return hour_12, m, ampm


def to_24h(hour_12, minute, ampm):
    """(7, 0, 'PM') -> '19:00'. (7, 0, 'AM') -> '07:00'."""
    hour_12 = int(hour_12)
    if ampm == "AM":
        hour_24 = 0 if hour_12 == 12 else hour_12
    else:
        hour_24 = 12 if hour_12 == 12 else hour_12 + 12
    return f"{hour_24:02d}:{int(minute):02d}"


class SettingsWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Night Light Preferences")
        self.set_default_size(340, 340)
        self.set_border_width(12)

        self.settings = common.load_settings()

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(vbox)

        vbox.pack_start(Gtk.Label(label="Mode", xalign=0), False, False, 0)

        self.off_radio = Gtk.RadioButton.new_with_label(None, "Off")
        self.on_radio = Gtk.RadioButton.new_with_label_from_widget(self.off_radio, "Always On")
        self.schedule_radio = Gtk.RadioButton.new_with_label_from_widget(self.off_radio, "Scheduled")
        for radio in (self.off_radio, self.on_radio, self.schedule_radio):
            vbox.pack_start(radio, False, False, 0)

        mode_to_radio = {
            "off": self.off_radio,
            "on": self.on_radio,
            "schedule": self.schedule_radio,
        }
        mode_to_radio[self.settings.get("mode", "off")].set_active(True)

        vbox.pack_start(Gtk.Separator(), False, False, 4)

        grid = Gtk.Grid(column_spacing=8, row_spacing=6)
        vbox.pack_start(grid, False, False, 0)

        grid.attach(Gtk.Label(label="Night temperature (K)", xalign=0), 0, 0, 1, 1)
        self.night_spin = Gtk.SpinButton()
        self.night_spin.set_range(1000, 10000)
        self.night_spin.set_increments(100, 500)
        self.night_spin.set_value(self.settings.get("night_temp", 3400))
        grid.attach(self.night_spin, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label="Start time", xalign=0), 0, 1, 1, 1)
        start_hour, start_minute, start_ampm, start_box = self.build_time_picker(
            self.settings.get("schedule_start", "19:00")
        )
        self.start_hour, self.start_minute, self.start_ampm = start_hour, start_minute, start_ampm
        grid.attach(start_box, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label="End time", xalign=0), 0, 2, 1, 1)
        end_hour, end_minute, end_ampm, end_box = self.build_time_picker(
            self.settings.get("schedule_end", "07:00")
        )
        self.end_hour, self.end_minute, self.end_ampm = end_hour, end_minute, end_ampm
        grid.attach(end_box, 1, 2, 1, 1)

        grid.attach(Gtk.Label(label="Intensity", xalign=0), 0, 3, 1, 1)
        self.intensity_spin = Gtk.SpinButton()
        self.intensity_spin.set_range(0.0, 2.0)
        self.intensity_spin.set_digits(2)
        self.intensity_spin.set_increments(0.1, 0.5)
        self.intensity_spin.set_value(self.settings.get("intensity", 1.0))
        grid.attach(self.intensity_spin, 1, 3, 1, 1)

        # Keep references so we can hide these unless "Scheduled" is picked.
        self.start_label = grid.get_child_at(0, 1)
        self.end_label = grid.get_child_at(0, 2)
        self.schedule_widgets = [self.start_label, start_box, self.end_label, end_box]

        for radio in (self.off_radio, self.on_radio, self.schedule_radio):
            radio.connect("toggled", self.on_mode_toggled)

        self.error_label = Gtk.Label(label="")
        vbox.pack_start(self.error_label, False, False, 0)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        vbox.pack_start(button_box, False, False, 8)

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda b: self.destroy())
        button_box.pack_start(cancel_button, True, True, 0)

        save_button = Gtk.Button(label="Save")
        save_button.connect("clicked", self.on_save_clicked)
        button_box.pack_start(save_button, True, True, 0)

        self.show_all()
        self.on_mode_toggled(None)  # sync visibility to whatever mode was loaded

    def build_time_picker(self, initial_24h_text):
        """Builds an hour/minute/AM-PM row, pre-filled from a stored
        24-hour 'HH:MM' string. Returns the three widgets plus the
        box containing them."""
        hour_12, minute, ampm = from_24h(initial_24h_text)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        hour_spin = Gtk.SpinButton()
        hour_spin.set_range(1, 12)
        hour_spin.set_increments(1, 1)
        hour_spin.set_numeric(True)
        hour_spin.set_value(hour_12)
        box.pack_start(hour_spin, False, False, 0)

        box.pack_start(Gtk.Label(label=":"), False, False, 0)

        minute_spin = Gtk.SpinButton()
        minute_spin.set_range(0, 59)
        minute_spin.set_increments(1, 5)
        minute_spin.set_numeric(True)
        minute_spin.set_value(minute)
        minute_spin.connect("output", self._format_two_digits)
        box.pack_start(minute_spin, False, False, 0)

        ampm_combo = Gtk.ComboBoxText()
        ampm_combo.append_text("AM")
        ampm_combo.append_text("PM")
        ampm_combo.set_active(0 if ampm == "AM" else 1)
        box.pack_start(ampm_combo, False, False, 0)

        return hour_spin, minute_spin, ampm_combo, box

    def _format_two_digits(self, spin_button):
        spin_button.set_text(f"{int(spin_button.get_value()):02d}")
        return True

    def on_mode_toggled(self, button):
        is_schedule = self.schedule_radio.get_active()
        for widget in self.schedule_widgets:
            widget.set_visible(is_schedule)

    def on_save_clicked(self, button):
        start_text = to_24h(self.start_hour.get_value(), self.start_minute.get_value(), self.start_ampm.get_active_text())
        end_text = to_24h(self.end_hour.get_value(), self.end_minute.get_value(), self.end_ampm.get_active_text())

        if self.off_radio.get_active():
            mode = "off"
        elif self.on_radio.get_active():
            mode = "on"
        else:
            mode = "schedule"

        self.settings["mode"] = mode
        self.settings["night_temp"] = int(self.night_spin.get_value())
        self.settings["schedule_start"] = start_text
        self.settings["schedule_end"] = end_text
        self.settings["intensity"] = round(self.intensity_spin.get_value(), 2)

        common.save_settings(self.settings)
        # Don't apply directly here - the daemon's own fade loop will
        # pick this up within a couple seconds and transition to it
        # smoothly. Applying here too could cause a visible jump if
        # it doesn't match wherever the daemon's own fade currently is.

        self.destroy()


def main():
    window = SettingsWindow()
    window.connect("destroy", Gtk.main_quit)
    Gtk.main()


if __name__ == "__main__":
    main()

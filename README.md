# Night Light

A lightweight, fully manual color-temperature (blue-light-reduction) tool for X11 Linux desktops. Built and tested on Ubuntu Unity.

## Features

- Real X11 gamma-ramp based color adjustment - the same underlying mechanism Redshift uses, not the cruder `xrandr --gamma` exponent shortcut (using that as a simple multiplier produces visibly wrong colors - discovered the hard way during development, see "How it works" below)
- Uses Redshift's actual published white-point color table, not a reconstructed approximation, and works correctly across its full 1000-10000K range (both the warm night side and the cooler day side)
- Three modes: Off, Always On, Scheduled - with independently configurable Day and Night temperatures for Scheduled mode
- Every temperature change - automatic schedule transitions or manual tweaks - fades smoothly, not an instant jarring snap; how fast is configurable (Instant / 2s / 10s / 30s / 1 min)
- Intensity changes (unlike temperature) apply immediately, since there's nothing to visually fade between strengths
- **Pause** for 15/30/60 minutes from the tray without changing your saved mode - Scheduled mode resumes exactly as configured once the pause ends
- Quick temperature and intensity presets right in the tray menu - no need to open Preferences for a quick change
- Tray shows live status (mode, current temperature, and a human label like "Warm" or "Very Warm") at a glance
- Tray icon that stays in sync with Preferences, however you change the mode
- Full preferences window with a proper AM/PM time picker and human-readable temperature labels next to the raw Kelvin values
- Shows up as a real app in your Dash/app menu
- Configuration via plain `settings.json` - no code editing needed, changes apply within ~100ms. Writes are atomic (a crash mid-save can't corrupt it), and a corrupted file is preserved as `.broken` and recovered from rather than silently discarded
- Only one daemon can run at a time (file-locked) - a second copy refuses to start rather than fighting the first one over the same gamma ramps
- Automated test suite covering all the pure logic (schedule math, color interpolation, settings persistence, pause timing) - runs without needing a real display, see `tests/`

## Not included (yet)

Deliberately out of scope for this round - each is its own sub-project: sunrise/sunset-based scheduling (needs location data and its own privacy design), per-monitor settings, a live-preview slider while dragging, a Wayland backend, a CLI/D-Bus interface, and app-specific or weekday/weekend profiles.

## Requirements

- Python 3
- GTK3 + PyGObject (`python3-gi`, `gir1.2-gtk-3.0`)
- `python3-xlib` - for real gamma ramp control via X11's RandR extension
- **Optional**, for the tray icon: `gir1.2-ayatanaappindicator3-0.1` or `gir1.2-appindicator3-0.1`. Without either, Night Light still works fully - you just won't see a panel icon, and can control it entirely through the Preferences window.

**On Ubuntu MATE specifically**: the MATE panel doesn't show AppIndicator tray icons out of the box the way Unity did. Add the **"Indicator Applet Complete"** applet to your panel once (right-click the panel -> Add to Panel... -> search "Indicator") and the Night Light tray icon will appear there. This is a one-time panel setup step, not something the install script can do for you.

On Ubuntu/Debian:
```bash
sudo apt install python3-gi gir1.2-gtk-3.0 python3-xlib gir1.2-ayatanaappindicator3-0.1
```

## Install

```bash
git clone https://github.com/HamzaAkramv15/nightlight.git
cd nightlight
chmod +x install.sh uninstall.sh
./install.sh
```

This sets up a background service that starts automatically on login, and adds a "Night Light Preferences" entry to your app menu.

## Setting a keyboard shortcut

Night Light deliberately doesn't bind a global hotkey on its own - a script silently grabbing system-wide keys would be a bad idea. You assign one yourself, once, using your desktop's own shortcut settings. `install.sh` prints the exact command to use at the end - it'll look something like this:

- **Unity / GNOME / MATE**: `Settings -> Keyboard -> Shortcuts -> Custom Shortcuts -> (+)` (in MATE: `MATE Control Center -> Keyboard Shortcuts -> Add`)
  - Command: exactly what `install.sh` printed (something like `/usr/bin/python3 /home/you/nightlight/nightlight_settings.py`)
  - Assign any key combo, e.g. `Super+N`
- **KDE**: `System Settings -> Shortcuts -> Custom Shortcuts`, same command
- **Other window managers** (i3, sway, etc.): bind the same command in your WM's own config, or via a tool like `xbindkeys`

This opens the full Preferences window - mode, temperature, schedule, intensity - not a quick-toggle popup.

## Usage

- **Tray icon** (if present): right-click for Off / Always On / Scheduled, Preferences, or Quit
- **Or** search "Night Light Preferences" in your app menu/Dash
- **Scheduled mode**: pick a night temperature and a start/end time - warm during that window, back to your chosen day temperature outside it
- **Always On**: applies your chosen night temperature all the time, regardless of clock
- Every temperature change fades smoothly over a couple of seconds rather than snapping instantly; intensity changes apply immediately (there's nothing to visually fade between strengths)

## Configuration

Edit `~/.config/nightlight/settings.json` directly, or use the Preferences window - both work, and changes apply almost immediately either way:

```json
{
  "mode": "schedule",
  "night_temp": 3400,
  "day_temp": 6500,
  "schedule_start": "19:00",
  "schedule_end": "07:00",
  "intensity": 1.0,
  "transition_seconds": 2,
  "pause_until": null
}
```

`night_temp` and `day_temp` both work across the full 1000-10000K range - values above 6500K shift the screen cooler/bluer rather than staying flat neutral, using the same interpolated table as the warm side.

`intensity` scales how strong the effect is relative to neutral: `1.0` is Redshift's real values, lower is subtler, higher is stronger (automatically clamped to stay within a valid range no matter how high you set it).

`transition_seconds` controls how long a typical day/night fade takes; `0` means instant (no visible fade).

`pause_until` is normally managed for you via the tray's Pause menu - it's an ISO timestamp string, and self-clears once it passes, so you shouldn't need to touch it directly.

## Running the tests

```bash
python3 -m unittest tests/test_nightlight_common.py -v
```

Covers schedule math (including midnight-crossing schedules), the color-temperature table (including the 6500-10000K range), fade-speed calculation, and settings persistence (atomic writes, corrupted-file recovery, pause timing, single-instance locking). All of it runs without a real X11 display, so it's safe to run anywhere, including CI.

## Uninstall

```bash
./uninstall.sh
```

Resets your screen to normal, then stops and removes the background service and app launcher entry. Your `settings.json` isn't deleted automatically.

## How it works (for the curious)

Most simple night-light scripts use `xrandr --output X --gamma R:G:B`. That interface takes gamma **exponents** (a power curve), not brightness multipliers - treating it as a simple "65% blue" multiplier produces genuinely wrong, inconsistent colors across shadows/midtones/highlights. This was confirmed directly during development: setting a channel's gamma to `3.0` made it *brighter*, not dimmer, proving the exponent behavior firsthand rather than assuming it.

Instead, `nightlight_common.py` builds a full 256+ entry gamma ramp per color channel and loads it directly via X11's RandR extension through `python-xlib` - the same fundamental technique Redshift itself uses. The white-point table is Redshift's real published data (from its `colorramp.c` source), not a reconstructed approximation.

The daemon ticks 10 times a second, continuously fading toward whatever the current mode/schedule says the target should be - both automatic schedule transitions and manual changes go through the identical fade path, for a consistent feel.

## Known limitations

- X11 only. This technique doesn't carry over to Wayland, which handles color through an entirely different protocol.
- Schedule times are fixed clock times you set yourself - no automatic sunrise/sunset calculation based on location.

## License

MIT - see [LICENSE](LICENSE).

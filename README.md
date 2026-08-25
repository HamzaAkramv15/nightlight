# Night Light

A lightweight, fully manual color-temperature (blue-light-reduction) tool for X11 Linux desktops. Built and tested on Ubuntu Unity.

## Features

- Real X11 gamma-ramp based color adjustment - the same underlying mechanism Redshift uses, not the cruder `xrandr --gamma` exponent shortcut (using that as a simple multiplier produces visibly wrong colors - discovered the hard way during development, see "How it works" below)
- Uses Redshift's actual published white-point color table, not a reconstructed approximation
- Three modes: Off, Always On, Scheduled
- Every change - automatic schedule transitions or manual tweaks - fades smoothly (10 steps/second), not an instant jarring snap
- Adjustable intensity
- Tray icon that stays in sync with Preferences, however you change the mode
- Full preferences window with a proper AM/PM time picker
- Shows up as a real app in your Dash/app menu
- Configuration via plain `settings.json` - no code editing needed, changes apply within ~100ms

## Requirements

- Python 3
- GTK3 + PyGObject (`python3-gi`, `gir1.2-gtk-3.0`)
- `python3-xlib` - for real gamma ramp control via X11's RandR extension
- **Optional**, for the tray icon: `gir1.2-ayatanaappindicator3-0.1` or `gir1.2-appindicator3-0.1`. Without either, Night Light still works fully - you just won't see a panel icon, and can control it entirely through the Preferences window.

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

## Usage

- **Tray icon** (if present): right-click for Off / Always On / Scheduled, Preferences, or Quit
- **Or** search "Night Light Preferences" in your app menu/Dash
- **Scheduled mode**: pick a night temperature and a start/end time - warm during that window, fully off (neutral) outside it
- **Always On**: applies your chosen night temperature all the time, regardless of clock
- Every change fades smoothly over a couple of seconds rather than snapping instantly

## Configuration

Edit `~/.config/nightlight/settings.json` directly, or use the Preferences window - both work, and changes apply almost immediately either way:

```json
{
  "mode": "schedule",
  "night_temp": 3400,
  "schedule_start": "19:00",
  "schedule_end": "07:00",
  "intensity": 1.0
}
```

`intensity` scales how strong the warm effect is: `1.0` is Redshift's real values, lower is subtler, higher is stronger (automatically clamped to stay within a valid range no matter how high you set it).

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

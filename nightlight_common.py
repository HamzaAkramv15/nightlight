"""
Shared code for Night Light: settings, and applying color temperature
via a real X11 RandR gamma RAMP (not the blunt xrandr --gamma
exponent shortcut, which is a fundamentally different, less precise
operation - see the README for why).

The white-point table below is Redshift's actual published table
(from src/colorramp.c), not an approximation - it's real measured/
calculated blackbody data, sampled at 100K intervals from 1000K to
10000K.
"""
import fcntl
import json
import os
from datetime import datetime, timedelta, time as dtime

SETTINGS_DIR = os.path.expanduser("~/.config/nightlight")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
_LOCK_FILE = os.path.join(SETTINGS_DIR, "daemon.lock")

DEFAULT_SETTINGS = {
    "mode": "off",
    "night_temp": 3400,
    "day_temp": 6500,
    "schedule_start": "19:00",
    "schedule_end": "07:00",
    "intensity": 1.0,       # 1.0 = Redshift's real values, lower = subtler, higher = stronger
    "transition_seconds": 2,  # how long a typical day<->night fade takes; 0 = instant
    "pause_until": None,    # ISO timestamp string, or None - see set_pause()/is_paused()
}

# Redshift's real white-point table (R, G, B as 0.0-1.0 multipliers),
# one entry per 100K starting at 1000K. Source: redshift/src/colorramp.c
_TABLE_START_K = 1000
_TABLE_STEP_K = 100
_BLACKBODY_TABLE = [
    (1.00000000, 0.18172716, 0.00000000),
    (1.00000000, 0.25503671, 0.00000000),
    (1.00000000, 0.30942099, 0.00000000),
    (1.00000000, 0.35357379, 0.00000000),
    (1.00000000, 0.39091524, 0.00000000),
    (1.00000000, 0.42322816, 0.00000000),
    (1.00000000, 0.45159884, 0.00000000),
    (1.00000000, 0.47675916, 0.00000000),
    (1.00000000, 0.49923747, 0.00000000),
    (1.00000000, 0.51943421, 0.00000000),
    (1.00000000, 0.54360078, 0.08679949),
    (1.00000000, 0.56618736, 0.14065513),
    (1.00000000, 0.58734976, 0.18362641),
    (1.00000000, 0.60724493, 0.22137978),
    (1.00000000, 0.62600248, 0.25591950),
    (1.00000000, 0.64373109, 0.28819679),
    (1.00000000, 0.66052319, 0.31873863),
    (1.00000000, 0.67645822, 0.34786758),
    (1.00000000, 0.69160518, 0.37579588),
    (1.00000000, 0.70602449, 0.40267128),
    (1.00000000, 0.71976951, 0.42860152),
    (1.00000000, 0.73288760, 0.45366838),
    (1.00000000, 0.74542112, 0.47793608),
    (1.00000000, 0.75740814, 0.50145662),
    (1.00000000, 0.76888303, 0.52427322),  # 3400K
    (1.00000000, 0.77987699, 0.54642268),
    (1.00000000, 0.79041843, 0.56793692),
    (1.00000000, 0.80053332, 0.58884417),
    (1.00000000, 0.81024551, 0.60916971),
    (1.00000000, 0.81957693, 0.62893653),
    (1.00000000, 0.82854786, 0.64816570),
    (1.00000000, 0.83717703, 0.66687674),
    (1.00000000, 0.84548188, 0.68508786),
    (1.00000000, 0.85347859, 0.70281616),
    (1.00000000, 0.86118227, 0.72007777),
    (1.00000000, 0.86860704, 0.73688797),
    (1.00000000, 0.87576611, 0.75326132),
    (1.00000000, 0.88267187, 0.76921169),
    (1.00000000, 0.88933596, 0.78475236),
    (1.00000000, 0.89576933, 0.79989606),
    (1.00000000, 0.90198230, 0.81465502),
    (1.00000000, 0.90963069, 0.82838210),
    (1.00000000, 0.91710889, 0.84190889),
    (1.00000000, 0.92441842, 0.85523742),
    (1.00000000, 0.93156127, 0.86836903),
    (1.00000000, 0.93853986, 0.88130458),
    (1.00000000, 0.94535695, 0.89404470),
    (1.00000000, 0.95201559, 0.90658983),
    (1.00000000, 0.95851906, 0.91894041),
    (1.00000000, 0.96487079, 0.93109690),
    (1.00000000, 0.97107439, 0.94305985),
    (1.00000000, 0.97713351, 0.95482993),
    (1.00000000, 0.98305189, 0.96640795),
    (1.00000000, 0.98883326, 0.97779486),
    (1.00000000, 0.99448139, 0.98899179),
    (1.00000000, 1.00000000, 1.00000000),  # 6500K - neutral
    (0.98947904, 0.99348723, 1.00000000),
    (0.97940448, 0.98722715, 1.00000000),
    (0.96975025, 0.98120637, 1.00000000),
    (0.96049223, 0.97541240, 1.00000000),
    (0.95160805, 0.96983355, 1.00000000),
    (0.94303638, 0.96443333, 1.00000000),
    (0.93480451, 0.95923080, 1.00000000),
    (0.92689056, 0.95421394, 1.00000000),
    (0.91927697, 0.94937330, 1.00000000),
    (0.91194747, 0.94470005, 1.00000000),
    (0.90488690, 0.94018594, 1.00000000),
    (0.89808115, 0.93582323, 1.00000000),
    (0.89151710, 0.93160469, 1.00000000),
    (0.88518247, 0.92752354, 1.00000000),
    (0.87906581, 0.92357340, 1.00000000),
    (0.87315640, 0.91974827, 1.00000000),
    (0.86744421, 0.91604254, 1.00000000),
    (0.86191983, 0.91245088, 1.00000000),
    (0.85657444, 0.90896831, 1.00000000),
    (0.85139976, 0.90559011, 1.00000000),
    (0.84638799, 0.90231183, 1.00000000),
    (0.84153180, 0.89912926, 1.00000000),
    (0.83682430, 0.89603843, 1.00000000),
    (0.83225897, 0.89303558, 1.00000000),
    (0.82782969, 0.89011714, 1.00000000),
    (0.82353066, 0.88727974, 1.00000000),
    (0.81935641, 0.88452017, 1.00000000),
    (0.81530175, 0.88183541, 1.00000000),
    (0.81136180, 0.87922257, 1.00000000),
    (0.80753191, 0.87667891, 1.00000000),
    (0.80380769, 0.87420182, 1.00000000),
    (0.80018497, 0.87178882, 1.00000000),
    (0.79665980, 0.86943756, 1.00000000),
    (0.79322843, 0.86714579, 1.00000000),
    (0.78988728, 0.86491137, 1.00000000),  # 10000K
]
_TABLE_MAX_K = _TABLE_START_K + (len(_BLACKBODY_TABLE) - 1) * _TABLE_STEP_K


def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r") as f:
            saved = json.load(f)
    except (json.JSONDecodeError, OSError):
        # Preserve the broken file for inspection instead of silently
        # discarding whatever was in it, then recover with fresh defaults
        # so the daemon/settings window still start up cleanly.
        try:
            os.replace(SETTINGS_FILE, SETTINGS_FILE + ".broken")
        except OSError:
            pass
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)
    settings = dict(DEFAULT_SETTINGS)
    settings.update(saved)
    return settings


def save_settings(settings):
    """Atomic write: write to a temp file, fsync, then rename over the
    real file. os.replace() is atomic on POSIX, so a crash or power loss
    mid-write can never leave settings.json truncated or half-written -
    worst case, the tmp file is orphaned and the previous good file is
    untouched."""
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    tmp_path = SETTINGS_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, SETTINGS_FILE)


def acquire_single_instance_lock():
    """Returns an open file handle holding an exclusive lock if this is
    the only Night Light daemon running, or None if another instance
    already holds it. The caller must keep the returned handle alive
    for the process's entire lifetime (the lock releases automatically
    when the file descriptor closes, e.g. on process exit) - don't let
    it get garbage collected early."""
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    lock_handle = open(_LOCK_FILE, "w")
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_handle.close()
        return None
    lock_handle.write(str(os.getpid()))
    lock_handle.flush()
    return lock_handle


def set_pause(minutes):
    """Temporarily force neutral (no adjustment) for `minutes`, regardless
    of the current mode. Automatically expires - see is_paused()."""
    settings = load_settings()
    until = datetime.now() + timedelta(minutes=minutes)
    settings["pause_until"] = until.isoformat()
    save_settings(settings)


def clear_pause(settings=None):
    """Ends an active pause immediately. Pass an already-loaded settings
    dict to avoid a redundant load_settings() call when the caller has
    one handy; otherwise loads and saves on its own."""
    owns_settings = settings is None
    if owns_settings:
        settings = load_settings()
    if settings.get("pause_until"):
        settings["pause_until"] = None
        if owns_settings:
            save_settings(settings)
    return settings


def is_paused(settings):
    """Checks (and self-expires) an active pause. Returns True if a pause
    is currently in effect. If the stored pause_until has already passed,
    clears it and persists that - so tray/UI state doesn't stay stuck
    showing "Paused" forever after the timer actually ran out."""
    pause_until = settings.get("pause_until")
    if not pause_until:
        return False
    try:
        until = datetime.fromisoformat(pause_until)
    except ValueError:
        settings["pause_until"] = None
        save_settings(settings)
        return False
    if datetime.now() >= until:
        settings["pause_until"] = None
        save_settings(settings)
        return False
    return True


def is_valid_time(text):
    try:
        h, m = text.strip().split(":")
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59
    except (ValueError, AttributeError):
        return False


def parse_time(text):
    h, m = text.strip().split(":")
    return dtime(int(h), int(m))


def compute_target_temp(settings):
    mode = settings.get("mode", "off")

    if mode == "on":
        return settings.get("night_temp", 3400)

    if mode == "schedule":
        now = datetime.now().time()
        start = parse_time(settings.get("schedule_start", "19:00"))
        end = parse_time(settings.get("schedule_end", "07:00"))
        if start <= end:
            in_night_window = start <= now <= end
        else:
            in_night_window = now >= start or now <= end
        return (
            settings.get("night_temp", 3400)
            if in_night_window
            else settings.get("day_temp", 6500)
        )

    return 6500


# A "typical" day<->night swing (roughly 6500K to 3400K) used as the
# reference distance for turning a human "X seconds" fade-speed setting
# into a per-tick Kelvin step. It's a reference point, not a hard limit -
# actual fades (e.g. day_temp to night_temp) can be shorter or longer than
# this and will simply take proportionally less/more time at the same step.
_REFERENCE_SWING_K = 3100


def compute_step_per_tick(transition_seconds, tick_ms=100):
    """How many Kelvin to move per daemon tick to make a ~_REFERENCE_SWING_K
    fade take about `transition_seconds` seconds. transition_seconds <= 0
    means "instant" - a single tick covers any realistic gap."""
    if not transition_seconds or transition_seconds <= 0:
        return 20000
    ticks = max(1, transition_seconds * (1000 / tick_ms))
    return max(1, round(_REFERENCE_SWING_K / ticks))


def kelvin_to_label(kelvin):
    """Human-friendly description of a Kelvin value, for display next to
    the raw number in the UI/tray - most people think "warm", not "3800K"."""
    if kelvin >= 8000:
        return "Very Cool"
    if kelvin >= 6700:
        return "Cool"
    if kelvin >= 6300:
        return "Neutral"
    if kelvin >= 5300:
        return "Slightly Warm"
    if kelvin >= 4300:
        return "Warm"
    if kelvin >= 3600:
        return "Very Warm"
    if kelvin >= 2900:
        return "Candlelight"
    return "Very Amber"


def kelvin_to_rgb(temp_kelvin):
    """Interpolate Redshift's real white-point table for this Kelvin value."""
    kelvin = min(max(temp_kelvin, _TABLE_START_K), _TABLE_MAX_K)
    position = (kelvin - _TABLE_START_K) / _TABLE_STEP_K
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(_BLACKBODY_TABLE) - 1)
    fraction = position - lower_index

    r1, g1, b1 = _BLACKBODY_TABLE[lower_index]
    r2, g2, b2 = _BLACKBODY_TABLE[upper_index]

    r = r1 + (r2 - r1) * fraction
    g = g1 + (g2 - g1) * fraction
    b = b1 + (b2 - b1) * fraction
    return r, g, b


def apply_temperature(kelvin, intensity=1.0):
    """
    Apply a Kelvin value to every active monitor by loading a real
    gamma RAMP via RandR (same underlying mechanism Redshift uses),
    not the single-exponent xrandr --gamma shortcut.

    intensity scales how far from neutral (1.0:1.0:1.0) we go:
    1.0 = exactly Redshift's real values, 0.5 = half as strong,
    1.5 = 50% stronger than Redshift's own default.

    Works across the whole table range (1000-10000K), not just the
    warm/night side - kelvin_to_rgb() already interpolates the cool
    (>6500K, bluer) side correctly, so there's no need to special-case
    it to flat neutral the way earlier versions of this function did.
    """
    from Xlib import display
    from Xlib.ext import randr

    r, g, b = kelvin_to_rgb(kelvin)
    r = 1.0 + (r - 1.0) * intensity
    g = 1.0 + (g - 1.0) * intensity
    b = 1.0 + (b - 1.0) * intensity
    # Intensity above 1.0 can push an already-extreme channel (like
    # blue at very low Kelvin, which the table already has at 0.0)
    # past zero into negative territory - not a valid gamma value.
    # Clamp back into range rather than handing X11 something invalid.
    r = max(0.0, min(2.0, r))
    g = max(0.0, min(2.0, g))
    b = max(0.0, min(2.0, b))

    d = display.Display()
    screen = d.screen()
    resources = randr.get_screen_resources(screen.root)

    for crtc in resources.crtcs:
        try:
            info = randr.get_crtc_info(d, crtc, resources.config_timestamp)
            if info.mode == 0:
                continue  # this CRTC isn't actually driving a monitor

            size = randr.get_crtc_gamma_size(d, crtc).size
            if size == 0:
                continue

            # Build a normal linear ramp (0 to max), then scale each
            # channel by our target color - this mirrors exactly what
            # Redshift's colorramp_fill() does.
            max_value = 65535
            base = [int(i * max_value / (size - 1)) for i in range(size)]
            red = [max(0, min(max_value, int(v * r))) for v in base]
            green = [max(0, min(max_value, int(v * g))) for v in base]
            blue = [max(0, min(max_value, int(v * b))) for v in base]

            randr.set_crtc_gamma(d, crtc, size, red, green, blue)
        except Exception as e:
            print(f"Could not set gamma ramp for a CRTC: {e}")

    d.sync()


def reset():
    apply_temperature(6500)

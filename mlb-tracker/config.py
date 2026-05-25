import zoneinfo
import settings_loader

APP_NAME = "MLB Tracker"
APP_TITLE = "MLB TRACKER"

# ---------------------------------------------------------------------------
# Preferred team override
#
# Leave as None to use settings.json. To make this a Giants tracker, change to:
# PREFERRED_TEAM_ABBR = "SF"
# ---------------------------------------------------------------------------
PREFERRED_TEAM_ABBR = None


def _team_nickname(team_name):
    multi_word = (
        "Blue Jays",
        "Red Sox",
        "White Sox",
    )

    for nickname in multi_word:
        if team_name.endswith(nickname):
            return nickname

    return team_name.split()[-1]

# ---------------------------------------------------------------------------
# Load user settings (team, timezone, logo)
# ---------------------------------------------------------------------------
_settings = settings_loader.load()

if PREFERRED_TEAM_ABBR:
    _team = next(
        (
            t for t in settings_loader.ALL_TEAMS
            if t["team_abbr"].upper() == PREFERRED_TEAM_ABBR.upper()
        ),
        None,
    )
    if _team:
        _settings.update(_team)
    else:
        raise ValueError(f"Unknown PREFERRED_TEAM_ABBR: {PREFERRED_TEAM_ABBR}")

TEAM_ID        = _settings["team_id"]
TEAM_NAME      = _settings["team_name"]
TEAM_ABBR      = _settings["team_abbr"]
TEAM_LOGO      = _settings["logo"]
LOCAL_TZ       = zoneinfo.ZoneInfo(_settings["timezone"])
TEAM_NICKNAME  = _team_nickname(TEAM_NAME)

# Keep DODGERS_TEAM_ID as an alias so existing code doesn't break
DODGERS_TEAM_ID = TEAM_ID

CURRENT_SEASON = 2026

DISPLAY_W = 800
DISPLAY_H = 480
MASTER_SCALE = 1
MASTER_W = DISPLAY_W
MASTER_H = DISPLAY_H

WAVESHARE_MODEL = "epd7in5_V2"

SCHEDULE_PAGE_SIZE = 7

SYNC_INTERVAL_NORMAL    = 1800
SYNC_INTERVAL_GAME_DAY  = 300
CONNECTIVITY_HOST       = "statsapi.mlb.com"
CONNECTIVITY_PORT       = 443
CONNECTIVITY_TIMEOUT    = 5

GPIO_BTN_LEFT         = 5
GPIO_BTN_CENTER       = 6
GPIO_BTN_RIGHT        = 13
GPIO_BTN_LIVE         = 26     # 4th button — jump to live game view
LONG_PRESS_THRESHOLD  = 1.5
CONFIG_COMBO_HOLD_SECONDS = 3.0

# Broadcast delay — add seconds to live game polling to sync with TV broadcast
# Set to 0 for no delay, increase if API is ahead of your broadcast
# Typical values: 0 (no delay), 15, 30, 45 seconds
BROADCAST_DELAY       = 0
LIVE_POLL_INTERVAL_SECONDS = 1

PAGE_BRIEFING  = 1
PAGE_SCHEDULE  = 2
PAGE_STANDINGS = 3
PAGE_COUNT     = 3

FONT_DIR  = "assets/fonts"
LOGO_DIR  = "assets/logos"
CACHE_DIR = "cache"
OUTPUT_DIR = "output"

MLB_BASE_URL = "https://statsapi.mlb.com/api/v1"

FONT_SCORE   = "assets/fonts/BebasNeue-Regular.ttf"
FONT_BOLD    = "assets/fonts/LiberationSans-Bold.ttf"
FONT_REGULAR = "assets/fonts/LiberationSans-Regular.ttf"

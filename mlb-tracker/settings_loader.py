"""
settings_loader.py
Loads user settings from settings.json.
Fresh installs must create settings.json through the setup wizard.
"""

import json
import os
import logging
import zoneinfo

logger = logging.getLogger(__name__)

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "settings.json")

REQUIRED_KEYS = ("team_id", "team_name", "team_abbr", "timezone", "logo")

# All 30 MLB teams — used by setup screen
ALL_TEAMS = [
    {"team_id": 108, "team_name": "Los Angeles Angels",      "team_abbr": "LAA", "timezone": "America/Los_Angeles", "logo": "LAA.png"},
    {"team_id": 109, "team_name": "Arizona Diamondbacks",    "team_abbr": "ARI", "timezone": "America/Phoenix",     "logo": "ARI.png"},
    {"team_id": 110, "team_name": "Baltimore Orioles",       "team_abbr": "BAL", "timezone": "America/New_York",    "logo": "BAL.png"},
    {"team_id": 111, "team_name": "Boston Red Sox",          "team_abbr": "BOS", "timezone": "America/New_York",    "logo": "BOS.png"},
    {"team_id": 112, "team_name": "Chicago Cubs",            "team_abbr": "CHC", "timezone": "America/Chicago",     "logo": "CHC.png"},
    {"team_id": 113, "team_name": "Cincinnati Reds",         "team_abbr": "CIN", "timezone": "America/New_York",    "logo": "CIN.png"},
    {"team_id": 114, "team_name": "Cleveland Guardians",     "team_abbr": "CLE", "timezone": "America/New_York",    "logo": "CLE.png"},
    {"team_id": 115, "team_name": "Colorado Rockies",        "team_abbr": "COL", "timezone": "America/Denver",      "logo": "COL.png"},
    {"team_id": 116, "team_name": "Detroit Tigers",          "team_abbr": "DET", "timezone": "America/Detroit",     "logo": "DET.png"},
    {"team_id": 117, "team_name": "Houston Astros",          "team_abbr": "HOU", "timezone": "America/Chicago",     "logo": "HOU.png"},
    {"team_id": 118, "team_name": "Kansas City Royals",      "team_abbr": "KC",  "timezone": "America/Chicago",     "logo": "KC.png"},
    {"team_id": 119, "team_name": "Los Angeles Dodgers",     "team_abbr": "LAD", "timezone": "America/Los_Angeles", "logo": "LAD.png"},
    {"team_id": 120, "team_name": "Washington Nationals",    "team_abbr": "WSH", "timezone": "America/New_York",    "logo": "WSH.png"},
    {"team_id": 121, "team_name": "New York Mets",           "team_abbr": "NYM", "timezone": "America/New_York",    "logo": "NYM.png"},
    {"team_id": 133, "team_name": "Oakland Athletics",       "team_abbr": "ATH", "timezone": "America/Chicago",     "logo": "ATH.png"},
    {"team_id": 134, "team_name": "Pittsburgh Pirates",      "team_abbr": "PIT", "timezone": "America/New_York",    "logo": "PIT.png"},
    {"team_id": 135, "team_name": "San Diego Padres",        "team_abbr": "SD",  "timezone": "America/Los_Angeles", "logo": "SD.png"},
    {"team_id": 136, "team_name": "Seattle Mariners",        "team_abbr": "SEA", "timezone": "America/Los_Angeles", "logo": "SEA.png"},
    {"team_id": 137, "team_name": "San Francisco Giants",    "team_abbr": "SF",  "timezone": "America/Los_Angeles", "logo": "SF.png"},
    {"team_id": 138, "team_name": "St. Louis Cardinals",     "team_abbr": "STL", "timezone": "America/Chicago",     "logo": "STL.png"},
    {"team_id": 139, "team_name": "Tampa Bay Rays",          "team_abbr": "TB",  "timezone": "America/New_York",    "logo": "TB.png"},
    {"team_id": 140, "team_name": "Texas Rangers",           "team_abbr": "TEX", "timezone": "America/Chicago",     "logo": "TEX.png"},
    {"team_id": 141, "team_name": "Toronto Blue Jays",       "team_abbr": "TOR", "timezone": "America/Toronto",     "logo": "TOR.png"},
    {"team_id": 142, "team_name": "Minnesota Twins",         "team_abbr": "MIN", "timezone": "America/Chicago",     "logo": "MIN.png"},
    {"team_id": 143, "team_name": "Philadelphia Phillies",   "team_abbr": "PHI", "timezone": "America/New_York",    "logo": "PHI.png"},
    {"team_id": 144, "team_name": "Atlanta Braves",          "team_abbr": "ATL", "timezone": "America/New_York",    "logo": "ATL.png"},
    {"team_id": 145, "team_name": "Chicago White Sox",       "team_abbr": "CWS", "timezone": "America/Chicago",     "logo": "CWS.png"},
    {"team_id": 146, "team_name": "Miami Marlins",           "team_abbr": "MIA", "timezone": "America/New_York",    "logo": "MIA.png"},
    {"team_id": 147, "team_name": "New York Yankees",        "team_abbr": "NYY", "timezone": "America/New_York",    "logo": "NYY.png"},
    {"team_id": 158, "team_name": "Milwaukee Brewers",       "team_abbr": "MIL", "timezone": "America/Chicago",     "logo": "MIL.png"},
]


def load():
    """Load settings.json. Returns dict with all fields guaranteed present."""
    if not os.path.exists(SETTINGS_PATH):
        raise RuntimeError(
            "settings.json not found. Run scripts/setup_wizard.py before "
            "starting MLB Tracker."
        )

    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        missing = [key for key in REQUIRED_KEYS if key not in data]
        if missing:
            raise RuntimeError(
                "settings.json is missing required keys: " + ", ".join(missing)
            )

        # Validate timezone
        try:
            zoneinfo.ZoneInfo(data["timezone"])
        except Exception:
            raise RuntimeError(f"Invalid timezone in settings: {data['timezone']}")

        logger.info(
            "Settings loaded: %s (%d) tz=%s",
            data["team_abbr"], data["team_id"], data["timezone"]
        )
        return data

    except (json.JSONDecodeError, OSError) as e:
        raise RuntimeError(f"Failed to load settings.json: {e}") from e


def save(data):
    """Write settings dict back to settings.json atomically."""
    import tempfile
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(SETTINGS_PATH), suffix=".tmp"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, SETTINGS_PATH)
        logger.info("Settings saved: %s", data)
    except Exception as e:
        logger.error("Failed to save settings: %s", e)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def is_first_boot():
    """Returns True if settings.json doesn't exist yet."""
    return not os.path.exists(SETTINGS_PATH)

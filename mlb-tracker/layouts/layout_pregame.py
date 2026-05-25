"""
layout_pregame.py
Pre-game VS screen — shown 10 minutes before first pitch.

Layout:
  - Black header bar with team name
  - Large team logos side by side with VS in centre
  - Full team names below logos
  - Live countdown in seconds (partial-refreshable)
  - Game time and venue at bottom

Partial refresh zone for countdown:
  ZONE_COUNTDOWN = (0, 360, 800, 430)
"""

from PIL import Image, ImageDraw
import os
import logging
from datetime import datetime
import config
from layouts.draw_utils import (
    bold_font, regular_font, score_font,
    draw_hline, text_w, draw_clock_right
)

logger = logging.getLogger(__name__)

W = config.MASTER_W
H = config.MASTER_H

LOGO_SIZE     = 150    # large logos for the VS screen
ZONE_COUNTDOWN_Y1 = 310
ZONE_COUNTDOWN_Y2 = 410

_logo_cache = {}


def _load_logo(filename, size=LOGO_SIZE):
    """Load and convert a team logo to 1-bit at the given size."""
    path = os.path.join(config.LOGO_DIR, filename)
    key  = (path, size)
    if key in _logo_cache:
        return _logo_cache[key]
    if not os.path.exists(path):
        logger.warning("Logo not found: %s", path)
        return None
    try:
        img  = Image.open(path).convert("RGBA")
        img  = img.resize((size, size), Image.LANCZOS)
        r, g, b, a = img.split()
        gray = img.convert("L")
        out  = Image.new("1", (size, size), 255)
        for x in range(size):
            for y in range(size):
                if a.getpixel((x, y)) > 128 and gray.getpixel((x, y)) < 180:
                    out.putpixel((x, y), 0)
        _logo_cache[key] = out
        return out
    except Exception as e:
        logger.warning("Logo load failed (%s): %s", path, e)
        return None


def render(state, game, seconds_remaining):
    """
    Render the full pre-game screen.
    game: a game dict from the schedule cache
    seconds_remaining: int — seconds until first pitch
    """
    img  = Image.new("1", (W, H), 255)
    draw = ImageDraw.Draw(img)

    _draw_header(draw, state)
    _draw_logos(draw, img, game)
    _draw_team_names(draw, game)
    _draw_countdown(draw, seconds_remaining)
    _draw_footer(draw, game)

    return img


def render_countdown_zone(state, game, seconds_remaining):
    """
    Render ONLY the countdown zone — for partial refresh.
    Returns full 800x480 image (driver needs full buffer).
    """
    img  = Image.new("1", (W, H), 255)
    draw = ImageDraw.Draw(img)

    # Render everything so the buffer is correct, partial refresh
    # will only push the countdown region to the screen
    _draw_header(draw, state)
    _draw_logos(draw, img, game)
    _draw_team_names(draw, game)
    _draw_countdown(draw, seconds_remaining)
    _draw_footer(draw, game)

    return img


def _draw_header(draw, state):
    draw.rectangle([0, 0, W, 44], fill=0)

    title = f"{config.TEAM_NAME.upper()}  —  GAME DAY"
    fnt   = bold_font(18)
    tw    = text_w(draw, title, fnt)
    draw.text(((W - tw) // 2, 12), title, font=fnt, fill=255)
    draw_clock_right(
        draw,
        W - 8,
        13,
        datetime.now(config.LOCAL_TZ),
        regular_font(10),
        fill=255,
    )

    if state and state.stale:
        draw.rectangle([8, 26, 68, 38], fill=255)
        draw.text((12, 27), "OFFLINE", font=regular_font(9), fill=0)


def _draw_logos(draw, img, game):
    """Draw home and away logos with VS in the centre."""
    my_logo_file  = config.TEAM_LOGO
    opp_logo_file = f"{game.get('opponent_abbr', 'MLB')}.png"

    # Which side is which
    if game.get("home_away") == "home":
        left_logo_file  = opp_logo_file
        right_logo_file = my_logo_file
    else:
        left_logo_file  = my_logo_file
        right_logo_file = opp_logo_file

    logo_y = 60

    # Left logo
    left_logo = _load_logo(left_logo_file)
    if left_logo:
        left_x = W // 4 - LOGO_SIZE // 2
        img.paste(left_logo, (left_x, logo_y))
    else:
        # Placeholder box
        left_x = W // 4 - LOGO_SIZE // 2
        draw.rectangle([left_x, logo_y, left_x + LOGO_SIZE, logo_y + LOGO_SIZE],
                       outline=0, width=2)

    # Right logo
    right_logo = _load_logo(right_logo_file)
    if right_logo:
        right_x = 3 * W // 4 - LOGO_SIZE // 2
        img.paste(right_logo, (right_x, logo_y))
    else:
        right_x = 3 * W // 4 - LOGO_SIZE // 2
        draw.rectangle([right_x, logo_y, right_x + LOGO_SIZE, logo_y + LOGO_SIZE],
                       outline=0, width=2)

    # VS in centre
    vs_fnt = score_font(72)
    vs_str = "VS"
    vw = text_w(draw, vs_str, vs_fnt)
    draw.text(((W - vw) // 2, logo_y + LOGO_SIZE // 2 - 30), vs_str,
              font=vs_fnt, fill=0)


def _draw_team_names(draw, game):
    """Team full names below logos."""
    opp_name = game.get("opponent_name", "Opponent")
    my_name  = config.TEAM_NAME

    if game.get("home_away") == "home":
        left_name  = opp_name
        right_name = my_name
        left_label  = "AWAY"
        right_label = "HOME"
    else:
        left_name  = my_name
        right_name = opp_name
        left_label  = "AWAY"
        right_label = "HOME"

    name_y  = 222   # logo ends at 60+150=210, give 12px gap
    label_y = 242

    name_fnt  = bold_font(16)
    label_fnt = regular_font(10)

    # Left team
    lw = text_w(draw, left_name, name_fnt)
    draw.text((W // 4 - lw // 2, name_y), left_name, font=name_fnt, fill=0)
    llw = text_w(draw, left_label, label_fnt)
    draw.text((W // 4 - llw // 2, label_y), left_label, font=label_fnt, fill=0)

    # Right team
    rw = text_w(draw, right_name, name_fnt)
    draw.text((3 * W // 4 - rw // 2, name_y), right_name, font=name_fnt, fill=0)
    rlw = text_w(draw, right_label, label_fnt)
    draw.text((3 * W // 4 - rlw // 2, label_y), right_label, font=label_fnt, fill=0)

    # Divider
    draw_hline(draw, 0, 258, W, thickness=1)


def _draw_countdown(draw, seconds_remaining):
    """Live countdown — this zone gets partially refreshed every second."""
    zone_y = ZONE_COUNTDOWN_Y1
    zone_h = ZONE_COUNTDOWN_Y2 - ZONE_COUNTDOWN_Y1

    # Clear zone
    draw.rectangle([0, zone_y, W, ZONE_COUNTDOWN_Y2], fill=255)

    if seconds_remaining <= 0:
        msg     = "FIRST PITCH!"
        msg_fnt = bold_font(36)
        mw      = text_w(draw, msg, msg_fnt)
        draw.text(((W - mw) // 2, zone_y + 8), msg, font=msg_fnt, fill=0)
        return

    # Format as M:SS or just seconds
    mins = seconds_remaining // 60
    secs = seconds_remaining % 60

    if mins > 0:
        time_str = f"{mins}:{secs:02d}"
        lbl_str  = "GAME STARTS IN"
    else:
        time_str = f"{seconds_remaining}"
        lbl_str  = "SECONDS UNTIL FIRST PITCH"

    lbl_fnt  = regular_font(13)
    time_fnt = score_font(64)

    lw = text_w(draw, lbl_str, lbl_fnt)
    draw.text(((W - lw) // 2, zone_y + 4), lbl_str, font=lbl_fnt, fill=0)

    tw = text_w(draw, time_str, time_fnt)
    draw.text(((W - tw) // 2, zone_y + 20), time_str, font=time_fnt, fill=0)


def _draw_footer(draw, game):
    """Game time and venue at the very bottom."""
    from datetime import datetime
    TZ = config.LOCAL_TZ

    draw_hline(draw, 0, ZONE_COUNTDOWN_Y2, W, thickness=1)

    try:
        dt_utc   = datetime.fromisoformat(game["date_utc"].replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone(TZ)
        time_str = dt_local.strftime("%-I:%M %p PT")
    except Exception:
        time_str = ""

    venue    = game.get("venue", "")
    ha       = venue
    info_str = f"{time_str}  •  {ha}" if time_str else ha

    fnt = regular_font(14)
    iw  = text_w(draw, info_str, fnt)
    draw.text(((W - iw) // 2, ZONE_COUNTDOWN_Y2 + 12), info_str, font=fnt, fill=0)

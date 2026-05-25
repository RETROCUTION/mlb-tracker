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
  ZONE_COUNTDOWN = inside the two horizontal divider lines
"""

from PIL import Image, ImageDraw
import os
import logging
from datetime import datetime
import config
from layouts.draw_utils import (
    bold_font, regular_font, score_font,
    draw_hline, text_w, text_h, draw_clock_right
)

logger = logging.getLogger(__name__)

W = config.MASTER_W
H = config.MASTER_H

LOGO_SIZE     = 150    # large logos for the VS screen
TEAM_DIVIDER_Y = 258
FOOTER_DIVIDER_Y = 410
ZONE_COUNTDOWN_Y1 = TEAM_DIVIDER_Y + 8
ZONE_COUNTDOWN_Y2 = FOOTER_DIVIDER_Y - 8

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

    _draw_header(draw, state, game)
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
    _draw_header(draw, state, game)
    _draw_logos(draw, img, game)
    _draw_team_names(draw, game)
    _draw_countdown(draw, seconds_remaining)
    _draw_footer(draw, game)

    return img


def update_dynamic(img, state, game, seconds_remaining):
    """Redraw the live parts of the upcoming-game screen in an existing image."""
    if img is None or game is None:
        return False

    draw = ImageDraw.Draw(img)
    _draw_countdown(draw, seconds_remaining)
    return True


def clear_countdown(img):
    """Hide only the timer while a slow full refresh is in progress."""
    if img is None:
        return False

    draw = ImageDraw.Draw(img)
    draw.rectangle([0, ZONE_COUNTDOWN_Y1, W, ZONE_COUNTDOWN_Y2], fill=255)
    _draw_countdown_label(draw)
    return True


def _draw_header(draw, state, game):
    draw.rectangle([0, 0, W, 44], fill=0)

    title = "UPCOMING GAME"
    fnt   = bold_font(18)
    tw    = text_w(draw, title, fnt)
    draw.text(((W - tw) // 2, 12), title, font=fnt, fill=255)
    draw_clock_right(
        draw,
        W - 8,
        7,
        datetime.now(config.LOCAL_TZ),
        regular_font(config.HEADER_CLOCK_FONT_SIZE),
        fill=255,
        label="ONLINE:",
        label_font=regular_font(9),
        show_date=True,
        date_font=regular_font(config.HEADER_DATE_FONT_SIZE),
        show_wifi=True,
    )

    if state and state.stale:
        draw.rectangle([8, 26, 68, 38], fill=255)
        draw.text((12, 27), "OFFLINE", font=regular_font(9), fill=0)


def _game_date_label(game):
    try:
        dt_utc = datetime.fromisoformat(game["date_utc"].replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone(config.LOCAL_TZ)
    except Exception:
        dt_local = datetime.now(config.LOCAL_TZ)

    return dt_local.strftime("%B %-d, %Y").upper()


def _draw_logos(draw, img, game):
    """Draw tracked-team and opponent logos with VS in the centre."""
    sides = _matchup_sides(game)
    left_logo_file = sides["left"]["logo"]
    right_logo_file = sides["right"]["logo"]

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
    sides = _matchup_sides(game)
    left_name = sides["left"]["name"]
    right_name = sides["right"]["name"]
    left_label = sides["left"]["label"]
    right_label = sides["right"]["label"]

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
    draw_hline(draw, 0, TEAM_DIVIDER_Y, W, thickness=1)


def _draw_countdown(draw, seconds_remaining):
    """Live countdown — this zone gets partially refreshed every second."""
    zone_y = ZONE_COUNTDOWN_Y1
    zone_h = ZONE_COUNTDOWN_Y2 - ZONE_COUNTDOWN_Y1

    # Clear inside the divider lines, leaving the lines themselves untouched.
    draw.rectangle([0, zone_y, W, ZONE_COUNTDOWN_Y2], fill=255)

    if seconds_remaining <= 0:
        msg     = "PLAY BALL!"
        msg_fnt = bold_font(36)
        mw      = text_w(draw, msg, msg_fnt)
        mh      = text_h(draw, msg, msg_fnt)
        draw.text(((W - mw) // 2, zone_y + (zone_h - mh) // 2), msg, font=msg_fnt, fill=0)
        return

    seconds_remaining = max(0, int(seconds_remaining))
    hours = seconds_remaining // 3600
    mins = (seconds_remaining % 3600) // 60
    secs = seconds_remaining % 60
    time_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
    lbl_str  = "GAME STARTS IN"

    lbl_fnt  = regular_font(13)
    time_fnt = score_font(64)

    lbl_h = text_h(draw, lbl_str, lbl_fnt)
    time_h = text_h(draw, time_str, time_fnt)
    gap = 4
    block_y = zone_y + (zone_h - lbl_h - gap - time_h) // 2 - 2

    lw = text_w(draw, lbl_str, lbl_fnt)
    draw.text(((W - lw) // 2, block_y), lbl_str, font=lbl_fnt, fill=0)

    tw = text_w(draw, time_str, time_fnt)
    draw.text(((W - tw) // 2, block_y + lbl_h + gap), time_str, font=time_fnt, fill=0)


def _draw_countdown_label(draw):
    zone_y = ZONE_COUNTDOWN_Y1
    zone_h = ZONE_COUNTDOWN_Y2 - ZONE_COUNTDOWN_Y1
    lbl_str = "GAME STARTS IN"
    placeholder_time = "00:00:00"

    lbl_fnt = regular_font(13)
    time_fnt = score_font(64)
    lbl_h = text_h(draw, lbl_str, lbl_fnt)
    time_h = text_h(draw, placeholder_time, time_fnt)
    gap = 4
    block_y = zone_y + (zone_h - lbl_h - gap - time_h) // 2 - 2

    lw = text_w(draw, lbl_str, lbl_fnt)
    draw.text(((W - lw) // 2, block_y), lbl_str, font=lbl_fnt, fill=0)


def _matchup_sides(game):
    """Keep the tracked team on the left, regardless of home/away status."""
    my_label = "HOME" if game.get("home_away") == "home" else "AWAY"
    opp_label = "AWAY" if my_label == "HOME" else "HOME"

    return {
        "left": {
            "name": config.TEAM_NAME,
            "logo": config.TEAM_LOGO,
            "label": my_label,
        },
        "right": {
            "name": game.get("opponent_name", "Opponent"),
            "logo": f"{game.get('opponent_abbr', 'MLB')}.png",
            "label": opp_label,
        },
    }


def _draw_footer(draw, game):
    """Game time and venue at the very bottom."""
    from datetime import datetime
    TZ = config.LOCAL_TZ

    draw_hline(draw, 0, FOOTER_DIVIDER_Y, W, thickness=1)

    try:
        dt_utc   = datetime.fromisoformat(game["date_utc"].replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone(TZ)
        date_str = dt_local.strftime("%B %-d, %Y").upper()
        time_str = dt_local.strftime("%-I:%M %p PT")
    except Exception:
        date_str = ""
        time_str = ""

    venue    = game.get("venue", "")
    ha       = venue
    info_str = f"{time_str}  •  {ha}" if time_str else ha

    date_fnt = bold_font(13)
    info_fnt = regular_font(14)

    if date_str:
        dw = text_w(draw, date_str, date_fnt)
        draw.text(((W - dw) // 2, FOOTER_DIVIDER_Y + 8), date_str, font=date_fnt, fill=0)

    iw  = text_w(draw, info_str, info_fnt)
    draw.text(((W - iw) // 2, FOOTER_DIVIDER_Y + 30), info_str, font=info_fnt, fill=0)

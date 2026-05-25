"""
layout_live.py
Full-screen live game mode for the Waveshare 7.5" e-ink display (800x480).

Zone layout (must match ZONE_* in main.py):
  ZONE A (0,   0,   800, 70)  — Score bar + clock
  ZONE B (0,   70,  310, 330) — Batter / Pitcher / Last pitch
  ZONE C (310, 70,  800, 330) — Diamond + Count + Outs
  ZONE D (0,   330, 800, 362) — Last play
  ZONE E (0,   362, 800, 480) — Line score (white bg, inning numbers above)
"""

from PIL import Image, ImageDraw
import logging
import os
from datetime import datetime
import config
from layouts.draw_utils import (
    bold_font, regular_font, score_font,
    draw_hline, draw_vline, text_w, ordinal, draw_clock_right
)

logger = logging.getLogger(__name__)

W = config.MASTER_W
H = config.MASTER_H

ZONE_A_Y  = 0
ZONE_A_H  = 70
ZONE_B_W  = 310
ZONE_BC_Y = 70
ZONE_BC_H = 260          # shrunk slightly to give line score more room
ZONE_C_X  = ZONE_B_W
ZONE_C_W  = W - ZONE_B_W
ZONE_D_Y  = 330
ZONE_D_H  = 32
ZONE_E_Y  = 362
ZONE_E_H  = H - ZONE_E_Y   # 118px — much more room for line score

# Diamond geometry
DIAMOND_CX = ZONE_C_X + ZONE_C_W // 2 + 42
DIAMOND_CY = ZONE_BC_Y + ZONE_BC_H // 2
DIAMOND_R  = 52
BASE_SZ    = 16

_logo_cache = {}


def _load_team_logo(abbr, size=42):
    if not abbr:
        return None

    path = os.path.join(config.LOGO_DIR, f"{abbr}.png")
    key = (path, size)
    if key in _logo_cache:
        return _logo_cache[key]
    if not os.path.exists(path):
        return None

    try:
        img = Image.open(path).convert("RGBA")
        img = img.resize((size, size), Image.LANCZOS)
        _, _, _, a = img.split()
        gray = img.convert("L")
        out = Image.new("1", (size, size), 255)
        for x in range(size):
            for y in range(size):
                if a.getpixel((x, y)) > 128 and gray.getpixel((x, y)) < 180:
                    out.putpixel((x, y), 0)
        _logo_cache[key] = out
        return out
    except Exception as e:
        logger.warning("Live logo load failed for %s: %s", abbr, e)
        return None


def _runner_label(name):
    if not name:
        return ""
    parts = str(name).strip().split()
    if not parts:
        return ""
    return parts[-1].upper()


def render(state, game):
    """Render live game screen. If game is None show no-live-game overlay."""
    img  = Image.new("1", (W, H), 255)
    draw = ImageDraw.Draw(img)

    if game is None:
        _draw_no_game(draw)
        return img

    _draw_zone_a(draw, game)
    _draw_zone_b(draw, game)
    _draw_zone_c(draw, game)
    _draw_zone_d(draw, game)
    _draw_zone_e(draw, game)
    return img


def _draw_no_game(draw):
    """Overlay shown when user navigates to live screen but no game is active."""
    import cache

    draw.rectangle([0, 0, W, 44], fill=0)
    draw.text((10, 13), "LIVE GAME", font=bold_font(18), fill=255)
    draw_clock_right(
        draw,
        W - 12,
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

    box_x, box_y = 150, 130
    box_w, box_h = 500, 220
    draw.rectangle([box_x, box_y, box_x + box_w, box_y + box_h], outline=0, width=3)

    title_fnt = bold_font(20)
    info_fnt  = regular_font(14)
    time_fnt  = bold_font(16)
    hint_fnt  = regular_font(11)

    title = "NO LIVE GAME IN PROGRESS"
    tw = text_w(draw, title, title_fnt)
    draw.text((W // 2 - tw // 2, box_y + 20), title, font=title_fnt, fill=0)

    # Find next game from cache
    try:
        sched = cache.read_schedule()
        games = sched.get("games", []) if sched else []
        nxt = next(
            (
                g for g in games
                if g.get("status") in ("Preview", "Pre-Game", "Scheduled")
            ),
            None,
        )
    except Exception:
        nxt = None

    if nxt:
        try:
            TZ     = config.LOCAL_TZ
            dt_utc = datetime.fromisoformat(nxt["date_utc"].replace("Z", "+00:00"))
            dt_loc = dt_utc.astimezone(TZ)
            opp    = nxt.get("opponent_name", "")

            lbl = "NEXT LIVE GAME:"
            lw  = text_w(draw, lbl, info_fnt)
            draw.text((W // 2 - lw // 2, box_y + 65), lbl, font=info_fnt, fill=0)

            vs_str = f"vs {opp}"
            vw = text_w(draw, vs_str, time_fnt)
            draw.text((W // 2 - vw // 2, box_y + 90), vs_str, font=time_fnt, fill=0)

            dt_str = dt_loc.strftime("%A, %B %-d  at  %-I:%M %p PT")
            dw = text_w(draw, dt_str, time_fnt)
            draw.text((W // 2 - dw // 2, box_y + 118), dt_str, font=time_fnt, fill=0)
        except Exception:
            pass
    else:
        msg = "No upcoming games scheduled"
        mw  = text_w(draw, msg, info_fnt)
        draw.text((W // 2 - mw // 2, box_y + 90), msg, font=info_fnt, fill=0)

    hint = "Press CENTER to return to main screen"
    hw   = text_w(draw, hint, hint_fnt)
    draw.text((W // 2 - hw // 2, box_y + 180), hint, font=hint_fnt, fill=0)


# ---------------------------------------------------------------------------
# ZONE A — Score bar
# ---------------------------------------------------------------------------

def _draw_zone_a(draw, g):
    away_abbr     = g.get("away_abbr", "AWY")
    home_abbr     = g.get("home_abbr", "HME")
    away_score    = g.get("away_score", 0)
    home_score    = g.get("home_score", 0)
    inning        = g.get("inning", 1)
    inning_half   = g.get("inning_half", "Top")
    status_detail = g.get("status_detail", "In Progress")

    score_fnt  = score_font(62)
    abbr_fnt   = bold_font(11)
    detail_fnt = regular_font(10)
    live_fnt   = bold_font(11)
    inn_fnt    = bold_font(17)

    lcx = W // 4
    rcx = 3 * W // 4

    # Away team logo + score — left quarter
    away_str = str(away_score)
    aw  = text_w(draw, away_str, score_fnt)
    away_logo = _load_team_logo(away_abbr, 42)
    away_total_w = 42 + 12 + aw if away_logo else aw
    away_x = lcx - away_total_w // 2
    if away_logo:
        draw._image.paste(away_logo, (away_x, 15))
        away_score_x = away_x + 54
    else:
        away_score_x = lcx - aw // 2
        abw = text_w(draw, away_abbr, abbr_fnt)
        draw.text((lcx - abw // 2, 4), away_abbr, font=abbr_fnt, fill=0)
    draw.text((away_score_x, 5), away_str, font=score_fnt, fill=0)

    # Home team logo + score — right quarter
    home_str = str(home_score)
    hw  = text_w(draw, home_str, score_fnt)
    home_logo = _load_team_logo(home_abbr, 42)
    home_total_w = hw + 12 + 42 if home_logo else hw
    home_x = rcx - home_total_w // 2
    home_score_x = home_x
    draw.text((home_score_x, 5), home_str, font=score_fnt, fill=0)
    if home_logo:
        draw._image.paste(home_logo, (home_score_x + hw + 12, 15))
    else:
        abw = text_w(draw, home_abbr, abbr_fnt)
        draw.text((rcx - abw // 2, 4), home_abbr, font=abbr_fnt, fill=0)

    # Centre — inning + status + LIVE badge
    half_arrow = "▲" if inning_half.lower() in ("top", "t") else "▼"
    inn_str = f"{half_arrow} {ordinal(inning)}"
    iw = text_w(draw, inn_str, inn_fnt)
    draw.text((W // 2 - iw // 2, 8), inn_str, font=inn_fnt, fill=0)

    dw = text_w(draw, status_detail, detail_fnt)
    draw.text((W // 2 - dw // 2, 30), status_detail, font=detail_fnt, fill=0)

    live_str = "● LIVE"
    lw = text_w(draw, live_str, live_fnt)
    draw.text((W // 2 - lw // 2, 50), live_str, font=live_fnt, fill=0)

    draw_clock_right(
        draw,
        W - 12,
        40,
        datetime.now(config.LOCAL_TZ),
        regular_font(config.HEADER_CLOCK_FONT_SIZE),
        fill=0,
        label="ONLINE:",
        label_font=regular_font(9),
        show_date=True,
        date_font=regular_font(config.HEADER_DATE_FONT_SIZE),
        show_wifi=True,
    )

    draw_hline(draw, 0, ZONE_A_H - 1, W, thickness=2, fill=0)


# ---------------------------------------------------------------------------
# ZONE B — Batter / Pitcher / Last pitch
# ---------------------------------------------------------------------------

def _draw_zone_b(draw, g):
    x = 0
    y = ZONE_BC_Y

    draw_hline(draw, 0, y, W, thickness=1)
    draw_vline(draw, ZONE_B_W, y, ZONE_BC_H, thickness=1)

    outs             = g.get("outs", 0)
    batter_name      = g.get("batter_name", "—")
    batter_avg       = g.get("batter_avg", ".---")
    batter_ab        = g.get("batter_ab_today", 0)
    batter_h         = g.get("batter_h_today", 0)
    pitcher_name     = g.get("pitcher_name", "—")
    pitcher_era      = g.get("pitcher_era", "-.--")
    pitch_count      = g.get("pitch_count", 0)
    last_pitch_speed = g.get("last_pitch_speed")
    last_pitch_type  = g.get("last_pitch_type")

    # When inning is over clear stale batter info and last pitch
    if outs >= 3:
        batter_name      = "—"
        batter_avg       = "—"
        batter_ab        = 0
        batter_h         = 0
        last_pitch_speed = None
        last_pitch_type  = None

    lbl_fnt   = regular_font(9)
    name_fnt  = bold_font(14)
    stat_fnt  = regular_font(11)
    speed_fnt = bold_font(26)
    type_fnt  = regular_font(11)
    pad = 10

    # Divide zone B into equal thirds:
    # top third = AT BAT, middle third = PITCHING, bottom third = LAST PITCH
    third = ZONE_BC_H // 3   # ~93px each

    bat_y  = y              # top of AT BAT section
    pit_y  = y + third      # top of PITCHING section
    lp_y   = y + third * 2  # top of LAST PITCH section

    # ---- INNING CHANGE — show clean state when 3 outs ----
    if outs >= 3:
        inning   = g.get("inning", 1)
        msg1_fnt = bold_font(17)
        msg1 = f"END OF {ordinal(inning).upper()} INNING"
        m1w = text_w(draw, msg1, msg1_fnt)
        mid = y + ZONE_BC_H // 2
        draw.text((ZONE_B_W // 2 - m1w // 2, mid - 10), msg1, font=msg1_fnt, fill=0)
        return
    draw.text((x + pad, bat_y + 6), "AT BAT", font=lbl_fnt, fill=0)
    draw_hline(draw, x, bat_y + 18, ZONE_B_W, thickness=1)

    if batter_name and batter_name not in ("—", "", "-.--"):
        parts = batter_name.split()
        if len(parts) > 1:
            draw.text((x + pad, bat_y + 22), parts[0],            font=stat_fnt, fill=0)
            draw.text((x + pad, bat_y + 36), " ".join(parts[1:]), font=name_fnt, fill=0)
        else:
            draw.text((x + pad, bat_y + 30), batter_name, font=name_fnt, fill=0)
        draw.text(
            (x + pad, bat_y + 58),
            f"AVG {batter_avg}   {batter_h}-{batter_ab} today",
            font=stat_fnt, fill=0
        )
    else:
        draw.text((x + pad, bat_y + 32), "Waiting...", font=stat_fnt, fill=0)

    # ---- PITCHING ----
    draw_hline(draw, x, pit_y, ZONE_B_W, thickness=1)
    draw.text((x + pad, pit_y + 6), "PITCHING", font=lbl_fnt, fill=0)
    draw_hline(draw, x, pit_y + 18, ZONE_B_W, thickness=1)

    parts = pitcher_name.split()
    if len(parts) > 1:
        draw.text((x + pad, pit_y + 22), parts[0],            font=stat_fnt, fill=0)
        draw.text((x + pad, pit_y + 36), " ".join(parts[1:]), font=name_fnt, fill=0)
    else:
        draw.text((x + pad, pit_y + 30), pitcher_name, font=name_fnt, fill=0)

    draw.text(
        (x + pad, pit_y + 58),
        f"ERA {pitcher_era}   {pitch_count} pitches",
        font=stat_fnt, fill=0
    )

    # ---- LAST PITCH ----
    draw_hline(draw, x, lp_y, ZONE_B_W, thickness=1)
    draw.text((x + pad, lp_y + 6), "LAST PITCH", font=lbl_fnt, fill=0)

    if last_pitch_speed and last_pitch_type:
        speed_str = str(last_pitch_speed)
        sw = text_w(draw, speed_str, speed_fnt)
        draw.text((x + pad,          lp_y + 18), speed_str,              font=speed_fnt, fill=0)
        draw.text((x + pad + sw + 4, lp_y + 34), "MPH",                  font=lbl_fnt,   fill=0)
        draw.text((x + pad,          lp_y + 50), last_pitch_type.upper(), font=type_fnt,  fill=0)
    else:
        draw.text((x + pad, lp_y + 28), "—", font=stat_fnt, fill=0)


# ---------------------------------------------------------------------------
# ZONE C — Diamond + Count + Outs
# ---------------------------------------------------------------------------

def _draw_zone_c(draw, g):
    balls   = g.get("balls",   0)
    strikes = g.get("strikes", 0)
    outs    = g.get("outs",    0)
    pitch_number = g.get("pitch_number", 0)
    on_1b   = g.get("on_1b",  False)
    on_2b   = g.get("on_2b",  False)
    on_3b   = g.get("on_3b",  False)
    runner_1b_name = g.get("runner_1b_name", "")
    runner_2b_name = g.get("runner_2b_name", "")
    runner_3b_name = g.get("runner_3b_name", "")

    # 3 outs = inning over — reset count and runners to clean state
    # so we don't freeze on stale count while API updates to next half inning
    if outs >= 3:
        balls   = 0
        strikes = 0
        on_1b   = False
        on_2b   = False
        on_3b   = False
        runner_1b_name = ""
        runner_2b_name = ""
        runner_3b_name = ""

    cx = DIAMOND_CX
    cy = DIAMOND_CY

    # Redraw the top border that separates zone C from zone A
    draw_hline(draw, ZONE_C_X, ZONE_BC_Y, ZONE_C_W, thickness=1, fill=0)
    # Redraw left border separating zone B from zone C
    draw_vline(draw, ZONE_B_W, ZONE_BC_Y, ZONE_BC_H, thickness=1, fill=0)

    base_home = (cx,             cy + DIAMOND_R)
    base_1b   = (cx + DIAMOND_R, cy)
    base_2b   = (cx,             cy - DIAMOND_R)
    base_3b   = (cx - DIAMOND_R, cy)

    for start, end in [
        (base_home, base_1b),
        (base_1b,   base_2b),
        (base_2b,   base_3b),
        (base_3b,   base_home),
    ]:
        draw.line([start, end], fill=0, width=2)

    def draw_base(centre, occupied):
        bx = centre[0] - BASE_SZ // 2
        by = centre[1] - BASE_SZ // 2
        if occupied:
            draw.rectangle([bx, by, bx + BASE_SZ, by + BASE_SZ], fill=0)
        else:
            draw.rectangle([bx, by, bx + BASE_SZ, by + BASE_SZ], outline=0, width=2)

    draw_base(base_1b, on_1b)
    draw_base(base_2b, on_2b)
    draw_base(base_3b, on_3b)

    # Home plate
    hp = base_home
    draw.polygon([
        (hp[0] - 9, hp[1] - 8),
        (hp[0] + 9, hp[1] - 8),
        (hp[0] + 9, hp[1] + 2),
        (hp[0],     hp[1] + 10),
        (hp[0] - 9, hp[1] + 2),
    ], outline=0, width=2)

    lbl = regular_font(9)
    runner_fnt = bold_font(10)

    def fit_runner(label, max_w):
        while label and text_w(draw, label, runner_fnt) > max_w:
            label = label[:-1]
        return label

    def draw_runner(label, x, y, max_w, anchor="left"):
        label = fit_runner(_runner_label(label), max_w)
        if not label:
            return
        lw = text_w(draw, label, runner_fnt)
        tx = x if anchor == "left" else x - lw
        draw.text((tx, y), label, font=runner_fnt, fill=0)

    if on_1b and runner_1b_name:
        draw_runner(
            runner_1b_name,
            base_1b[0] + BASE_SZ // 2 + 10,
            base_1b[1] - 18,
            W - (base_1b[0] + BASE_SZ // 2 + 16),
        )
    else:
        draw.text((base_1b[0] + BASE_SZ // 2 + 4, base_1b[1] - 6), "1B", font=lbl, fill=0)

    if on_2b and runner_2b_name:
        draw_runner(
            runner_2b_name,
            min(W - 6, base_2b[0] + 72),
            base_2b[1] - 24,
            84,
            anchor="right",
        )
    else:
        draw.text((base_2b[0] + BASE_SZ // 2 + 4, base_2b[1] - 6), "2B", font=lbl, fill=0)

    if on_3b and runner_3b_name:
        draw_runner(
            runner_3b_name,
            base_3b[0] - BASE_SZ // 2 - 10,
            base_3b[1] - 18,
            96,
            anchor="right",
        )
    else:
        draw.text((base_3b[0] - BASE_SZ // 2 - 22, base_3b[1] - 6), "3B", font=lbl, fill=0)

    # Count & outs dots
    count_x = ZONE_C_X + 12
    count_y = ZONE_BC_Y + 14
    dot_r   = 8
    dot_gap = 22
    hdr_fnt = bold_font(11)

    def draw_dots(label, count, max_count, dy):
        draw.text((count_x, count_y + dy), label, font=hdr_fnt, fill=0)
        dx = count_x + 68
        for i in range(max_count):
            ex = dx + i * dot_gap
            ey = count_y + dy + 6
            if i < count:
                draw.ellipse([ex - dot_r, ey - dot_r, ex + dot_r, ey + dot_r], fill=0)
            else:
                draw.ellipse([ex - dot_r, ey - dot_r, ex + dot_r, ey + dot_r], outline=0, width=2)

    draw_dots("BALLS",   balls,   4, 0)
    draw_dots("STRIKES", strikes, 3, 26)
    draw_dots("OUTS",    outs,    3, 52)

    if pitch_number:
        pitch_str = f"PITCH {pitch_number}"
        pitch_fnt = bold_font(18)
        draw.text(
            (count_x + 4, count_y + 92),
            pitch_str,
            font=pitch_fnt,
            fill=0,
        )

    # Runners summary
    runners = []
    if on_1b: runners.append("1ST")
    if on_2b: runners.append("2ND")
    if on_3b: runners.append("3RD")
    runner_str = "RUNNERS: " + ", ".join(runners) if runners else "BASES EMPTY"
    rf = regular_font(10)
    rw = text_w(draw, runner_str, rf)
    draw.text(
        (ZONE_C_X + (ZONE_C_W - rw) // 2, ZONE_BC_Y + ZONE_BC_H - 18),
        runner_str, font=rf, fill=0
    )


# ---------------------------------------------------------------------------
# ZONE D — Last play
# ---------------------------------------------------------------------------

def _draw_zone_d(draw, g):
    y = ZONE_D_Y
    draw_hline(draw, 0, y, W, thickness=1)

    last_play = g.get("last_play", "")
    lbl_fnt   = bold_font(11)
    play_fnt  = regular_font(12)

    lbl_str = "LAST PLAY:"
    lbl_w   = text_w(draw, lbl_str, lbl_fnt)
    draw.text((10, y + 11), lbl_str, font=lbl_fnt, fill=0)

    max_w = W - lbl_w - 28
    while last_play and text_w(draw, last_play + "…", play_fnt) > max_w:
        last_play = last_play[:-1]
    if g.get("last_play", "") != last_play:
        last_play += "…"

    draw.text((lbl_w + 18, y + 11), last_play, font=play_fnt, fill=0)


# ---------------------------------------------------------------------------
# ZONE E — Line score (white bg, inning numbers above, 118px zone)
# ---------------------------------------------------------------------------

def _draw_zone_e(draw, g):
    y = ZONE_E_Y

    draw.rectangle([0, y, W, H], fill=255)
    draw_hline(draw, 0, y, W, thickness=2, fill=0)

    away_abbr    = g.get("away_abbr", "AWY")
    home_abbr    = g.get("home_abbr", "HME")
    away_innings = g.get("away_innings", [])
    home_innings = g.get("home_innings", [])
    away_score   = g.get("away_score", 0)
    home_score   = g.get("home_score", 0)
    away_hits    = g.get("away_hits",  0)
    home_hits    = g.get("home_hits",  0)
    away_errors  = g.get("away_errors", 0)
    home_errors  = g.get("home_errors", 0)
    current_inn  = g.get("inning", 1)
    inning_half  = g.get("inning_half", "Top")

    latest_inn = max(9, current_inn, len(away_innings), len(home_innings))
    extra_mode = latest_inn > 9
    if extra_mode:
        extra_start = 10 + ((max(current_inn, latest_inn) - 10) // 9) * 9
        display_innings = list(range(extra_start, extra_start + 9))
    else:
        display_innings = list(range(1, 10))

    # Fonts — bigger now that we have more room
    inn_hdr_fnt = bold_font(13)
    team_fnt    = bold_font(15)
    inn_fnt     = regular_font(15)
    tot_fnt     = bold_font(16)

    # Layout
    team_col_w  = 116 if extra_mode else 46
    rhe_col_w   = 32
    rhe_total_w = rhe_col_w * 3
    inn_area_w  = W - team_col_w - rhe_total_w - 4
    inn_col_w   = inn_area_w // len(display_innings)
    rhe_x       = W - rhe_total_w

    # Vertical positions within the 118px zone
    # Row layout: [inning numbers] [divider] [away] [divider] [home]
    inn_hdr_y  = y + 5      # inning number row
    divider1_y = y + 26     # line below inning numbers
    row_away_y = y + 32     # away team scores
    divider2_y = y + 58     # line between teams
    row_home_y = y + 64     # home team scores

    if extra_mode:
        flag_fnt = bold_font(9)
        draw.rectangle([4, y + 2, team_col_w - 6, divider1_y - 2], fill=0)
        for n, flag in enumerate(("EXTRA", "INNINGS")):
            fw = text_w(draw, flag, flag_fnt)
            draw.text(
                (max(4, (team_col_w - fw) // 2), y + 4 + n * 10),
                flag,
                font=flag_fnt,
                fill=255,
            )

    # Inning number headers
    for i, inning_no in enumerate(display_innings):
        col_x   = team_col_w + i * inn_col_w
        inn_cx  = col_x + inn_col_w // 2
        inn_str = str(inning_no)
        iw      = text_w(draw, inn_str, inn_hdr_fnt)
        is_cur  = (inning_no == current_inn)

        if is_cur:
            # Outline box for current inning header — filled black header, white number
            draw.rectangle([col_x, y + 2, col_x + inn_col_w - 1, divider1_y - 1], fill=0)
            draw.text((inn_cx - iw // 2, inn_hdr_y), inn_str, font=inn_hdr_fnt, fill=255)
        else:
            draw.text((inn_cx - iw // 2, inn_hdr_y), inn_str, font=inn_hdr_fnt, fill=0)

    # R H E headers
    for j, lbl in enumerate(("R", "H", "E")):
        cx = rhe_x + j * rhe_col_w + rhe_col_w // 2
        lw = text_w(draw, lbl, inn_hdr_fnt)
        draw.text((cx - lw // 2, inn_hdr_y), lbl, font=inn_hdr_fnt, fill=0)

    # Dividers
    draw_hline(draw, 0, divider1_y, W, thickness=1, fill=0)
    draw_hline(draw, 0, divider2_y, W, thickness=1, fill=0)
    draw_vline(draw, rhe_x - 2, y, H - y, thickness=2, fill=0)

    # Team abbreviations
    draw.text((4, row_away_y), away_abbr, font=team_fnt, fill=0)
    draw.text((4, row_home_y), home_abbr, font=team_fnt, fill=0)

    try:
        current_idx = max(0, int(current_inn) - 1)
    except (TypeError, ValueError):
        current_idx = 0

    def normalized_innings(values, total, completed_current=False):
        out = list(values)
        while len(out) <= current_idx:
            out.append(None)

        if completed_current and out[current_idx] is None:
            completed = sum(
                int(v)
                for i, v in enumerate(out)
                if i != current_idx and v is not None
            )
            out[current_idx] = max(0, int(total or 0) - completed)

        return out

    half = str(inning_half).lower()
    if half.startswith(("bot", "bottom", "b")):
        away_innings = normalized_innings(away_innings, away_score, completed_current=True)
        home_innings = normalized_innings(home_innings, home_score, completed_current=False)
        if len(home_innings) > current_idx:
            home_innings[current_idx] = None
    else:
        away_innings = normalized_innings(away_innings, away_score, completed_current=False)
        home_innings = normalized_innings(home_innings, home_score, completed_current=False)
        if len(away_innings) > current_idx:
            away_innings[current_idx] = None

    # Inning scores
    def draw_row(innings, row_y, total, hits, errors):
        for i, inning_no in enumerate(display_innings):
            score_idx = inning_no - 1
            col_x  = team_col_w + i * inn_col_w
            inn_cx = col_x + inn_col_w // 2
            is_cur = (inning_no == current_inn)

            if score_idx < len(innings) and innings[score_idx] is not None:
                val = str(innings[score_idx])
            else:
                val = ""

            vw = text_w(draw, val, inn_fnt)
            if is_cur:
                # Outline current inning without clearing values already drawn
                # for the other team's row.
                draw.rectangle(
                    [col_x, divider1_y, col_x + inn_col_w - 1, H - 1],
                    outline=0, width=2
                )
                draw.text((inn_cx - vw // 2, row_y), val, font=inn_fnt, fill=0)
            else:
                draw.text((inn_cx - vw // 2, row_y), val, font=inn_fnt, fill=0)

        # R H E totals
        for j, val in enumerate((str(total), str(hits), str(errors))):
            cx = rhe_x + j * rhe_col_w + rhe_col_w // 2
            vw = text_w(draw, val, tot_fnt)
            draw.text((cx - vw // 2, row_y), val, font=tot_fnt, fill=0)

    draw_row(away_innings, row_away_y, away_score, away_hits, away_errors)
    draw_row(home_innings, row_home_y, home_score, home_hits, home_errors)

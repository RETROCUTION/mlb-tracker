from PIL import Image, ImageDraw
from datetime import datetime
import os
import logging
logger = logging.getLogger(__name__)
import config
import settings_loader
from layouts.draw_utils import (
    bold_font, regular_font, score_font,
    draw_text_centered, draw_hline, draw_vline,
    text_w, text_h, format_date_long, format_time_local,
    format_datetime_short, ordinal, draw_clock_right
)

TZ = config.LOCAL_TZ
W = config.MASTER_W
H = config.MASTER_H

# ---------------------------------------------------------------------------
# LAYOUT TUNING
# ---------------------------------------------------------------------------

HEADER_H           = 44
FOOTER_RECORD_H    = 50
FOOTER_OUTLOOK_H   = 36
BODY_Y             = HEADER_H
BODY_H             = H - HEADER_H - FOOTER_RECORD_H - FOOTER_OUTLOOK_H

LOGO_SIZE          = 36
LOGO_X             = 8
LOGO_Y             = 4
TITLE_X            = 52
HEADER_DT_SIZE     = 12

LG_LABEL_Y         = 6
LG_LABEL_SIZE      = 11
LG_VS_SIZE         = 12
LG_DATE_Y          = 24
LG_VENUE_Y         = 44
LG_SCORE_Y         = 105
LG_SCORE_SIZE_WIN  = 130
LG_SCORE_SIZE_LOS  = 100
LG_SCORE_SIZE_LIV  = 115
LG_SCORE_GAP       = 20
LG_RESULT_OFFSET   = 12
LG_TEAM_LINE1_SIZE = 14
LG_TEAM_LINE2_SIZE = 16

NG_LABEL_Y         = 6
NG_LABEL_SIZE      = 11
NG_DATE_Y          = 24
NG_TIME_Y          = 44
NG_TIME_SIZE       = 62
NG_OPP_Y           = 150
NG_OPP_SIZE        = 18
NG_VENUE_Y         = 180
NG_PITCHERS_LBL_Y  = 210
NG_PITCHER1_Y      = 228
NG_PITCHER2_Y      = 250
NG_PITCHER_SIZE    = 18

# Opponent stats column — right side of next game panel
OPP_STATS_COL_W    = 120   # wider for better readability
OPP_STATS_X_OFF    = W - OPP_STATS_COL_W  # flush to right edge

REC_VAL_SIZE       = 17
REC_LBL_SIZE       = 10
REC_VAL_Y_OFF      = 5
REC_LBL_Y_OFF      = 28

OUT_LABEL_SIZE     = 12
OUT_VAL_SIZE       = 15
OUT_BAR_H          = 10
OUT_IDX_SIZE       = 11
OUT_BG_FILL        = 255

# ---------------------------------------------------------------------------

_logo_cache = {}


def _load_logo():
    path = os.path.join(config.LOGO_DIR, config.TEAM_LOGO)
    if path in _logo_cache:
        return _logo_cache[path]
    if not os.path.exists(path):
        return None
    try:
        img = Image.open(path).convert("RGBA")
        img = img.resize((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
        r, g, b, a = img.split()
        gray = img.convert("L")
        logo_1bit = Image.new("1", (LOGO_SIZE, LOGO_SIZE), 255)
        for x in range(LOGO_SIZE):
            for y in range(LOGO_SIZE):
                alpha = a.getpixel((x, y))
                pixel = gray.getpixel((x, y))
                if alpha > 128 and pixel < 180:
                    logo_1bit.putpixel((x, y), 0)
        _logo_cache[path] = logo_1bit
        return logo_1bit
    except Exception as e:
        logger.warning("Logo load failed: %s", e)
        return None


def _split_team_name(name):
    clean = " ".join((name or "").strip().split())

    for team in getattr(settings_loader, "ALL_TEAMS", []):
        if team.get("team_name", "").lower() == clean.lower():
            full_name = team["team_name"]
            nickname = _team_nickname(full_name)
            city = full_name[:len(full_name) - len(nickname)].strip()
            return (city.upper(), nickname.upper())

    parts = clean.split()
    if len(parts) == 1:
        return ("", parts[0].upper())

    return (" ".join(parts[:-1]).upper(), parts[-1].upper())


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


def _find_live_game(games):
    for g in games:
        if g["status"] == "Live":
            return g
    return None


def _find_last_completed(games):
    last = None
    for g in games:
        if g["status"] == "Final":
            last = g
    return last


def _find_next_game(games):
    for g in games:
        if g["status"] in ("Preview", "Pre-Game", "Scheduled"):
            return g
    return None


_logo_paste_info = {}   # used to pass opp logo coords from _draw_next_game to render


def render(state, summary, games):
    img  = Image.new("1", (W, H), 255)
    draw = ImageDraw.Draw(img)

    _logo_paste_info.clear()
    _draw_header(draw, img, state)
    _draw_left_panel(draw, games)
    _draw_next_game(draw, games, summary)
    _draw_body_dividers(draw)
    _draw_record_bar(draw, summary)
    _draw_outlook_bar(draw, summary)

    # Paste opponent logo if next game section loaded one
    if "opp_logo" in _logo_paste_info:
        img.paste(
            _logo_paste_info["opp_logo"],
            (_logo_paste_info["opp_logo_x"], _logo_paste_info["opp_logo_y"])
        )

    return img


def _draw_header(draw, img, state):
    draw.rectangle([0, 0, W, HEADER_H], fill=0)

    logo = _load_logo()
    if logo:
        img.paste(logo, (LOGO_X, LOGO_Y))

    draw.text(
        (TITLE_X, 14),
        config.APP_TITLE,
        font=bold_font(18),
        fill=255
    )

    label_fnt = regular_font(9)
    val_fnt   = regular_font(HEADER_DT_SIZE)
    now_local = datetime.now(TZ)

    if not state.stale:
        draw_clock_right(
            draw,
            W - 12,
            14,
            now_local,
            val_fnt,
            fill=255,
            label="ONLINE:",
            label_font=label_fnt,
            gap=8,
        )
    else:
        # Offline — show last sync time + OFFLINE badge
        if state.last_sync_time:
            sync_local = state.last_sync_time.astimezone(TZ)
            time_str   = sync_local.strftime("%a, %b %-d, %Y  %-I:%M %p PT")
            label_str  = "LAST SYNC:"
            label_w    = text_w(draw, label_str, label_fnt)
            val_w      = text_w(draw, time_str, val_fnt)
            total_w    = label_w + 8 + val_w
            draw.text((W - total_w - 12, 10), label_str, font=label_fnt, fill=255)
            draw.text((W - val_w - 12,    8), time_str,  font=val_fnt,   fill=255)

        # OFFLINE badge
        badge_fnt = regular_font(9)
        badge_str = "OFFLINE"
        bw = text_w(draw, badge_str, badge_fnt) + 8
        draw.rectangle([W - bw - 8, 26, W - 8, 40], fill=255)
        draw.text((W - bw - 4, 27), badge_str, font=badge_fnt, fill=0)

        draw_clock_right(
            draw,
            W - bw - 16,
            26,
            now_local,
            regular_font(11),
            fill=255,
        )


def _draw_body_dividers(draw):
    section_w = W // 2
    draw_vline(draw, section_w, BODY_Y, BODY_H, thickness=1)
    draw_hline(draw, 0, BODY_Y + BODY_H, W, thickness=1)


def _draw_left_panel(draw, games):
    live = _find_live_game(games)
    if live:
        _draw_game_score(draw, live, is_live=True, games=games)
    else:
        last = _find_last_completed(games)
        _draw_game_score(draw, last, is_live=False, games=games)


def _draw_game_score(draw, game, is_live, games=None):
    section_x = 0
    section_y = BODY_Y
    section_w = W // 2

    if game is None:
        draw.text(
            (section_x + 10, section_y + LG_LABEL_Y),
            "LAST GAME",
            font=bold_font(LG_LABEL_SIZE),
            fill=0
        )
        draw.text(
            (section_x + 10, section_y + 40),
            "No games found",
            font=regular_font(12),
            fill=0
        )
        return

    if is_live:
        label_text = "IN PROGRESS"
        label_bg   = True
    else:
        series = _get_series_info(games or [], game)
        label_text = f"LAST GAME - {series}" if series else "LAST GAME"
        label_bg   = False

    label_fnt = bold_font(LG_LABEL_SIZE)
    label_w   = text_w(draw, label_text, label_fnt)

    if label_bg:
        pad = 5
        draw.rectangle(
            [section_x + 8,
             section_y + LG_LABEL_Y - 2,
             section_x + 8 + label_w + pad * 2,
             section_y + LG_LABEL_Y + LG_LABEL_SIZE + 4],
            fill=0
        )
        draw.text(
            (section_x + 8 + pad, section_y + LG_LABEL_Y),
            label_text,
            font=label_fnt,
            fill=255
        )
        vs_x = section_x + 8 + label_w + pad * 2 + 8
    else:
        draw.text(
            (section_x + 10, section_y + LG_LABEL_Y),
            label_text,
            font=label_fnt,
            fill=0
        )
        vs_x = section_x + 10 + label_w + 8

    if is_live:
        vs_str = f"vs {game.get('opponent_name', '')}"
        draw.text(
            (vs_x, section_y + LG_LABEL_Y),
            vs_str,
            font=regular_font(LG_VS_SIZE),
            fill=0
        )

    dt_utc   = datetime.fromisoformat(game["date_utc"].replace("Z", "+00:00"))
    dt_local = dt_utc.astimezone(TZ)
    date_str = format_date_long(dt_local)
    time_str = format_time_local(dt_local)
    draw.text(
        (section_x + 10, section_y + LG_DATE_Y),
        f"{date_str}  {time_str}",
        font=regular_font(13),
        fill=0
    )

    ha = "Home" if game["home_away"] == "home" else "Away"
    draw.text(
        (section_x + 10, section_y + LG_VENUE_Y),
        f"{ha}  |  {game['venue']}",
        font=regular_font(12),
        fill=0
    )

    lad_score = game.get("dodgers_score") or 0
    opp_score = game.get("opponent_score") or 0

    if is_live:
        lad_size = LG_SCORE_SIZE_LIV
        opp_size = LG_SCORE_SIZE_LIV
    else:
        lad_wins = lad_score > opp_score
        lad_size = LG_SCORE_SIZE_WIN if lad_wins else LG_SCORE_SIZE_LOS
        opp_size = LG_SCORE_SIZE_LOS if lad_wins else LG_SCORE_SIZE_WIN

    lad_fnt  = score_font(lad_size)
    opp_fnt  = score_font(opp_size)
    dash_fnt = score_font(50)

    lad_str  = str(lad_score)
    opp_str  = str(opp_score)
    dash_str = "-"

    lad_w  = text_w(draw, lad_str, lad_fnt)
    opp_w  = text_w(draw, opp_str, opp_fnt)
    dash_w = text_w(draw, dash_str, dash_fnt)

    total_w     = lad_w + LG_SCORE_GAP + dash_w + LG_SCORE_GAP + opp_w
    start_x     = section_x + (section_w - total_w) // 2
    score_y     = section_y + LG_SCORE_Y
    opp_score_x = start_x + lad_w + LG_SCORE_GAP + dash_w + LG_SCORE_GAP

    line1_fnt = regular_font(LG_TEAM_LINE1_SIZE)
    line2_fnt = bold_font(LG_TEAM_LINE2_SIZE)

    lad_line1, lad_line2 = _split_team_name(config.TEAM_NAME)
    opp_line1, opp_line2 = _split_team_name(game["opponent_name"])

    lad_l1_w = text_w(draw, lad_line1, line1_fnt)
    lad_l2_w = text_w(draw, lad_line2, line2_fnt)
    lad_cx   = start_x + lad_w // 2

    draw.text(
        (lad_cx - lad_l1_w // 2, score_y - 28),
        lad_line1, font=line1_fnt, fill=0
    )
    draw.text(
        (lad_cx - lad_l2_w // 2, score_y - 16),
        lad_line2, font=line2_fnt, fill=0
    )

    opp_l1_w = text_w(draw, opp_line1, line1_fnt)
    opp_l2_w = text_w(draw, opp_line2, line2_fnt)
    opp_cx   = opp_score_x + opp_w // 2

    draw.text(
        (opp_cx - opp_l1_w // 2, score_y - 28),
        opp_line1, font=line1_fnt, fill=0
    )
    draw.text(
        (opp_cx - opp_l2_w // 2, score_y - 16),
        opp_line2, font=line2_fnt, fill=0
    )

    draw.text((start_x, score_y), lad_str, font=lad_fnt, fill=0)
    draw.text(
        (start_x + lad_w + LG_SCORE_GAP,
         score_y + (lad_size - 50) // 2),
        dash_str, font=dash_fnt, fill=0
    )
    draw.text(
        (opp_score_x, score_y + (lad_size - opp_size) // 2),
        opp_str, font=opp_fnt, fill=0
    )

    result_y = score_y + lad_size + LG_RESULT_OFFSET

    if is_live:
        inning      = game.get("inning", "")
        inning_half = game.get("inning_half", "")
        outs        = game.get("outs")

        half_label = "TOP"
        if str(inning_half).lower().startswith(("bot", "bottom", "b")):
            half_label = "BOTTOM"

        live_str = "LIVE"
        if inning:
            live_str = f"LIVE  |  {half_label} OF {ordinal(inning)}".upper()

        live_fnt = bold_font(16)
        live_w = text_w(draw, live_str, live_fnt)
        status_h = 28
        outs_text = ""
        outs_w = 0
        outs_fnt = bold_font(15)

        if outs is not None:
            try:
                outs_int = int(outs)
            except (TypeError, ValueError):
                outs_int = 0
            outs_text = f"{outs_int} OUT" if outs_int == 1 else f"{outs_int} OUTS"
            outs_w = text_w(draw, outs_text, outs_fnt)

        gap = 14 if outs_text else 0
        total_status_w = live_w + gap + outs_w
        status_x = section_x + (section_w - total_status_w) // 2

        draw.rectangle(
            [status_x - 4, result_y,
             status_x + live_w + 4, result_y + status_h],
            fill=0
        )
        draw.text(
            (status_x, result_y + 5),
            live_str, font=live_fnt, fill=255
        )

        if outs_text:
            draw.text(
                (status_x + live_w + gap, result_y + 6),
                outs_text,
                font=outs_fnt,
                fill=0,
            )
    else:
        result = game.get("result", "")

        winner = game.get("decision_winner")
        loser  = game.get("decision_loser")
        if winner and loser:
            decision_text = f"W: {winner}   L: {loser}"
            decision_fnt = regular_font(14)
            decision_w = text_w(draw, decision_text, decision_fnt)
            draw.text(
                (section_x + (section_w - decision_w) // 2, result_y + 4),
                decision_text,
                font=decision_fnt,
                fill=0,
            )

        if result in ("W", "L"):
            outcome_text = f"{config.TEAM_NICKNAME.upper()} WIN!" if result == "W" else "LOSS"
            outcome_fnt = score_font(38)
            outcome_w = text_w(draw, outcome_text, outcome_fnt)
            draw.text(
                (section_x + (section_w - outcome_w) // 2, result_y + 30),
                outcome_text,
                font=outcome_fnt,
                fill=0,
            )


def _load_opp_logo(abbr, size=36):
    """Load opponent team logo for display in next game section."""
    path = os.path.join(config.LOGO_DIR, f"{abbr}.png")
    key  = (path, size)
    if key in _logo_cache:
        return _logo_cache[key]
    if not os.path.exists(path):
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
    except Exception:
        return None


def _get_series_info(games, target, compact=False):
    """
    Detect which game of the series this is.
    Returns e.g. "GAME 2 OF 3", "G2/3", or None.
    """
    if not target:
        return None

    opp_id = target.get("opponent_id")
    if not opp_id:
        return None

    target_key = (
        target.get("game_pk"),
        target.get("date_utc", "")[:10],
        target.get("game_number", 1),
    )
    target_idx = None

    for i, g in enumerate(games):
        key = (
            g.get("game_pk"),
            g.get("date_utc", "")[:10],
            g.get("game_number", 1),
        )
        if key == target_key:
            target_idx = i
            break

    if target_idx is None:
        return None

    start = target_idx
    while start > 0 and games[start - 1].get("opponent_id") == opp_id:
        start -= 1

    end = target_idx
    while end + 1 < len(games) and games[end + 1].get("opponent_id") == opp_id:
        end += 1

    series_games = games[start:end + 1]

    if len(series_games) < 2:
        return None

    game_no = target_idx - start + 1
    if compact:
        return f"G{game_no}/{len(series_games)}"

    return f"GAME {game_no} OF {len(series_games)}"


def _division_short_name(name):
    if not name:
        return "DIV"

    return (
        name.upper()
        .replace("NATIONAL LEAGUE", "NL")
        .replace("AMERICAN LEAGUE", "AL")
    )


def _get_opp_stats(summary, opp_id):
    """Pull opponent team stats from the summary all_teams cache, with div rank."""
    if not summary or not opp_id:
        return None
    all_teams = summary.get("all_teams", [])
    opp = next((t for t in all_teams if t.get("team_id") == opp_id), None)
    if not opp:
        return None

    # Compute division rank from nl_west or by finding teams in same division
    div_id    = opp.get("division_id")
    div_teams = [t for t in all_teams if t.get("division_id") == div_id]
    div_teams.sort(key=lambda t: (-t.get("pct", 0), -t.get("wins", 0)))
    div_rank  = next(
        (i + 1 for i, t in enumerate(div_teams) if t.get("team_id") == opp_id), None
    )
    opp = dict(opp)   # don't mutate cache
    opp["computed_div_rank"] = div_rank
    return opp


def _draw_next_game(draw, games, summary=None):
    nxt = _find_next_game(games)

    section_x = W // 2
    section_y = BODY_Y

    series = _get_series_info(games, nxt)
    label = f"NEXT GAME - {series}" if series else "NEXT GAME"

    draw.text(
        (section_x + 10, section_y + NG_LABEL_Y),
        label,
        font=bold_font(NG_LABEL_SIZE),
        fill=0
    )

    if not nxt:
        draw.text(
            (section_x + 10, section_y + 40),
            "No upcoming games",
            font=regular_font(12),
            fill=0
        )
        return

    dt_utc   = datetime.fromisoformat(nxt["date_utc"].replace("Z", "+00:00"))
    dt_local = dt_utc.astimezone(TZ)

    draw.text(
        (section_x + 10, section_y + NG_DATE_Y),
        format_date_long(dt_local),
        font=regular_font(14),
        fill=0
    )

    draw.text(
        (section_x + 10, section_y + NG_TIME_Y),
        format_time_local(dt_local),
        font=score_font(NG_TIME_SIZE),
        fill=0
    )

    opp_abbr = nxt.get("opponent_abbr", "OPP")
    opp_name = nxt.get("opponent_name", "")
    opp_id   = nxt.get("opponent_id")
    opp_logo = _load_opp_logo(opp_abbr, 36)
    opp_y    = section_y + NG_OPP_Y

    # Team name first, then logo to the right
    opp_name_str = f"vs {opp_name}"
    name_x       = section_x + 10
    draw.text(
        (name_x, opp_y),
        opp_name_str,
        font=bold_font(NG_OPP_SIZE),
        fill=0
    )

    if opp_logo:
        logo_x = name_x + text_w(draw, opp_name_str, bold_font(NG_OPP_SIZE)) + 10
        _logo_paste_info["opp_logo"]   = opp_logo
        _logo_paste_info["opp_logo_x"] = logo_x
        _logo_paste_info["opp_logo_y"] = opp_y - 4

    ha = "Home" if nxt["home_away"] == "home" else "Away"
    venue = nxt.get("venue", "")
    draw.text(
        (section_x + 10, section_y + NG_VENUE_Y),
        f"{ha}  |  {venue}",
        font=regular_font(14),
        fill=0
    )

    lad_p = nxt.get("probable_pitcher_dodgers") or "TBD"
    opp_p = nxt.get("probable_pitcher_opponent") or "TBD"

    draw.text(
        (section_x + 10, section_y + NG_PITCHERS_LBL_Y),
        "Probable Pitchers:",
        font=regular_font(13),
        fill=0
    )

    lbl_fnt  = bold_font(NG_PITCHER_SIZE)
    name_fnt = regular_font(NG_PITCHER_SIZE)
    my_lbl   = f"{config.TEAM_ABBR}:"
    opp_lbl  = f"{opp_abbr}:"

    lbl_w = max(
        text_w(draw, my_lbl,  lbl_fnt),
        text_w(draw, opp_lbl, lbl_fnt)
    ) + 8

    draw.text((section_x + 10, section_y + NG_PITCHER1_Y), my_lbl,  font=lbl_fnt,  fill=0)
    draw.text((section_x + 10 + lbl_w, section_y + NG_PITCHER1_Y), lad_p, font=name_fnt, fill=0)

    draw.text((section_x + 10, section_y + NG_PITCHER2_Y), opp_lbl, font=lbl_fnt,  fill=0)
    draw.text((section_x + 10 + lbl_w, section_y + NG_PITCHER2_Y), opp_p, font=name_fnt, fill=0)

    # ---- Opponent stats column — right side ----
    opp = _get_opp_stats(summary, opp_id)
    if opp:
        _draw_opp_stats_column(draw, opp, section_y)


def _draw_opp_stats_column(draw, opp, section_y):
    """Draw vertical opponent stats column on right side of next game panel."""
    col_x   = OPP_STATS_X_OFF
    col_w   = OPP_STATS_COL_W
    val_fnt = bold_font(15)
    lbl_fnt = regular_font(9)
    hdr_fnt = bold_font(10)
    row_h   = 38

    wins      = opp.get("wins", 0)
    losses    = opp.get("losses", 0)
    pct       = opp.get("pct", 0.0)
    rank      = opp.get("mlb_rank", "—")
    l10w      = opp.get("last_10_wins", 0)
    l10l      = opp.get("last_10_losses", 0)
    rdiff     = opp.get("run_differential", 0)
    rdiff_str = f"+{rdiff}" if rdiff > 0 else str(rdiff)
    abbr      = opp.get("team_abbr", "OPP")

    div_rank_val = opp.get("computed_div_rank")
    div_name     = opp.get("division_name", "")
    div_short = _division_short_name(div_name)

    stats = [
        (f"{wins}-{losses}",                                              "RECORD"),
        (f"{pct:.3f}",                                                    "WPCT"),
        (f"{div_short} {ordinal(div_rank_val)}" if div_rank_val else "—", "DIV RANK"),
        (f"{ordinal(rank)}",                                              "MLB RANK"),
        (f"{l10w}-{l10l}",                                               "LAST 10"),
        (rdiff_str,                                                       "RUN DIFF"),
    ]

    # Header box
    hdr_h   = 22
    hdr_y   = section_y + 4
    hdr_str = f"{abbr} STATS"
    hw      = text_w(draw, hdr_str, hdr_fnt)
    draw.rectangle([col_x, hdr_y, col_x + col_w, hdr_y + hdr_h], fill=0)
    draw.text((col_x + (col_w - hw) // 2, hdr_y + 5), hdr_str, font=hdr_fnt, fill=255)

    # Stat rows — fully enclosed outer border
    total_h = len(stats) * row_h
    box_top = hdr_y + hdr_h
    box_bot = box_top + total_h
    draw.rectangle([col_x, box_top, col_x + col_w, box_bot], outline=0, width=1)

    for i, (val, lbl) in enumerate(stats):
        y = box_top + i * row_h
        if i > 0:
            draw_hline(draw, col_x, y, col_w, thickness=1)

        row_val_fnt = val_fnt
        if text_w(draw, val, row_val_fnt) > col_w - 8:
            row_val_fnt = bold_font(13)
        if text_w(draw, val, row_val_fnt) > col_w - 8:
            row_val_fnt = bold_font(11)

        vw = text_w(draw, val, row_val_fnt)
        lw = text_w(draw, lbl, lbl_fnt)
        draw.text((col_x + (col_w - vw) // 2, y + 4),  val, font=row_val_fnt, fill=0)
        draw.text((col_x + (col_w - lw) // 2, y + 22), lbl, font=lbl_fnt, fill=0)


def _draw_record_bar(draw, summary):
    bar_y = H - FOOTER_RECORD_H - FOOTER_OUTLOOK_H
    draw_hline(draw, 0, bar_y, W, thickness=1)

    if not summary:
        draw.text(
            (10, bar_y + 10),
            "No standings data",
            font=regular_font(11),
            fill=0
        )
        return

    r          = summary["record"]
    record_str = f"{r['wins']}-{r['losses']}"

    pct        = summary.get("pct", 0.0)
    pct_str    = f"{pct:.3f}"

    nl_rank = summary.get("division_rank", summary.get("nl_west_rank", 0))
    try:
        nl_rank_int = int(nl_rank)
    except (TypeError, ValueError):
        nl_rank_int = 0

    div_name = summary.get("division_name", "")
    if not div_name:
        for t in summary.get("all_teams", []):
            if t.get("team_id") == config.TEAM_ID:
                div_name = t.get("division_name", "")
                break

    div_short = _division_short_name(div_name)
    div_str = f"{div_short} {ordinal(nl_rank_int)}" if nl_rank_int else f"{div_short} —"
    mlb_rank   = summary.get("mlb_rank", "-")
    mlb_total  = summary.get("mlb_total_teams", 30)
    l10w       = summary.get("last_10_wins", 0)
    l10l       = summary.get("last_10_losses", 0)
    rdiff      = summary.get("run_differential", 0)
    rdiff_str  = f"+{rdiff}" if rdiff > 0 else str(rdiff)

    stats = [
        (record_str,            "RECORD"),
        (pct_str,               "WPCT"),
        (div_str,               "DIV RANK"),
        (f"{ordinal(mlb_rank)}","MLB RANK"),
        (f"{l10w}-{l10l}",      "LAST 10"),
        (rdiff_str,             "RUN DIFF"),
    ]

    n       = len(stats)       # 6
    col_w   = W // n           # 133px
    val_fnt = bold_font(REC_VAL_SIZE)
    lbl_fnt = regular_font(REC_LBL_SIZE)

    for i, (val, lbl) in enumerate(stats):
        # Use exact pixel positions so divider 3 lands exactly at W//2 = 400
        x_start = (i * W) // n
        x_end   = ((i + 1) * W) // n
        cw      = x_end - x_start

        if i > 0:
            draw_vline(
                draw, x_start, bar_y + 6,
                FOOTER_RECORD_H - 12,
                thickness=1,
                fill=0
            )
        draw_text_centered(draw, x_start, bar_y + REC_VAL_Y_OFF, cw, val, val_fnt)
        draw_text_centered(draw, x_start, bar_y + REC_LBL_Y_OFF, cw, lbl, lbl_fnt, fill=0)


def _draw_outlook_bar(draw, summary):
    bar_y = H - FOOTER_OUTLOOK_H
    draw_hline(draw, 0, bar_y, W, thickness=1)

    if not summary:
        return

    if summary.get("season_not_started"):
        message = summary.get("season_message") or "Next season has not started yet"
        message = message.upper()
        msg_fnt = bold_font(14)
        if text_w(draw, message, msg_fnt) > W - 24:
            msg_fnt = bold_font(12)
        msg_w = text_w(draw, message, msg_fnt)
        draw.rectangle([0, bar_y, W, H], fill=0)
        draw.text(
            ((W - msg_w) // 2, bar_y + 10),
            message,
            font=msg_fnt,
            fill=255,
        )
        return

    index = summary.get("ws_index", 0)
    label = summary.get("ws_label", ws_label_fallback(index))

    label_str = "WORLD SERIES CHANCES:"
    label_x   = 12
    label_fnt = regular_font(OUT_LABEL_SIZE)
    val_fnt   = bold_font(OUT_VAL_SIZE)

    draw.text((label_x, bar_y + 10), label_str, font=label_fnt, fill=0)

    # Draw the text label (e.g. "VERY LIKELY") instead of percentage
    label_val_x = label_x + text_w(draw, label_str, label_fnt) + 12
    draw.text((label_val_x, bar_y + 6), label, font=val_fnt, fill=0)

    # Progress bar starts after the label value
    bar_x     = label_val_x + text_w(draw, label, val_fnt) + 16
    bar_right = W - 80
    bar_w     = bar_right - bar_x
    bar_mid_y = bar_y + (FOOTER_OUTLOOK_H // 2)

    # Only draw bar if there's enough room
    if bar_w > 20:
        draw.rectangle(
            [bar_x,     bar_mid_y - OUT_BAR_H // 2,
             bar_right, bar_mid_y + OUT_BAR_H // 2],
            outline=0, width=1
        )

        fill_w = int(bar_w * index / 100)
        if fill_w > 2:
            draw.rectangle(
                [bar_x + 1,      bar_mid_y - OUT_BAR_H // 2 + 1,
                 bar_x + fill_w, bar_mid_y + OUT_BAR_H // 2 - 1],
                fill=0
            )

    draw.text(
        (bar_right + 8, bar_mid_y - 6),
        f"{index}/100",
        font=regular_font(OUT_IDX_SIZE),
        fill=0
    )


def ws_label_fallback(index):
    """Fallback if ws_label not yet in cached summary (pre-sync)."""
    if index >= 90:
        return "ABSOLUTELY"
    elif index >= 75:
        return "VERY LIKELY"
    elif index >= 60:
        return "GOOD CHANCE"
    elif index >= 45:
        return "POSSIBLE"
    elif index >= 30:
        return "UNLIKELY"
    else:
        return "NOT LOOKING GOOD"

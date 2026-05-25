from PIL import Image, ImageDraw
from datetime import datetime
import logging
import math
import config
from layouts.draw_utils import (
    bold_font, regular_font,
    draw_hline, draw_vline,
    text_w, ordinal, draw_clock_right
)

logger = logging.getLogger(__name__)

TZ = config.LOCAL_TZ
W  = config.MASTER_W
H  = config.MASTER_H

HEADER_H   = 40
COL_HDR_H  = 22
ROW_AREA_H = H - HEADER_H - COL_HDR_H

TEAMS_PER_COL = 15
COL_W = W // 2

OFF_RANK = 6
OFF_TEAM = 30
OFF_W    = 88
OFF_L    = 116
OFF_PCT  = 146
OFF_GB   = 196
OFF_L10  = 232
OFF_DIFF = 282
OFF_STRK = 342

TZ = config.LOCAL_TZ


def render(state, summary):
    img  = Image.new("1", (W, H), 255)
    draw = ImageDraw.Draw(img)

    all_teams = []
    if summary:
        all_teams = summary.get("all_teams", [])

    _draw_header(draw, state)
    _draw_column_headers(draw)
    _draw_teams(draw, all_teams, summary)

    return img


def _draw_header(draw, state):
    draw.rectangle([0, 0, W, HEADER_H], fill=0)

    season = config.CURRENT_SEASON
    if getattr(state, "display_season", None):
        season = state.display_season

    draw.text(
        (10, 12),
        f"MLB RANKINGS  {season}",
        font=bold_font(22),
        fill=255
    )

    label_fnt = regular_font(9)
    val_fnt   = regular_font(config.HEADER_CLOCK_FONT_SIZE)
    now_local = datetime.now(TZ)

    if not state.stale:
        draw_clock_right(
            draw,
            W - 10,
            14,
            now_local,
            val_fnt,
            fill=255,
            label="ONLINE:",
            label_font=label_fnt,
        )
    else:
        if state.last_sync_time:
            sync_local = state.last_sync_time.astimezone(TZ)
            time_str   = sync_local.strftime("%-I:%M %p PT")
            lbl_str    = "LAST SYNC:"
            lw = text_w(draw, lbl_str, label_fnt)
            tw = text_w(draw, time_str, val_fnt)
            draw.text((W - lw - tw - 10, 10), lbl_str,  font=label_fnt, fill=255)
            draw.text((W - tw - 10,       8), time_str, font=val_fnt,   fill=255)
        bw = text_w(draw, "OFFLINE", label_fnt) + 8
        draw.rectangle([W - bw - 8, 26, W - 8, 38], fill=255)
        draw.text((W - bw - 4, 27), "OFFLINE", font=label_fnt, fill=0)
        draw_clock_right(
            draw,
            W - bw - 16,
            26,
            now_local,
            val_fnt,
            fill=255,
        )


def _draw_column_headers(draw):
    hdr_y = HEADER_H
    draw.rectangle([0, hdr_y, W, hdr_y + COL_HDR_H], fill=0)

    fnt  = bold_font(11)
    fill = 255

    for base_x in (0, COL_W):
        draw.text((base_x + OFF_RANK, hdr_y + 6), "#",    font=fnt, fill=fill)
        draw.text((base_x + OFF_TEAM, hdr_y + 6), "TEAM", font=fnt, fill=fill)
        draw.text((base_x + OFF_W,    hdr_y + 6), "W",    font=fnt, fill=fill)
        draw.text((base_x + OFF_L,    hdr_y + 6), "L",    font=fnt, fill=fill)
        draw.text((base_x + OFF_PCT,  hdr_y + 6), "PCT",  font=fnt, fill=fill)
        draw.text((base_x + OFF_GB,   hdr_y + 6), "GB",   font=fnt, fill=fill)
        draw.text((base_x + OFF_L10,  hdr_y + 6), "L10",  font=fnt, fill=fill)
        draw.text((base_x + OFF_DIFF, hdr_y + 6), "RD",   font=fnt, fill=fill)
        draw.text((base_x + OFF_STRK, hdr_y + 6), "STRK", font=fnt, fill=fill)

    draw_hline(draw, 0, hdr_y + COL_HDR_H, W, thickness=1, fill=0)


def _draw_teams(draw, all_teams, summary):
    row_y_start = HEADER_H + COL_HDR_H

    rank_fnt   = bold_font(13)
    abbr_fnt   = bold_font(15)
    stat_fnt   = regular_font(13)
    detail_fnt = regular_font(12)

    highlight_id = config.TEAM_ID
    try:
        from layouts import _settings
        highlight_id = _settings.get("team_id", config.TEAM_ID)
    except Exception:
        pass

    rows_per_col = max(1, math.ceil(len(all_teams) / 2))
    left_teams  = all_teams[:rows_per_col]
    right_teams = all_teams[rows_per_col: rows_per_col * 2]

    for col_idx, teams in enumerate((left_teams, right_teams)):
        base_x = 0 if col_idx == 0 else COL_W

        for row_i, team in enumerate(teams):
            row_top      = row_y_start + (row_i * ROW_AREA_H) // rows_per_col
            row_bottom   = row_y_start + ((row_i + 1) * ROW_AREA_H) // rows_per_col
            row_h        = row_bottom - row_top
            y            = row_top
            is_my_team   = team.get("team_id") == highlight_id
            mid_y        = y + row_h // 2 - 8

            if is_my_team:
                draw.rectangle([base_x, y, base_x + COL_W - 1, row_bottom - 1], fill=0)
                txt = dim = 255
            else:
                txt = dim = 0

            draw_hline(draw, base_x, row_bottom - 1, COL_W, thickness=1, fill=0)

            rank   = team.get("mlb_rank", row_i + 1 + col_idx * TEAMS_PER_COL)
            abbr   = team.get("team_abbr", "???")
            wins   = team.get("wins", 0)
            losses = team.get("losses", 0)
            pct    = team.get("pct", 0.0)
            gb     = team.get("games_back", "-")
            l10w   = team.get("last_10_wins", 0)
            l10l   = team.get("last_10_losses", 0)
            rdiff  = team.get("run_differential", 0)
            rdiff_str = f"+{rdiff}" if rdiff > 0 else str(rdiff)
            streak = team.get("streak", "")

            draw.text((base_x + OFF_RANK, mid_y), str(rank),        font=rank_fnt,   fill=txt)
            draw.text((base_x + OFF_TEAM, mid_y), abbr,             font=abbr_fnt,   fill=txt)
            draw.text((base_x + OFF_W,    mid_y), str(wins),        font=stat_fnt,   fill=txt)
            draw.text((base_x + OFF_L,    mid_y), str(losses),      font=stat_fnt,   fill=txt)
            draw.text((base_x + OFF_PCT,  mid_y), f"{pct:.3f}",     font=detail_fnt, fill=dim)
            draw.text((base_x + OFF_GB,   mid_y), str(gb),          font=detail_fnt, fill=dim)
            draw.text((base_x + OFF_L10,  mid_y), f"{l10w}-{l10l}", font=detail_fnt, fill=dim)
            draw.text((base_x + OFF_DIFF, mid_y), rdiff_str,        font=detail_fnt, fill=dim)
            draw.text((base_x + OFF_STRK, mid_y), streak,           font=detail_fnt, fill=dim)

    draw_vline(draw, COL_W, HEADER_H, H - HEADER_H, thickness=1, fill=0)

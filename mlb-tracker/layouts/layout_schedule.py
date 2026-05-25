from PIL import Image, ImageDraw
from datetime import datetime
import os
import logging
import config
from layouts.draw_utils import (
    bold_font, regular_font,
    draw_hline,
    text_w, draw_clock_right
)

logger = logging.getLogger(__name__)

TZ = config.LOCAL_TZ
W = config.MASTER_W
H = config.MASTER_H
PAGE_SIZE = config.SCHEDULE_PAGE_SIZE

HEADER_H = 42
COL_HDR_H = 28
FOOTER_H = 0
ROW_AREA_H = H - HEADER_H - COL_HDR_H - FOOTER_H
ROW_H = ROW_AREA_H // PAGE_SIZE

COL = {
    "date": 10,
    "opp": 140,
    "ha": 400,
    "score": 470,
    "result": 625,
}

COL_W = {
    "ha": 62,
    "score": 140,
    "result": 52,
}

_logo_cache = {}


def _draw_centered(draw, x, y, width, text, fnt, fill=0):
    tw = text_w(draw, text, fnt)
    draw.text((x + (width - tw) // 2, y), text, font=fnt, fill=fill)


def _load_logo():
    path = os.path.join(config.LOGO_DIR, config.TEAM_LOGO)

    if path in _logo_cache:
        return _logo_cache[path]

    if not os.path.exists(path):
        return None

    try:
        img = Image.open(path).convert("RGBA")
        img = img.resize((32, 32), Image.LANCZOS)

        _, _, _, a = img.split()
        gray = img.convert("L")

        logo_1bit = Image.new("1", (32, 32), 255)

        for x in range(32):
            for y in range(32):
                alpha = a.getpixel((x, y))
                pixel = gray.getpixel((x, y))

                if alpha > 128 and pixel < 180:
                    logo_1bit.putpixel((x, y), 0)

        _logo_cache[path] = logo_1bit
        return logo_1bit

    except Exception as e:
        logger.warning("Logo load failed: %s", e)
        return None


def render(state, games):
    img = Image.new("1", (W, H), 255)
    draw = ImageDraw.Draw(img)

    _draw_header(draw, img, state, games)
    _draw_column_headers(draw)
    _draw_rows(draw, state, games)

    return img


def _draw_header(draw, img, state, games):
    draw.rectangle([0, 0, W, HEADER_H], fill=0)

    logo = _load_logo()
    if logo:
        img.paste(logo, (6, 5))

    title_fnt = bold_font(20)
    nav_fnt = regular_font(12)
    page_fnt = regular_font(11)
    clock_fnt = regular_font(config.HEADER_CLOCK_FONT_SIZE)

    draw.text(
        (46, 12),
        f"{config.TEAM_NICKNAME.upper()} SCHEDULE  {getattr(state, 'display_season', config.CURRENT_SEASON)}",
        font=title_fnt,
        fill=255
    )

    game_count = (
        len(games)
        if games is not None
        else getattr(state, "schedule_game_count", 0)
    )
    total_pages = max(1, -(-game_count // PAGE_SIZE))
    current_page = (state.schedule_offset // PAGE_SIZE) + 1
    page_str = f"Page {current_page} / {total_pages}"

    draw_clock_right(
        draw,
        W - 12,
        3,
        datetime.now(TZ),
        clock_fnt,
        fill=255,
        label="ONLINE:",
        label_font=regular_font(9),
        show_date=True,
        date_font=regular_font(config.HEADER_DATE_FONT_SIZE),
        show_wifi=True,
    )

    score_center_x = COL["score"] + COL_W["score"] // 2
    pw = text_w(draw, page_str, page_fnt)
    draw.text((score_center_x - pw // 2, 7), page_str, font=page_fnt, fill=255)

    prev_str = "< PREV"
    next_str = "NEXT >"
    nav_gap = 14
    prev_w = text_w(draw, prev_str, nav_fnt)
    next_w = text_w(draw, next_str, nav_fnt)
    nav_x = score_center_x - (prev_w + nav_gap + next_w) // 2
    draw.text((nav_x, 24), prev_str, font=nav_fnt, fill=255)
    draw.text((nav_x + prev_w + nav_gap, 24), next_str, font=nav_fnt, fill=255)

    draw_hline(draw, 0, HEADER_H - 1, W, thickness=1, fill=0)


def _draw_column_headers(draw):
    hdr_y = HEADER_H
    draw.rectangle([0, hdr_y, W, hdr_y + COL_HDR_H], fill=0)

    fnt = bold_font(12)
    fill = 255

    draw.text((COL["date"], hdr_y + 8), "DATE", font=fnt, fill=fill)
    draw.text((COL["opp"], hdr_y + 8), "OPPONENT", font=fnt, fill=fill)
    _draw_centered(draw, COL["ha"], hdr_y + 8, COL_W["ha"], "H/A", fnt, fill=fill)
    _draw_centered(
        draw,
        COL["score"],
        hdr_y + 8,
        COL_W["score"],
        "SCORE / TIME",
        fnt,
        fill=fill,
    )
    _draw_centered(
        draw,
        COL["result"],
        hdr_y + 8,
        COL_W["result"],
        "W/L",
        fnt,
        fill=fill,
    )

    draw_hline(draw, 0, hdr_y + COL_HDR_H, W, thickness=1, fill=0)


def _draw_rows(draw, state, games):
    offset = state.schedule_offset
    visible = games[offset: offset + PAGE_SIZE]

    next_idx = None

    for i, g in enumerate(games):
        if g["status"] in ("Preview", "Pre-Game", "Scheduled"):
            next_idx = i
            break

    row_start_y = HEADER_H + COL_HDR_H

    date_fnt = regular_font(13)
    wkday_fnt = regular_font(11)
    opp_fnt = bold_font(15)
    detail_fnt = regular_font(12)
    score_fnt = bold_font(15)
    result_fnt = bold_font(16)
    live_fnt = regular_font(10)

    for row_i, g in enumerate(visible):
        global_idx = offset + row_i
        y = row_start_y + row_i * ROW_H
        is_next = global_idx == next_idx
        fg = 255 if is_next else 0

        if is_next:
            draw.rectangle([0, y, W, y + ROW_H - 1], fill=0)

        draw_hline(draw, 0, y + ROW_H - 1, W, thickness=1, fill=0)

        dt_utc = datetime.fromisoformat(g["date_utc"].replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone(TZ)

        weekday = dt_local.strftime("%a")
        date_str = dt_local.strftime("%b %-d, %Y")
        mid_y = y + ROW_H // 2

        draw.text((COL["date"], mid_y - 14), weekday, font=wkday_fnt, fill=fg)
        draw.text((COL["date"], mid_y - 1), date_str, font=date_fnt, fill=fg)

        opp_x = COL["opp"]

        if is_next:
            badge_fnt = bold_font(9)
            bw = text_w(draw, "NEXT", badge_fnt) + 12

            draw.rectangle([opp_x, y + 6, opp_x + bw, y + 23], outline=fg, width=2)
            draw.text((opp_x + 6, y + 8), "NEXT", font=badge_fnt, fill=fg)

            opp_x = opp_x + bw + 8

        draw.text(
            (opp_x, mid_y - 9),
            g["opponent_name"],
            font=opp_fnt,
            fill=fg
        )

        ha_str = "Home" if g["home_away"] == "home" else "Away"

        _draw_centered(draw, COL["ha"], mid_y - 7, COL_W["ha"], ha_str, detail_fnt, fill=fg)

        status = g["status"]

        if status == "Final":
            lad = g.get("dodgers_score") or 0
            opp = g.get("opponent_score") or 0

            _draw_centered(
                draw,
                COL["score"],
                mid_y - 9,
                COL_W["score"],
                f"{lad} - {opp}",
                score_fnt,
                fill=fg,
            )

            _draw_centered(
                draw,
                COL["result"],
                mid_y - 9,
                COL_W["result"],
                g.get("result", ""),
                result_fnt,
                fill=fg,
            )

        elif status == "Live":
            lad = g.get("dodgers_score") or 0
            opp = g.get("opponent_score") or 0

            _draw_centered(
                draw,
                COL["score"],
                mid_y - 13,
                COL_W["score"],
                f"{lad} - {opp}",
                score_fnt,
                fill=fg,
            )

            _draw_centered(
                draw,
                COL["score"],
                mid_y + 5,
                COL_W["score"],
                "LIVE",
                live_fnt,
                fill=fg,
            )

        else:
            time_str = dt_local.strftime("%-I:%M %p PT")

            _draw_centered(
                draw,
                COL["score"],
                mid_y - 7,
                COL_W["score"],
                time_str,
                detail_fnt,
                fill=fg,
            )

            _draw_centered(
                draw,
                COL["result"],
                mid_y - 7,
                COL_W["result"],
                "-",
                result_fnt,
                fill=fg,
            )

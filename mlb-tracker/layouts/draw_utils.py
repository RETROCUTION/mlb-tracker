from PIL import ImageFont
import config

_font_cache = {}


def font(path, size):
    key = (path, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, size)
    return _font_cache[key]


def score_font(size):
    return font(config.FONT_SCORE, size)


def bold_font(size):
    return font(config.FONT_BOLD, size)


def regular_font(size):
    return font(config.FONT_REGULAR, size)


def text_w(draw, text, fnt):
    bbox = draw.textbbox((0, 0), text, font=fnt)
    return bbox[2] - bbox[0]


def text_h(draw, text, fnt):
    bbox = draw.textbbox((0, 0), text, font=fnt)
    return bbox[3] - bbox[1]


def draw_text_centered(draw, x, y, width, text, fnt, fill=0):
    w = text_w(draw, text, fnt)
    draw.text((x + (width - w) // 2, y), text, font=fnt, fill=fill)


def draw_hline(draw, x, y, width, thickness=2, fill=0):
    draw.rectangle([x, y, x + width, y + thickness], fill=fill)


def draw_vline(draw, x, y, height, thickness=2, fill=0):
    draw.rectangle([x, y, x + thickness, y + height], fill=fill)


def draw_rect_outline(draw, x, y, w, h, thickness=2, fill=0):
    draw.rectangle([x, y, x + w, y + h], outline=fill, width=thickness)


def format_date_long(dt):
    return dt.strftime("%A, %B %-d, %Y")


def format_time_local(dt):
    return dt.strftime("%-I:%M %p PT")


def format_clock_local(dt, show_seconds=True):
    if show_seconds:
        return dt.strftime("%-I:%M:%S %p PT")

    return dt.strftime("%-I:%M %p PT")


def format_header_date(dt):
    return dt.strftime("%b %-d, %Y").upper()


def format_datetime_short(dt):
    return dt.strftime("%a, %b %-d, %Y  %-I:%M %p PT")


def ordinal(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n)
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def draw_clock_right(draw, right_x, y, now, fnt, fill=0, label=None,
                     label_font=None, gap=6, show_date=False,
                     date_font=None, date_gap=15, show_seconds=False):
    time_str = format_clock_local(now, show_seconds=show_seconds)
    tw = text_w(draw, time_str, fnt)

    if label:
        label_font = label_font or fnt
        lw = text_w(draw, label, label_font)
        total_w = lw + gap + tw
        x = right_x - total_w
        draw.text((x, y + 2), label, font=label_font, fill=fill)
        draw.text((right_x - tw, y), time_str, font=fnt, fill=fill)
        if show_date:
            date_font = date_font or label_font
            date_str = format_header_date(now)
            dw = text_w(draw, date_str, date_font)
            draw.text((right_x - dw, y + date_gap), date_str, font=date_font, fill=fill)
        return total_w

    draw.text((right_x - tw, y), time_str, font=fnt, fill=fill)
    if show_date:
        date_font = date_font or regular_font(config.HEADER_DATE_FONT_SIZE)
        date_str = format_header_date(now)
        dw = text_w(draw, date_str, date_font)
        draw.text((right_x - dw, y + date_gap), date_str, font=date_font, fill=fill)
    return tw

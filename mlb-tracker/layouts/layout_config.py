from PIL import Image, ImageDraw
from datetime import datetime
import config
from layouts.draw_utils import bold_font, regular_font, draw_clock_right, text_w

W = config.MASTER_W
H = config.MASTER_H


def render(state):
    img = Image.new("1", (W, H), 255)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, W, 44], fill=0)
    title = "MLB TRACKER CONFIG"
    title_fnt = bold_font(18)
    draw.text((12, 13), title, font=title_fnt, fill=255)
    draw_clock_right(
        draw,
        W - 12,
        13,
        datetime.now(config.LOCAL_TZ),
        regular_font(10),
        fill=255,
    )

    heading_fnt = bold_font(24)
    body_fnt = regular_font(17)
    small_fnt = regular_font(12)

    heading = "OPEN CONFIG PAGE"
    hw = text_w(draw, heading, heading_fnt)
    draw.text(((W - hw) // 2, 74), heading, font=heading_fnt, fill=0)

    lines = [
        "Use a phone or computer on the same Wi-Fi network.",
        "Open this address in a browser:",
    ]

    y = 126
    for line in lines:
        lw = text_w(draw, line, body_fnt)
        draw.text(((W - lw) // 2, y), line, font=body_fnt, fill=0)
        y += 28

    box_x = 72
    box_y = 190
    box_w = W - box_x * 2
    box_h = 84
    draw.rectangle([box_x, box_y, box_x + box_w, box_y + box_h], outline=0, width=2)

    url = getattr(state, "config_url", None) or "http://mlb-tracker.local:8765"
    url_fnt = bold_font(20)
    if text_w(draw, url, url_fnt) > box_w - 36:
        url_fnt = bold_font(16)
    url_w = text_w(draw, url, url_fnt)
    draw.text((box_x + (box_w - url_w) // 2, box_y + 28), url, font=url_fnt, fill=0)

    help_lines = [
        "The web page has dropdowns for Wi-Fi, team, and timezone.",
        "It also has a password field and manual Wi-Fi entry.",
        "Keyboard/terminal option: python3 scripts/setup_wizard.py --force",
    ]
    hy = 286
    for line in help_lines:
        line_fnt = small_fnt
        if text_w(draw, line, line_fnt) > W - 24:
            line_fnt = regular_font(10)
        lw = text_w(draw, line, line_fnt)
        draw.text(((W - lw) // 2, hy), line, font=line_fnt, fill=0)
        hy += 22

    hint1 = "LEFT + RIGHT held for 3 seconds opens this screen."
    hint2 = "LEFT/RIGHT primarily scroll the schedule screen. CENTER returns to the tracker."
    for hint, hy in ((hint1, 350), (hint2, 376)):
        hw = text_w(draw, hint, small_fnt)
        draw.text(((W - hw) // 2, hy), hint, font=small_fnt, fill=0)

    draw.rectangle([0, H - 44, W, H], fill=0)
    footer = "Press CENTER to go back"
    fw = text_w(draw, footer, bold_font(16))
    draw.text(((W - fw) // 2, H - 31), footer, font=bold_font(16), fill=255)

    return img

#!/usr/bin/env python3
"""
simulate_pregame.py

Full end-to-end simulation:
  1. Pre-game VS screen with live second-by-second countdown (30 seconds)
  2. Transitions to live game mode
  3. Cycles through key moments from yesterday's real game:
     Dodgers 10, Angels 1  (May 17, 2026)
     Roki Sasaki: 7 IP, 1 ER, 4 H, 8 K, 0 BB, 91 pitches

Run from ~/dodgers-tracker with service disabled:
    sudo systemctl disable dodgers-tracker
    sudo /usr/bin/python3 simulate_pregame.py

Press Ctrl+C to stop early.
"""

import sys
import os
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

import display_waveshare
from layouts import layout_pregame, layout_live
from state import AppState

OUTPUT_DIR   = "output"
COUNTDOWN_S  = 30    # seconds of pre-game countdown
PLAY_DELAY   = 3     # seconds between game states

# ---------------------------------------------------------------------------
# Fake "next game" dict for pre-game screen
# ---------------------------------------------------------------------------

NEXT_GAME = {
    "date_utc":      "2026-05-18T02:10:00Z",   # 7:10 PM PT
    "home_away":     "away",
    "opponent_name": "Los Angeles Angels",
    "opponent_abbr": "LAA",
    "venue":         "Angel Stadium",
    "probable_pitcher_dodgers":  "Yoshinobu Yamamoto",
    "probable_pitcher_opponent": "Walbert Ureña",
}

# ---------------------------------------------------------------------------
# Key moments from Dodgers 10, Angels 1 — May 17 2026
# Roki Sasaki: 7 IP, 1 ER, 4 H, 8 K, 0 BB, 91 pitches
# ---------------------------------------------------------------------------

GAME_STATES = [

    # 1. Top 1st — Sasaki's first pitch
    dict(
        away_name="Los Angeles Dodgers", away_abbr="LAD",
        home_name="Los Angeles Angels",  home_abbr="LAA",
        away_score=0, home_score=0,
        inning=1, inning_half="Top", status_detail="In Progress",
        outs=0, balls=0, strikes=0,
        on_1b=False, on_2b=False, on_3b=False,
        batter_name="Roki Sasaki", batter_avg=".000",
        batter_ab_today=0, batter_h_today=0,
        pitcher_name="Roki Sasaki", pitcher_era="2.14",
        pitch_count=0, last_pitch_speed=None, last_pitch_type=None,
        last_play="Sasaki takes the mound — 7-inning gem incoming",
        away_innings=[], home_innings=[],
        away_hits=0, home_hits=0, away_errors=0, home_errors=0,
    ),

    # 2. Bot 1st — Angels go down 1-2-3
    dict(
        away_name="Los Angeles Dodgers", away_abbr="LAD",
        home_name="Los Angeles Angels",  home_abbr="LAA",
        away_score=0, home_score=0,
        inning=1, inning_half="Bot", status_detail="In Progress",
        outs=0, balls=0, strikes=0,
        on_1b=False, on_2b=False, on_3b=False,
        batter_name="Mike Trout", batter_avg=".267",
        batter_ab_today=0, batter_h_today=0,
        pitcher_name="Roki Sasaki", pitcher_era="2.14",
        pitch_count=8, last_pitch_speed=99, last_pitch_type="4-Seam Fastball",
        last_play="Dodgers go down quietly — Sasaki takes the mound",
        away_innings=[0], home_innings=[],
        away_hits=0, home_hits=0, away_errors=0, home_errors=0,
    ),

    # 3. Top 4th — Ohtani 2-run single, LAD leads 2-0
    dict(
        away_name="Los Angeles Dodgers", away_abbr="LAD",
        home_name="Los Angeles Angels",  home_abbr="LAA",
        away_score=2, home_score=0,
        inning=4, inning_half="Top", status_detail="In Progress",
        outs=1, balls=0, strikes=0,
        on_1b=False, on_2b=False, on_3b=False,
        batter_name="Freddie Freeman", batter_avg=".315",
        batter_ab_today=1, batter_h_today=1,
        pitcher_name="Roki Sasaki", pitcher_era="2.14",
        pitch_count=34, last_pitch_speed=97, last_pitch_type="4-Seam Fastball",
        last_play="Ohtani 2-run single! LAD leads 2-0",
        away_innings=[0, 0, 0, 2], home_innings=[0, 0, 0],
        away_hits=3, home_hits=1, away_errors=0, home_errors=0,
    ),

    # 4. Top 4th — Pages 2-run single, LAD leads 4-0
    dict(
        away_name="Los Angeles Dodgers", away_abbr="LAD",
        home_name="Los Angeles Angels",  home_abbr="LAA",
        away_score=4, home_score=0,
        inning=4, inning_half="Top", status_detail="In Progress",
        outs=2, balls=0, strikes=0,
        on_1b=True, on_2b=False, on_3b=False,
        batter_name="Will Smith", batter_avg=".289",
        batter_ab_today=1, batter_h_today=0,
        pitcher_name="Roki Sasaki", pitcher_era="2.14",
        pitch_count=34, last_pitch_speed=93, last_pitch_type="Sinker",
        last_play="Pages 2-run single! LAD extends lead 4-0",
        away_innings=[0, 0, 0, 4], home_innings=[0, 0, 0],
        away_hits=5, home_hits=1, away_errors=0, home_errors=0,
    ),

    # 5. Bot 5th — Angels lone run scores, 4-1
    dict(
        away_name="Los Angeles Dodgers", away_abbr="LAD",
        home_name="Los Angeles Angels",  home_abbr="LAA",
        away_score=4, home_score=1,
        inning=5, inning_half="Bot", status_detail="In Progress",
        outs=2, balls=1, strikes=2,
        on_1b=False, on_2b=False, on_3b=False,
        batter_name="Logan O'Hoppe", batter_avg=".241",
        batter_ab_today=2, batter_h_today=1,
        pitcher_name="Roki Sasaki", pitcher_era="2.14",
        pitch_count=56, last_pitch_speed=95, last_pitch_type="4-Seam Fastball",
        last_play="Angels scratch across a run — now 4-1, Sasaki still dealing",
        away_innings=[0, 0, 0, 4, 0], home_innings=[0, 0, 0, 0, 1],
        away_hits=5, home_hits=3, away_errors=0, home_errors=0,
    ),

    # 6. Top 6th — Tucker RBI double, 5-1
    dict(
        away_name="Los Angeles Dodgers", away_abbr="LAD",
        home_name="Los Angeles Angels",  home_abbr="LAA",
        away_score=5, home_score=1,
        inning=6, inning_half="Top", status_detail="In Progress",
        outs=1, balls=0, strikes=1,
        on_1b=False, on_2b=True, on_3b=False,
        batter_name="Shohei Ohtani", batter_avg=".312",
        batter_ab_today=2, batter_h_today=1,
        pitcher_name="Roki Sasaki", pitcher_era="2.14",
        pitch_count=34, last_pitch_speed=88, last_pitch_type="Slider",
        last_play="Tucker RBI double! LAD leads 5-1",
        away_innings=[0, 0, 0, 4, 0, 1], home_innings=[0, 0, 0, 0, 1],
        away_hits=7, home_hits=3, away_errors=0, home_errors=0,
    ),

    # 7. Top 7th — Sasaki's final inning, strikeout #8
    dict(
        away_name="Los Angeles Dodgers", away_abbr="LAD",
        home_name="Los Angeles Angels",  home_abbr="LAA",
        away_score=5, home_score=1,
        inning=7, inning_half="Top", status_detail="In Progress",
        outs=2, balls=0, strikes=2,
        on_1b=False, on_2b=False, on_3b=False,
        batter_name="Mike Trout", batter_avg=".267",
        batter_ab_today=2, batter_h_today=0,
        pitcher_name="Roki Sasaki", pitcher_era="2.14",
        pitch_count=86, last_pitch_speed=100, last_pitch_type="4-Seam Fastball",
        last_play="Sasaki dealing — 0-2 count on Trout, 86 pitches",
        away_innings=[0, 0, 0, 4, 0, 1, 0], home_innings=[0, 0, 0, 0, 1, 0],
        away_hits=7, home_hits=3, away_errors=0, home_errors=0,
    ),

    # 8. Bot 7th — Sasaki's line: 7 IP, 1 ER, 4 H, 8 K, 91 pitches
    dict(
        away_name="Los Angeles Dodgers", away_abbr="LAD",
        home_name="Los Angeles Angels",  home_abbr="LAA",
        away_score=5, home_score=1,
        inning=7, inning_half="Bot", status_detail="In Progress",
        outs=0, balls=0, strikes=0,
        on_1b=False, on_2b=False, on_3b=False,
        batter_name="Zach Neto", batter_avg=".253",
        batter_ab_today=2, batter_h_today=0,
        pitcher_name="Roki Sasaki", pitcher_era="2.14",
        pitch_count=91, last_pitch_speed=99, last_pitch_type="4-Seam Fastball",
        last_play="Sasaki K's 8! Career-high innings — 7 IP, 1 ER, 91 pitches",
        away_innings=[0, 0, 0, 4, 0, 1, 0], home_innings=[0, 0, 0, 0, 1, 0],
        away_hits=7, home_hits=4, away_errors=0, home_errors=0,
    ),

    # 9. Top 8th — Dodgers pour it on, 8-1
    dict(
        away_name="Los Angeles Dodgers", away_abbr="LAD",
        home_name="Los Angeles Angels",  home_abbr="LAA",
        away_score=8, home_score=1,
        inning=8, inning_half="Top", status_detail="In Progress",
        outs=1, balls=0, strikes=0,
        on_1b=False, on_2b=False, on_3b=False,
        batter_name="Andy Pages", batter_avg=".271",
        batter_ab_today=3, batter_h_today=2,
        pitcher_name="Ben Joyce", pitcher_era="4.82",
        pitch_count=18, last_pitch_speed=103, last_pitch_type="4-Seam Fastball",
        last_play="Tucker RBI single — LAD now leads 8-1",
        away_innings=[0, 0, 0, 4, 0, 1, 0, 2], home_innings=[0, 0, 0, 0, 1, 0, 0],
        away_hits=9, home_hits=4, away_errors=0, home_errors=0,
    ),

    # 10. Top 9th — Dodgers add two more, 10-1
    dict(
        away_name="Los Angeles Dodgers", away_abbr="LAD",
        home_name="Los Angeles Angels",  home_abbr="LAA",
        away_score=10, home_score=1,
        inning=9, inning_half="Top", status_detail="In Progress",
        outs=2, balls=0, strikes=0,
        on_1b=False, on_2b=False, on_3b=False,
        batter_name="Shohei Ohtani", batter_avg=".312",
        batter_ab_today=4, batter_h_today=2,
        pitcher_name="Charlie Barnes", pitcher_era="5.14",
        pitch_count=22, last_pitch_speed=91, last_pitch_type="Changeup",
        last_play="Dodgers tack on 2 more — leads 10-1 heading to the bottom",
        away_innings=[0, 0, 0, 4, 0, 1, 0, 2, 2], home_innings=[0, 0, 0, 0, 1, 0, 0],
        away_hits=12, home_hits=4, away_errors=0, home_errors=0,
    ),

    # 11. Final — Dodgers win 10-1
    dict(
        away_name="Los Angeles Dodgers", away_abbr="LAD",
        home_name="Los Angeles Angels",  home_abbr="LAA",
        away_score=10, home_score=1,
        inning=9, inning_half="Bot", status_detail="Game Over",
        outs=3, balls=0, strikes=0,
        on_1b=False, on_2b=False, on_3b=False,
        batter_name="—", batter_avg="—",
        batter_ab_today=0, batter_h_today=0,
        pitcher_name="Evan Phillips", pitcher_era="1.42",
        pitch_count=11, last_pitch_speed=95, last_pitch_type="4-Seam Fastball",
        last_play="Final: Dodgers sweep Angels 10-1! Sasaki career-high 8 K's",
        away_innings=[0, 0, 0, 4, 0, 1, 0, 2, 2],
        home_innings=[0, 0, 0, 0, 1, 0, 0, 0, 0],
        away_hits=12, home_hits=4, away_errors=0, home_errors=0,
    ),
]


def show_and_save(img, frame_num, label="", mode="full"):
    """Save PNG and push to e-ink display."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"sim_{frame_num:03d}.png")
    img.save(path)
    logger.info("  → %s  [%s]  %s", path, mode, label)

    if mode == "full":
        display_waveshare.show(img)
    elif mode == "fast":
        display_waveshare.show_fast(img)
    elif mode == "partial":
        from layouts.layout_pregame import ZONE_COUNTDOWN_Y1, ZONE_COUNTDOWN_Y2
        display_waveshare.show_partial(img, 0, ZONE_COUNTDOWN_Y1, 800, ZONE_COUNTDOWN_Y2)

    return path


def main():
    state = AppState()

    logger.info("=" * 60)
    logger.info("PRE-GAME → LIVE GAME SIMULATION")
    logger.info("Game: LAD @ LAA  May 17 2026  (final: 10-1)")
    logger.info(f"Countdown: {COUNTDOWN_S}s  |  Game plays: {len(GAME_STATES)}")
    logger.info("Pushing to e-ink display — service must be stopped!")
    logger.info("=" * 60)

    frame = 1

    # -----------------------------------------------------------------------
    # PHASE 1: Countdown — matches Waveshare demo pattern exactly:
    #   1. Full refresh to paint complete screen
    #   2. init_part() ONCE
    #   3. Loop: clear countdown rectangle, draw new number, display_Partial
    #      with FULL SCREEN coords (0,0,width,height) every time
    # -----------------------------------------------------------------------
    logger.info("\n[PHASE 1] Pre-game countdown — %ds", COUNTDOWN_S)

    from layouts.layout_pregame import ZONE_COUNTDOWN_Y1, ZONE_COUNTDOWN_Y2
    from layouts import layout_pregame
    from PIL import ImageDraw

    # Step 1: Render full screen and do a FULL refresh
    logger.info("Full refresh — painting initial pregame screen...")
    persistent_img = layout_pregame.render(state, NEXT_GAME, COUNTDOWN_S)
    show_and_save(persistent_img, frame, "PREGAME INITIAL", mode="full")
    frame += 1

    # Wait for full refresh to fully complete before switching modes
    time.sleep(3)

    # Step 2: Switch to partial mode ONCE
    logger.info("Switching to partial mode for countdown...")
    display_waveshare.show_partial(persistent_img)  # init_part + first partial draw

    # Step 3: Count down — only redraw the countdown zone on the persistent image
    for secs in range(COUNTDOWN_S - 1, -1, -1):
        label = f"PREGAME T-{secs}s" if secs > 0 else "FIRST PITCH!"
        logger.info("  %s", label)

        # Clear ONLY the countdown rectangle on the persistent image
        draw = ImageDraw.Draw(persistent_img)
        draw.rectangle(
            [0, ZONE_COUNTDOWN_Y1, 800, ZONE_COUNTDOWN_Y2],
            fill=255
        )

        # Redraw just the countdown text into that cleared area
        layout_pregame._draw_countdown(draw, secs)

        # Save PNG for reference
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        persistent_img.save(os.path.join(OUTPUT_DIR, f"sim_{frame:03d}.png"))
        frame += 1

        # Partial refresh with FULL screen coords — demo always uses 0,0,w,h
        display_waveshare.show_partial(persistent_img)

        if secs > 0:
            time.sleep(1)

    logger.info("Countdown complete — transitioning to live game mode\n")
    display_waveshare.sleep()
    time.sleep(2)

    # -----------------------------------------------------------------------
    # PHASE 2: Live game plays
    # First frame = full refresh (clears pregame screen)
    # Subsequent frames = fast refresh
    # -----------------------------------------------------------------------
    logger.info("[PHASE 2] Live game — %d key moments", len(GAME_STATES))

    for i, g in enumerate(GAME_STATES):
        logger.info(
            "[%2d/%d]  %s %s  |  LAD %d - LAA %d  |  %s-%s %do  |  %s",
            i + 1, len(GAME_STATES),
            g["inning_half"], _ord(g["inning"]),
            g["away_score"], g["home_score"],
            g["balls"], g["strikes"], g["outs"],
            g["last_play"][:55]
        )

        try:
            img = layout_live.render(state, g)
        except Exception as e:
            logger.error("Render failed: %s", e)
            import traceback; traceback.print_exc()
            continue

        mode = "full" if i == 0 else "fast"
        show_and_save(img, frame, g["last_play"][:40], mode=mode)
        frame += 1

        if i < len(GAME_STATES) - 1:
            time.sleep(PLAY_DELAY)

    display_waveshare.sleep()   # sleep when done
    total = frame - 1
    logger.info("\nDone! %d frames total", total)


def _ord(n):
    try: n = int(n)
    except: return str(n)
    s = {1:"st",2:"nd",3:"rd"}.get(n%10,"th")
    if 11 <= n%100 <= 13: s = "th"
    return f"{n}{s}"


if __name__ == "__main__":
    main()

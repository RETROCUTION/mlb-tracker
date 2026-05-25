#!/usr/bin/env python3
"""
simulate_live.py
Simulates a live Dodgers game cycling through realistic at-bat states.
Saves each frame to output/live_NNN.png so you can review them on your Mac.
Bypasses all hardware — safe to run while service is running or stopped.

Usage:
    cd ~/dodgers-tracker
    source ../dodgers-env/bin/activate
    python3 simulate_live.py

Then on your Mac:
    scp pi@192.168.68.7:~/dodgers-tracker/output/live_*.png ~/Desktop/sim/
"""

import sys
import os
import time
import logging

# ---------------------------------------------------------------------------
# Stub out ALL hardware-touching modules before anything else imports them
# ---------------------------------------------------------------------------
import types

def _make_stub(name):
    m = types.ModuleType(name)
    return m

# Stub gpiozero so waveshare driver doesn't try to claim GPIO
_gz = _make_stub("gpiozero")
class _FakeButton:
    def __init__(self, *a, **kw): pass
    when_pressed = when_released = when_held = None
    def close(self): pass
_gz.Button = _FakeButton
sys.modules["gpiozero"] = _gz

# Stub display_waveshare
_dw = _make_stub("display_waveshare")
_dw.HARDWARE_AVAILABLE = False
_saved_img = [None]

def _show(image):
    _saved_img[0] = image

def _show_fast(image):
    _saved_img[0] = image

def _show_partial(image, x1, y1, x2, y2):
    _saved_img[0] = image

def _clear():
    pass

_dw.show         = _show
_dw.show_fast    = _show_fast
_dw.show_partial = _show_partial
_dw.clear        = _clear
sys.modules["display_waveshare"] = _dw

# ---------------------------------------------------------------------------
# Now safe to import project modules
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

from layouts import layout_live

OUTPUT_DIR = "output"
STEP_DELAY = 4     # seconds between states

# ---------------------------------------------------------------------------
# Game states
# ---------------------------------------------------------------------------

STATES = [

    # 1. Top 1st — first pitch
    dict(
        away_name="San Francisco Giants", away_abbr="SF",
        home_name="Los Angeles Dodgers",  home_abbr="LAD",
        away_score=0, home_score=0,
        inning=1, inning_half="Top", status_detail="In Progress",
        outs=0, balls=0, strikes=0,
        on_1b=False, on_2b=False, on_3b=False,
        batter_name="Wilmer Flores", batter_avg=".281",
        batter_ab_today=0, batter_h_today=0,
        pitcher_name="Yoshinobu Yamamoto", pitcher_era="2.84",
        pitch_count=0, last_pitch_speed=None, last_pitch_type=None,
        last_play="Game underway — first pitch",
        away_innings=[], home_innings=[],
        away_hits=0, home_hits=0, away_errors=0, home_errors=0,
    ),

    # 2. Count 1-0
    dict(
        away_name="San Francisco Giants", away_abbr="SF",
        home_name="Los Angeles Dodgers",  home_abbr="LAD",
        away_score=0, home_score=0,
        inning=1, inning_half="Top", status_detail="In Progress",
        outs=0, balls=1, strikes=0,
        on_1b=False, on_2b=False, on_3b=False,
        batter_name="Wilmer Flores", batter_avg=".281",
        batter_ab_today=0, batter_h_today=0,
        pitcher_name="Yoshinobu Yamamoto", pitcher_era="2.84",
        pitch_count=1, last_pitch_speed=96, last_pitch_type="4-Seam Fastball",
        last_play="Ball 1 — fastball up and away",
        away_innings=[], home_innings=[],
        away_hits=0, home_hits=0, away_errors=0, home_errors=0,
    ),

    # 3. Count 1-1
    dict(
        away_name="San Francisco Giants", away_abbr="SF",
        home_name="Los Angeles Dodgers",  home_abbr="LAD",
        away_score=0, home_score=0,
        inning=1, inning_half="Top", status_detail="In Progress",
        outs=0, balls=1, strikes=1,
        on_1b=False, on_2b=False, on_3b=False,
        batter_name="Wilmer Flores", batter_avg=".281",
        batter_ab_today=0, batter_h_today=0,
        pitcher_name="Yoshinobu Yamamoto", pitcher_era="2.84",
        pitch_count=2, last_pitch_speed=84, last_pitch_type="Sweeper",
        last_play="Strike 1 — swinging, sweeper low and away",
        away_innings=[], home_innings=[],
        away_hits=0, home_hits=0, away_errors=0, home_errors=0,
    ),

    # 4. Strikeout — 1 out, new batter
    dict(
        away_name="San Francisco Giants", away_abbr="SF",
        home_name="Los Angeles Dodgers",  home_abbr="LAD",
        away_score=0, home_score=0,
        inning=1, inning_half="Top", status_detail="In Progress",
        outs=1, balls=0, strikes=0,
        on_1b=False, on_2b=False, on_3b=False,
        batter_name="LaMonte Wade Jr.", batter_avg=".245",
        batter_ab_today=0, batter_h_today=0,
        pitcher_name="Yoshinobu Yamamoto", pitcher_era="2.84",
        pitch_count=5, last_pitch_speed=97, last_pitch_type="4-Seam Fastball",
        last_play="Flores struck out swinging — 1 out",
        away_innings=[], home_innings=[],
        away_hits=0, home_hits=0, away_errors=0, home_errors=0,
    ),

    # 5. SF singles — runner on 1st
    dict(
        away_name="San Francisco Giants", away_abbr="SF",
        home_name="Los Angeles Dodgers",  home_abbr="LAD",
        away_score=0, home_score=0,
        inning=1, inning_half="Top", status_detail="In Progress",
        outs=1, balls=0, strikes=0,
        on_1b=True, on_2b=False, on_3b=False,
        batter_name="Matt Chapman", batter_avg=".262",
        batter_ab_today=0, batter_h_today=0,
        pitcher_name="Yoshinobu Yamamoto", pitcher_era="2.84",
        pitch_count=9, last_pitch_speed=92, last_pitch_type="Sinker",
        last_play="Wade singles on a line drive to left — runner on 1st",
        away_innings=[], home_innings=[],
        away_hits=1, home_hits=0, away_errors=0, home_errors=0,
    ),

    # 6. Runners on 1st & 2nd
    dict(
        away_name="San Francisco Giants", away_abbr="SF",
        home_name="Los Angeles Dodgers",  home_abbr="LAD",
        away_score=0, home_score=0,
        inning=1, inning_half="Top", status_detail="In Progress",
        outs=1, balls=2, strikes=1,
        on_1b=True, on_2b=True, on_3b=False,
        batter_name="Matt Chapman", batter_avg=".262",
        batter_ab_today=0, batter_h_today=0,
        pitcher_name="Yoshinobu Yamamoto", pitcher_era="2.84",
        pitch_count=14, last_pitch_speed=86, last_pitch_type="Changeup",
        last_play="Wild pitch — Wade to 2nd, runners on 1st & 2nd",
        away_innings=[], home_innings=[],
        away_hits=1, home_hits=0, away_errors=0, home_errors=0,
    ),

    # 7. SF scores 2 — runner on 3rd, 2 outs
    dict(
        away_name="San Francisco Giants", away_abbr="SF",
        home_name="Los Angeles Dodgers",  home_abbr="LAD",
        away_score=2, home_score=0,
        inning=1, inning_half="Top", status_detail="In Progress",
        outs=2, balls=0, strikes=0,
        on_1b=False, on_2b=False, on_3b=True,
        batter_name="Jorge Soler", batter_avg=".238",
        batter_ab_today=0, batter_h_today=0,
        pitcher_name="Yoshinobu Yamamoto", pitcher_era="2.84",
        pitch_count=22, last_pitch_speed=88, last_pitch_type="Slider",
        last_play="Chapman doubles to right — 2 runs score! SF leads 2-0",
        away_innings=[], home_innings=[],
        away_hits=2, home_hits=0, away_errors=0, home_errors=0,
    ),

    # 8. Bot 3rd — bases loaded, full count
    dict(
        away_name="San Francisco Giants", away_abbr="SF",
        home_name="Los Angeles Dodgers",  home_abbr="LAD",
        away_score=2, home_score=1,
        inning=3, inning_half="Bot", status_detail="In Progress",
        outs=1, balls=3, strikes=2,
        on_1b=True, on_2b=True, on_3b=True,
        batter_name="Freddie Freeman", batter_avg=".315",
        batter_ab_today=1, batter_h_today=1,
        pitcher_name="Logan Webb", pitcher_era="3.12",
        pitch_count=58, last_pitch_speed=91, last_pitch_type="Sinker",
        last_play="Full count — bases loaded, Freeman at the plate",
        away_innings=[2, 0, 0], home_innings=[0, 0, 1],
        away_hits=3, home_hits=4, away_errors=0, home_errors=0,
    ),

    # 9. Grand slam! LAD leads 5-2
    dict(
        away_name="San Francisco Giants", away_abbr="SF",
        home_name="Los Angeles Dodgers",  home_abbr="LAD",
        away_score=2, home_score=5,
        inning=3, inning_half="Bot", status_detail="In Progress",
        outs=1, balls=0, strikes=0,
        on_1b=False, on_2b=False, on_3b=False,
        batter_name="Teoscar Hernandez", batter_avg=".272",
        batter_ab_today=1, batter_h_today=0,
        pitcher_name="Logan Webb", pitcher_era="3.12",
        pitch_count=62, last_pitch_speed=89, last_pitch_type="Sinker",
        last_play="GRAND SLAM! Freeman crushes it to left — LAD leads 5-2!",
        away_innings=[2, 0, 0], home_innings=[0, 0, 5],
        away_hits=3, home_hits=5, away_errors=0, home_errors=0,
    ),

    # 10. Top 7th — tight game, runner on 2nd
    dict(
        away_name="San Francisco Giants", away_abbr="SF",
        home_name="Los Angeles Dodgers",  home_abbr="LAD",
        away_score=4, home_score=5,
        inning=7, inning_half="Top", status_detail="In Progress",
        outs=0, balls=0, strikes=1,
        on_1b=False, on_2b=True, on_3b=False,
        batter_name="Wilmer Flores", batter_avg=".281",
        batter_ab_today=2, batter_h_today=1,
        pitcher_name="Blake Treinen", pitcher_era="1.98",
        pitch_count=8, last_pitch_speed=98, last_pitch_type="4-Seam Fastball",
        last_play="Runner on 2nd — Treinen dealing in the 7th",
        away_innings=[2, 0, 0, 1, 0, 1, None, None, None],
        home_innings=[0, 0, 5, 0, 0, 0, None, None, None],
        away_hits=7, home_hits=8, away_errors=1, home_errors=0,
    ),

    # 11. Final — LAD wins 7-4
    dict(
        away_name="San Francisco Giants", away_abbr="SF",
        home_name="Los Angeles Dodgers",  home_abbr="LAD",
        away_score=4, home_score=7,
        inning=9, inning_half="Bot", status_detail="Game Over",
        outs=3, balls=0, strikes=0,
        on_1b=False, on_2b=False, on_3b=False,
        batter_name="—", batter_avg="—",
        batter_ab_today=0, batter_h_today=0,
        pitcher_name="Evan Phillips", pitcher_era="1.42",
        pitch_count=14, last_pitch_speed=95, last_pitch_type="4-Seam Fastball",
        last_play="Final: Dodgers win 7-4!  W: Phillips  L: Webb",
        away_innings=[2, 0, 0, 1, 0, 1, 0, 0, 0],
        home_innings=[0, 0, 5, 0, 0, 0, 2, 0, None],
        away_hits=9, home_hits=11, away_errors=1, home_errors=0,
    ),
]


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    logger.info("=" * 60)
    logger.info("Live game simulation — %d states, %ds each", len(STATES), STEP_DELAY)
    logger.info("Frames saved to: %s/live_NNN.png", OUTPUT_DIR)
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)

    for i, g in enumerate(STATES):
        logger.info(
            "[%2d/%d]  %s %s  |  SF %d - LAD %d  |  %s-%s  %d out(s)  |  %s",
            i + 1, len(STATES),
            g["inning_half"], _ordinal(g["inning"]),
            g["away_score"], g["home_score"],
            g["balls"], g["strikes"], g["outs"],
            g["last_play"][:60]
        )

        try:
            img = layout_live.render(None, g)
        except Exception as e:
            logger.error("Render failed on state %d: %s", i + 1, e)
            import traceback
            traceback.print_exc()
            continue

        # Save numbered frame
        frame_path = os.path.join(OUTPUT_DIR, f"live_{i+1:03d}.png")
        img.save(frame_path)
        logger.info("  → %s", frame_path)

        # Also save as current.png for easy viewing
        img.save(os.path.join(OUTPUT_DIR, "current.png"))

        if i < len(STATES) - 1:
            time.sleep(STEP_DELAY)

    logger.info("\nSimulation complete! Grab all frames from your Mac:")
    logger.info("  mkdir -p ~/Desktop/sim")
    logger.info("  scp pi@192.168.68.7:~/dodgers-tracker/output/live_*.png ~/Desktop/sim/")


def _ordinal(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n)
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    return f"{n}{suffix}"


if __name__ == "__main__":
    main()

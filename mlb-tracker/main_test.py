"""
main_test.py — Bare minimum test version
No clock, no partial refresh, no live mode, no threads
Just button press -> render -> show
"""

import time
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib")
sys.path.insert(0, "/home/pi/dodgers-env/lib/python3.13/site-packages")

import config
import cache
import sync_manager
import render
import input_controls
from state import AppState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

state = AppState()

HARDWARE_AVAILABLE = False
epd_module = None

try:
    from waveshare_epd import epd7in5_V2 as epd_module
    HARDWARE_AVAILABLE = True
    logger.info("Waveshare driver loaded")
except Exception as e:
    logger.warning("No hardware: %s", e)


def _show(image):
    """Bare minimum show — exactly like the original that worked."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    image.save(os.path.join(config.OUTPUT_DIR, "current.png"))
    if not HARDWARE_AVAILABLE:
        return
    epd = epd_module.EPD()
    epd.init()
    epd.display(epd.getbuffer(image))
    epd.sleep()
    logger.info("Display updated")


def _do_render():
    games   = cache.read_schedule()
    games   = games.get("games", []) if games else []
    summary = cache.read_summary()
    state.schedule_game_count = len(games)
    img = render.render(state, summary, games)
    _show(img)
    logger.info("Page %d shown", state.page)


def _on_center():
    logger.info("CENTER — toggle page")
    state.toggle_page()
    _do_render()


def main():
    logger.info("TEST MODE starting")
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.CACHE_DIR, exist_ok=True)

    # Position schedule
    games = cache.read_schedule()
    games = games.get("games", []) if games else []
    idx, _ = sync_manager.find_next_game(games)
    if idx is not None:
        state.jump_to_game(idx)
    state.schedule_game_count = len(games)

    input_controls.setup(on_center_short=_on_center)

    logger.info("Initial render")
    _do_render()

    logger.info("Running — press CENTER to cycle pages")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        input_controls.cleanup()
        logger.info("Done")


if __name__ == "__main__":
    main()

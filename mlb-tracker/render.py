import os
import logging
from PIL import Image
import config
from layouts import (
    layout_briefing,
    layout_schedule,
    layout_standings,
    layout_live,
    layout_pregame,
    layout_config,
)

logger = logging.getLogger(__name__)


def render(state, summary, games):
    if getattr(state, "config_mode", False):
        img = layout_config.render(state)
    elif state.live_mode:
        img = layout_live.render(state, state.live_game_data)
    elif getattr(state, "pregame_mode", False):
        img = layout_pregame.render(
            state,
            state.pregame_game,
            state.pregame_seconds_remaining or 0,
        )
    elif state.page == config.PAGE_BRIEFING:
        img = layout_briefing.render(state, summary, games)
    elif state.page == config.PAGE_SCHEDULE:
        img = layout_schedule.render(state, games)
    elif state.page == config.PAGE_STANDINGS:
        img = layout_standings.render(state, summary)
    else:
        img = layout_briefing.render(state, summary, games)

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(config.OUTPUT_DIR, "current.png")
    img.save(out_path)
    logger.info("Rendered page %d to %s", state.page, out_path)

    return img

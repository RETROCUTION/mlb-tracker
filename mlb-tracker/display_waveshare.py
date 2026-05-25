import logging
import os
import time
from PIL import ImageOps
import config

logger = logging.getLogger(__name__)

HARDWARE_AVAILABLE = False

try:
    from waveshare_epd import epd7in5_V2 as epd_module
    HARDWARE_AVAILABLE = True
    logger.info("Waveshare hardware driver loaded")
except ImportError:
    logger.warning("Waveshare driver not found - running in stub mode")


_epd = None
_partial_ready = False
_partial_count = 0
_last_partial_timing_log = 0.0


def _get_epd():
    global _epd

    if not HARDWARE_AVAILABLE:
        return None

    if _epd is None:
        _epd = epd_module.EPD()

    return _epd


def prepare_for_display(image, invert=False):
    """
    Convert the rendered layout image into the exact image sent to the panel.
    Inversion lives here so render/layout output stays in normal polarity.
    """
    if invert:
        return ImageOps.invert(image.convert("L")).convert("RGB")

    if image.mode == "1":
        return image

    return image.convert("1")


def _save_debug_images(image, panel_img):
    if not getattr(config, "SAVE_DISPLAY_DEBUG_IMAGES", False):
        return

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    image.save(os.path.join(config.OUTPUT_DIR, "current_normal.png"))
    panel_img.save(os.path.join(config.OUTPUT_DIR, "current_panel.png"))


def init_display(clear=True):
    """
    Initialize the display object once. The first rendered frame should still be
    sent with show_full(), then all regular frames can use fullscreen partial.
    """
    epd = _get_epd()
    if epd is None:
        return

    try:
        epd.init()
        if clear:
            epd.Clear()
        logger.info("Display initialized%s", " and cleared" if clear else "")
    except Exception as e:
        logger.error("Display init error: %s", e)


def show_full(image, invert=False, clear_first=False):
    """
    Full refresh, then switch to partial mode once for subsequent frames.
    """
    global _partial_ready

    panel_img = prepare_for_display(image, invert=invert)
    _save_debug_images(image, panel_img)

    epd = _get_epd()
    if epd is None:
        return

    try:
        epd.init()
        if clear_first:
            epd.Clear()
        epd.display(epd.getbuffer(panel_img))
        time.sleep(1)
        epd.init_part()
        _partial_ready = True
        logger.info(
            "Display updated full%s; partial mode ready",
            " after clear" if clear_first else "",
        )
    except Exception as e:
        _partial_ready = False
        logger.error("Display full refresh error: %s", e)


def show_partial_fullscreen(image, invert=False):
    """
    Fast update path proven by clock.py: send the whole 800x480 buffer through
    display_Partial(), never a small rectangle.
    """
    global _partial_ready, _partial_count, _last_partial_timing_log

    start = time.monotonic()
    panel_img = prepare_for_display(image, invert=invert)
    prep_done = time.monotonic()
    _save_debug_images(image, panel_img)

    epd = _get_epd()
    if epd is None:
        return

    try:
        if not _partial_ready:
            epd.init_part()
            _partial_ready = True

        buffer_start = time.monotonic()
        buffer = epd.getbuffer(panel_img)
        buffer_done = time.monotonic()
        epd.display_Partial(
            buffer,
            0,
            0,
            epd.width,
            epd.height,
        )
        done = time.monotonic()
        _partial_count += 1

        timing_logs_enabled = getattr(config, "LOG_DISPLAY_TIMING", False)
        slow_refresh = done - start >= 0.95
        should_log_timing = timing_logs_enabled and (
            done - _last_partial_timing_log >= 30
            or (slow_refresh and done - _last_partial_timing_log >= 10)
        )

        if should_log_timing:
            _last_partial_timing_log = done
            logger.info(
                "Partial refresh timing — total=%.2fs prep=%.2fs buffer=%.2fs epd=%.2fs invert=%s count=%d",
                done - start,
                prep_done - start,
                buffer_done - buffer_start,
                done - buffer_done,
                invert,
                _partial_count,
            )
        else:
            logger.debug("Display updated partial fullscreen")
    except Exception as e:
        _partial_ready = False
        logger.error("Display partial refresh error: %s", e)


def show(image, invert=False):
    show_full(image, invert=invert)


def show_fast(image, invert=False):
    show_partial_fullscreen(image, invert=invert)


def show_partial(image, x1=0, y1=0, x2=None, y2=None, invert=False):
    show_partial_fullscreen(image, invert=invert)


def clear():
    global _partial_ready

    epd = _get_epd()
    if epd is None:
        return

    try:
        epd.init()
        epd.Clear()
        _partial_ready = False
        logger.info("Display cleared")
    except Exception as e:
        logger.error("Display clear error: %s", e)


def sleep():
    global _partial_ready

    epd = _get_epd()
    if epd is None:
        return

    try:
        epd.sleep()
        _partial_ready = False
        logger.info("Display sleeping")
    except Exception as e:
        logger.error("Display sleep error: %s", e)

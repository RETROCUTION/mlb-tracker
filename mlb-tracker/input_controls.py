import time
import logging
import threading
import config

logger = logging.getLogger(__name__)

_callbacks = {}
_press_times = {}

HARDWARE_AVAILABLE = False

try:
    from gpiozero import Button
    HARDWARE_AVAILABLE = True
    logger.info("gpiozero available")
except ImportError:
    logger.warning("gpiozero not available — buttons disabled")

_buttons = {}
_combo_timer = None
_combo_fired = False

DEBOUNCE_SECONDS = 0.5
_last_event_time = {}


def setup(
    on_center_short=None,
    on_center_long=None,
    on_left_short=None,
    on_left_long=None,
    on_right_short=None,
    on_right_long=None,
    on_live=None,
    on_config_combo=None,
):
    _callbacks["center_short"] = on_center_short
    _callbacks["center_long"]  = on_center_long
    _callbacks["left_short"]   = on_left_short
    _callbacks["left_long"]    = on_left_long
    _callbacks["right_short"]  = on_right_short
    _callbacks["right_long"]   = on_right_long
    _callbacks["live"]         = on_live
    _callbacks["config_combo"] = on_config_combo

    if not HARDWARE_AVAILABLE:
        logger.info("Buttons disabled — no gpiozero")
        return

    try:
        _buttons["left"] = Button(
            config.GPIO_BTN_LEFT,
            pull_up=True,
            bounce_time=0.05,
            hold_time=config.LONG_PRESS_THRESHOLD
        )

        _buttons["center"] = Button(
            config.GPIO_BTN_CENTER,
            pull_up=True,
            bounce_time=0.05,
            hold_time=config.LONG_PRESS_THRESHOLD
        )

        _buttons["right"] = Button(
            config.GPIO_BTN_RIGHT,
            pull_up=True,
            bounce_time=0.05,
            hold_time=config.LONG_PRESS_THRESHOLD
        )

        _buttons["left"].when_pressed = lambda: _on_press("left")
        _buttons["center"].when_pressed = lambda: _on_press("center")
        _buttons["right"].when_pressed = lambda: _on_press("right")

        _buttons["left"].when_released = lambda: _on_release("left")
        _buttons["center"].when_released = lambda: _on_release("center")
        _buttons["right"].when_released = lambda: _on_release("right")

        _buttons["left"].when_held = lambda: _on_hold("left")
        _buttons["center"].when_held = lambda: _on_hold("center")
        _buttons["right"].when_held = lambda: _on_hold("right")

        if getattr(config, "GPIO_BTN_LIVE", None):
            _buttons["live"] = Button(
                config.GPIO_BTN_LIVE,
                pull_up=True,
                bounce_time=0.05,
                hold_time=config.LONG_PRESS_THRESHOLD
            )
            _buttons["live"].when_pressed = lambda: _on_press("live")
            _buttons["live"].when_released = lambda: _on_release("live")

            logger.info(
                "Buttons initialized on GPIO %d %d %d %d",
                config.GPIO_BTN_LEFT,
                config.GPIO_BTN_CENTER,
                config.GPIO_BTN_RIGHT,
                config.GPIO_BTN_LIVE
            )
        else:
            logger.info(
                "Buttons initialized on GPIO %d %d %d (no live button)",
                config.GPIO_BTN_LEFT,
                config.GPIO_BTN_CENTER,
                config.GPIO_BTN_RIGHT
            )

    except Exception as e:
        logger.error("Button setup failed: %s", e)


def _debounced(key):
    now = time.time()
    last = _last_event_time.get(key, 0)

    if now - last < DEBOUNCE_SECONDS:
        logger.debug("Debounced event: %s", key)
        return False

    _last_event_time[key] = now
    return True


def _fire(key):
    if not _debounced(key):
        return

    cb = _callbacks.get(key)

    if cb:
        logger.info("Button event: %s", key)

        try:
            cb()
        except Exception as e:
            logger.error("Button callback error for %s: %s", key, e)


def _on_press(name):
    global _combo_fired

    _press_times[name] = time.time()
    if name in ("left", "right"):
        _combo_fired = False
        _maybe_start_config_combo_timer()


def _on_release(name):
    global _combo_fired

    t = _press_times.pop(name, None)

    if name in ("left", "right"):
        _cancel_config_combo_timer()

    if _combo_fired:
        if not any(k in _press_times for k in ("left", "right")):
            _combo_fired = False
        return

    if t is not None and (time.time() - t) < config.LONG_PRESS_THRESHOLD:
        if name == "live":
            _fire("live")
        else:
            _fire(f"{name}_short")


def _on_hold(name):
    if name in ("left", "right"):
        other = "right" if name == "left" else "left"
        if other in _press_times:
            logger.debug("Suppressing %s long while config combo is held", name)
            return

    _press_times.pop(name, None)
    _fire(f"{name}_long")


def _maybe_start_config_combo_timer():
    global _combo_timer

    if "left" not in _press_times or "right" not in _press_times:
        return

    if _combo_timer and _combo_timer.is_alive():
        return

    hold_seconds = float(getattr(config, "CONFIG_COMBO_HOLD_SECONDS", 3.0))
    _combo_timer = threading.Timer(hold_seconds, _fire_config_combo_if_still_held)
    _combo_timer.daemon = True
    _combo_timer.start()


def _cancel_config_combo_timer():
    global _combo_timer

    if "left" in _press_times and "right" in _press_times:
        return

    if _combo_timer:
        _combo_timer.cancel()
        _combo_timer = None


def _fire_config_combo_if_still_held():
    global _combo_timer, _combo_fired

    _combo_timer = None
    if "left" not in _press_times or "right" not in _press_times:
        return

    _combo_fired = True
    _press_times.pop("left", None)
    _press_times.pop("right", None)
    _fire("config_combo")


def cleanup():
    _cancel_config_combo_timer()

    for btn in _buttons.values():
        try:
            btn.close()
        except Exception:
            pass

    logger.info("Buttons cleaned up")

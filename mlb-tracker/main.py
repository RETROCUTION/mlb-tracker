"""
main.py — MLB Tracker

Runs the normal tracker screens with a live seconds clock on every render.
The Waveshare panel is driven like the working clock.py reference:

- full init / clear / full display once
- init_part() once after the first full frame
- regular updates use display_Partial() with the full 800x480 buffer
"""

import time
import threading
import logging
import os
import sys
from datetime import datetime, timezone
from collections import deque

# Ensure system python finds waveshare lib and virtualenv packages
_EXTRA_PATHS = [
    "/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib",
    "/home/pi/dodgers-env/lib/python3.13/site-packages",
    "/home/pi/mlb-tracker/venv/lib/python3.13/site-packages",
]

for _p in _EXTRA_PATHS:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config
import cache
import sync_manager
import mlb_api
import render
import input_controls
import display_waveshare
import config_server
from state import AppState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "mlb_tracker.log")
        ),
    ]
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

DISPLAY_TICK_SECONDS = 1
SYNC_INTERVAL = 60
LIVE_POLL_INTERVAL = getattr(config, "LIVE_POLL_INTERVAL_SECONDS", 1)
FULL_REFRESH_INTERVAL = 15 * 60
PREGAME_WINDOW_SECONDS = 10 * 60
BOOT_DELAY = 0

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

state = AppState()

_state_lock = threading.RLock()
_render_lock = threading.Lock()
_display_request_lock = threading.Lock()
_sync_thread_lock = threading.Lock()
_live_poll_thread_lock = threading.Lock()
_force_full_next = True
_force_clear_next = False
_last_full_refresh = 0.0
_live_buffer = deque(maxlen=600)
_display_generation = 0
_was_online = False
_input_transition_active = False
_clock_paused = False
_last_frame_img = None
_last_frame_signature = None


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_games():
    sched = cache.read_schedule()
    return sched.get("games", []) if sched else []


def _load_summary():
    return cache.read_summary()


def _find_live_game(games):
    for g in games:
        if g.get("status") == "Live":
            return g
    return None


def _find_live_game_pk(games):
    live_game = _find_live_game(games)
    return live_game.get("game_pk") if live_game else None


def _find_next_upcoming_game(games):
    for g in games:
        if g.get("status") not in ("Preview", "Pre-Game", "Scheduled"):
            continue

        try:
            start_utc = datetime.fromisoformat(
                g["date_utc"].replace("Z", "+00:00")
            )
        except Exception:
            continue

        if start_utc >= datetime.now(timezone.utc):
            return g

    return None


def _request_display(full=False, clear=False):
    global _force_full_next, _force_clear_next, _display_generation
    with _display_request_lock:
        if full:
            _force_full_next = True
        if clear:
            _force_clear_next = True
        _display_generation += 1


def _begin_button_action(name):
    global _input_transition_active, _clock_paused, _display_generation

    with _display_request_lock:
        if _input_transition_active:
            logger.info("Ignoring %s button while display transition is active", name)
            return False

        _input_transition_active = True
        _clock_paused = True
        _display_generation += 1

    return True


def _finish_button_action():
    global _input_transition_active, _clock_paused, _display_generation

    with _display_request_lock:
        if not _input_transition_active:
            return

        _input_transition_active = False
        _clock_paused = False
        _display_generation += 1


def _is_clock_paused():
    with _display_request_lock:
        return _clock_paused


def _has_forced_display_pending():
    with _display_request_lock:
        return _force_full_next or _force_clear_next


def _get_display_generation():
    with _display_request_lock:
        return _display_generation


def _take_display_flags(force_full, now):
    global _force_full_next, _force_clear_next

    with _display_request_lock:
        do_full = (
            force_full
            or _force_full_next
            or (now - _last_full_refresh >= FULL_REFRESH_INTERVAL)
        )
        clear_first = _force_clear_next

        if do_full:
            _force_full_next = False
            _force_clear_next = False

    return do_full, clear_first


def _set_online_state(value):
    global _was_online
    with _state_lock:
        _was_online = bool(value)


def _get_online_state():
    with _state_lock:
        return _was_online


# ---------------------------------------------------------------------------
# Sync / live data
# ---------------------------------------------------------------------------

def _do_sync():
    logger.info("Syncing data...")

    ok = sync_manager.sync()

    with _state_lock:
        if ok:
            state.stale = False
            state.last_sync_time = datetime.now(timezone.utc)
            logger.info("Sync successful")
        else:
            state.stale = True
            logger.warning("Sync failed — using cached data")

    return ok


def _fetch_live_game_data(game_pk):
    try:
        raw = mlb_api.fetch_live_game(game_pk)
        return mlb_api.parse_live_game(raw)
    except Exception as e:
        logger.warning("Live game fetch failed for %s: %s", game_pk, e)
        return None


def _live_delay_seconds():
    try:
        return max(0, int(getattr(config, "BROADCAST_DELAY", 0)))
    except (TypeError, ValueError):
        return 0


def _append_live_sample(game_pk, live_data):
    if live_data is None:
        return

    now = time.time()
    sample = dict(live_data)
    sample["game_pk"] = game_pk
    _live_buffer.append((now, sample))

    with _state_lock:
        state.live_latest_game_data = sample

    _update_displayed_live_data_from_buffer(now)


def _remember_final_live_game(game_pk, live_data):
    if live_data is None:
        return

    sample = dict(live_data)
    sample["game_pk"] = game_pk
    if sample.get("status") != "Final":
        sample["status"] = "Final"

    with _state_lock:
        state.live_final_game_data = sample


def _update_displayed_live_data_from_buffer(now=None):
    with _state_lock:
        if not state.live_game_pk:
            return

    if now is None:
        now = time.time()

    delay = _live_delay_seconds()
    cutoff = now - delay
    selected = None

    if delay > 0:
        for fetched_at, sample in reversed(_live_buffer):
            if fetched_at <= cutoff:
                selected = sample
                break

    if selected is None and _live_buffer:
        selected = _live_buffer[0] if delay > 0 else _live_buffer[-1]
        selected = selected[1]

    if selected is None:
        return

    with _state_lock:
        state.live_game_data = selected


def _enter_live_mode(game_pk, auto=False):
    if not game_pk:
        return False

    live_data = _fetch_live_game_data(game_pk)
    _append_live_sample(game_pk, live_data)

    if live_data and live_data.get("status") != "Live":
        logger.info("Game %s is no longer live: %s", game_pk, live_data.get("status"))
        _remember_final_live_game(game_pk, live_data)
        _request_display(full=True, clear=True)
        return False

    with _state_lock:
        state.live_mode = True
        state.live_game_pk = game_pk
        state.live_final_game_data = None
        state.pregame_mode = False
        state.pregame_manual = False
        state.pregame_game = None
        state.pregame_seconds_remaining = None

    logger.info(
        "%s live game mode for gamePk %s",
        "Auto-entered" if auto else "Entered",
        game_pk,
    )
    _request_display(full=True, clear=True)
    return True


def _exit_live_mode(suppress_current=False):
    global _live_buffer

    with _state_lock:
        old_pk = state.live_game_pk
        if suppress_current and old_pk:
            state.live_suppressed_game_pk = old_pk

        state.page = config.PAGE_BRIEFING
        state.live_mode = False
        if not suppress_current:
            state.live_game_pk = None
            state.live_game_data = None
            state.live_latest_game_data = None

    if not suppress_current:
        _live_buffer.clear()

    logger.info("Exited live game mode")
    _request_display(full=True, clear=True)


def _exit_pregame_mode():
    with _state_lock:
        state.page = config.PAGE_BRIEFING
        state.pregame_mode = False
        state.pregame_manual = False
        state.pregame_game = None
        state.pregame_seconds_remaining = None

    logger.info("Exited pregame screen")
    _request_display(full=True, clear=True)


def _exit_config_mode():
    with _state_lock:
        state.config_mode = False
        state.config_url = None
        state.page = config.PAGE_BRIEFING

    config_server.stop()
    logger.info("Exited config screen")
    _request_display(full=True, clear=True)


def _restart_after_config_save():
    logger.info("Config saved from web portal; restarting tracker")
    try:
        input_controls.cleanup()
        display_waveshare.sleep()
    finally:
        os._exit(0)


def _poll_live_game():
    with _state_lock:
        game_pk = state.live_game_pk if state.live_mode else None

    if not game_pk:
        return

    live_data = _fetch_live_game_data(game_pk)
    if live_data is None:
        return

    _append_live_sample(game_pk, live_data)

    status = live_data.get("status")
    if status and status != "Live":
        logger.info("Live game ended or left live state: %s", status)
        _remember_final_live_game(game_pk, live_data)
        _exit_live_mode(suppress_current=False)
        if _do_sync():
            _position_schedule()
        return


def _start_live_poll_async():
    if not _live_poll_thread_lock.acquire(blocking=False):
        logger.debug("Live poll already running")
        return False

    def worker():
        try:
            _poll_live_game()
        finally:
            _live_poll_thread_lock.release()

    thread = threading.Thread(target=worker, name="live-poll", daemon=True)
    thread.start()
    return True


def _sync_interval_cycle():
    previous_online = _get_online_state()
    online = sync_manager.check_connectivity()

    if online and not previous_online:
        logger.info("Connectivity restored — syncing")
        _do_sync()
        _position_schedule()
        _handle_auto_live(_load_games())
        _request_display(full=True)

    elif not online and previous_online:
        logger.warning("Lost connectivity — showing offline state")
        with _state_lock:
            state.stale = True
        _request_display(full=True)

    elif online:
        logger.info("Sync interval reached")

        old_summary = _load_summary()
        old_games = _load_games()

        _do_sync()
        _position_schedule()
        _handle_auto_live(_load_games())

        new_summary = _load_summary()
        new_games = _load_games()

        if _data_changed(old_summary, new_summary, old_games, new_games):
            logger.info("Data changed")
            _request_display(full=True)
        else:
            logger.info("Data unchanged")

    _set_online_state(online)


def _start_sync_async():
    if not _sync_thread_lock.acquire(blocking=False):
        logger.debug("Sync already running")
        return False

    def worker():
        try:
            _sync_interval_cycle()
        finally:
            _sync_thread_lock.release()

    thread = threading.Thread(target=worker, name="sync-cycle", daemon=True)
    thread.start()
    return True


def _handle_auto_live(games):
    live_pk = _find_live_game_pk(games)

    with _state_lock:
        suppressed_pk = state.live_suppressed_game_pk
        already_live = state.live_mode
        current_pk = state.live_game_pk

    if live_pk is None:
        with _state_lock:
            state.live_suppressed_game_pk = None
        if already_live and current_pk is not None:
            _exit_live_mode(suppress_current=False)
        return

    if already_live:
        if current_pk != live_pk:
            _enter_live_mode(live_pk, auto=True)
        return

    if live_pk == suppressed_pk:
        logger.debug("Live game %s suppressed by manual center exit", live_pk)
        return

    _enter_live_mode(live_pk, auto=True)


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def _update_pregame_state(games):
    with _state_lock:
        if state.live_mode:
            state.pregame_mode = False
            state.pregame_manual = False
            return

        manual_pregame = state.pregame_manual
        manual_game = state.pregame_game

    now_utc = datetime.now(timezone.utc)

    if manual_pregame and manual_game:
        try:
            start_utc = datetime.fromisoformat(
                manual_game["date_utc"].replace("Z", "+00:00")
            )
            seconds_remaining = max(0, int((start_utc - now_utc).total_seconds()))
        except Exception:
            seconds_remaining = 0

        with _state_lock:
            state.pregame_mode = True
            state.pregame_game = manual_game
            state.pregame_seconds_remaining = seconds_remaining
        return

    pregame = None
    seconds_remaining = None

    for g in games:
        if g.get("status") not in ("Preview", "Pre-Game", "Scheduled"):
            continue

        try:
            start_utc = datetime.fromisoformat(
                g["date_utc"].replace("Z", "+00:00")
            )
        except Exception:
            continue

        seconds = int((start_utc - now_utc).total_seconds())
        if 0 <= seconds <= PREGAME_WINDOW_SECONDS:
            pregame = g
            seconds_remaining = seconds
            break

    with _state_lock:
        state.pregame_mode = pregame is not None
        state.pregame_manual = False
        state.pregame_game = pregame
        state.pregame_seconds_remaining = seconds_remaining


def _is_preferred_team(name, abbr):
    return abbr == config.TEAM_ABBR or config.TEAM_NAME.lower() in name.lower()


def _merge_live_data_into_games(games):
    with _state_lock:
        live_data = state.live_game_data if state.live_game_pk else None
        final_data = state.live_final_game_data

    merge_data = live_data or final_data
    if not merge_data:
        return games

    game_pk = merge_data.get("game_pk")
    merged = []

    for g in games:
        if game_pk and g.get("game_pk") != game_pk:
            merged.append(g)
            continue

        away_is_team = _is_preferred_team(
            merge_data.get("away_name", ""),
            merge_data.get("away_abbr", ""),
        )
        home_is_team = _is_preferred_team(
            merge_data.get("home_name", ""),
            merge_data.get("home_abbr", ""),
        )

        if not away_is_team and not home_is_team:
            merged.append(g)
            continue

        updated = dict(g)
        if away_is_team:
            team_score = merge_data.get("away_score", 0)
            opp_score = merge_data.get("home_score", 0)
        else:
            team_score = merge_data.get("home_score", 0)
            opp_score = merge_data.get("away_score", 0)

        updated["dodgers_score"] = team_score
        updated["opponent_score"] = opp_score

        status = merge_data.get("status") or "Live"
        if status == "Live":
            updated["status"] = "Live"
            updated["status_detail"] = merge_data.get("status_detail", "Live")
            updated["inning"] = merge_data.get("inning", "")
            updated["inning_half"] = merge_data.get("inning_half", "")
            updated["balls"] = merge_data.get("balls")
            updated["strikes"] = merge_data.get("strikes")
            updated["outs"] = merge_data.get("outs")
            updated["pitch_number"] = merge_data.get("pitch_number")
        else:
            updated["status"] = "Final"
            updated["status_detail"] = merge_data.get("status_detail", "Final")
            updated["inning"] = ""
            updated["inning_half"] = ""
            updated["balls"] = None
            updated["strikes"] = None
            updated["outs"] = None
            updated["pitch_number"] = None
            updated["result"] = "W" if int(team_score or 0) > int(opp_score or 0) else "L"
        merged.append(updated)

    return merged


def _render_to_img():
    with _state_lock:
        has_live_tracking = state.live_game_pk is not None

    if has_live_tracking:
        _update_displayed_live_data_from_buffer()

    games = _load_games()
    summary = _load_summary()
    games = _merge_live_data_into_games(games)

    with _state_lock:
        state.schedule_game_count = len(games)
        if summary:
            state.display_season = summary.get("season", config.CURRENT_SEASON)

    _update_pregame_state(games)

    return render.render(state, summary, games)


def _should_invert_display():
    with _state_lock:
        if state.live_mode or state.pregame_mode:
            return False

        return state.page in (
            config.PAGE_SCHEDULE,
            config.PAGE_STANDINGS,
        )


def _screen_name():
    with _state_lock:
        if state.live_mode:
            return "live"
        if state.pregame_mode:
            return "pregame"
        if state.page == config.PAGE_SCHEDULE:
            return "schedule"
        if state.page == config.PAGE_STANDINGS:
            return "standings"
        return "briefing"


def _screen_signature():
    with _state_lock:
        return (
            state.config_mode,
            state.live_mode,
            state.live_game_pk,
            state.pregame_mode,
            state.pregame_game.get("game_pk") if state.pregame_game else None,
            state.page,
            state.schedule_offset,
        )


def _can_tick_header(signature):
    with _state_lock:
        return (
            not state.config_mode
            and not state.live_mode
            and not state.pregame_mode
            and state.page in (
                config.PAGE_BRIEFING,
                config.PAGE_SCHEDULE,
                config.PAGE_STANDINGS,
            )
            and _last_frame_img is not None
            and _last_frame_signature == signature
        )


def _try_header_tick(force_full=False):
    if force_full or _has_forced_display_pending():
        return False

    signature = _screen_signature()
    if not _can_tick_header(signature):
        return False

    if not render.update_dynamic_header(_last_frame_img, state):
        return False

    invert = _should_invert_display()
    display_waveshare.show_partial_fullscreen(_last_frame_img, invert=invert)
    logger.debug(
        "Display updated header tick — screen=%s invert=%s",
        _screen_name(),
        invert,
    )
    _finish_button_action()
    return True


def _do_render(force_full=False):
    global _last_full_refresh, _last_frame_img, _last_frame_signature

    if _is_clock_paused() and not force_full and not _has_forced_display_pending():
        return

    with _render_lock:
        if _try_header_tick(force_full=force_full):
            return

        img = None
        stable_generation = None
        stable_signature = None
        for attempt in range(3):
            start_generation = _get_display_generation()
            start_signature = _screen_signature()
            img = _render_to_img()
            end_generation = _get_display_generation()
            end_signature = _screen_signature()

            if (
                start_generation == end_generation
                and start_signature == end_signature
            ):
                stable_generation = end_generation
                stable_signature = end_signature
                break

            logger.info(
                "Screen changed during render; retrying frame (%d)",
                attempt + 1,
            )
            stable_generation = end_generation
            stable_signature = end_signature

        if img is None:
            return

        if (
            _get_display_generation() != stable_generation
            or _screen_signature() != stable_signature
        ):
            logger.info("Screen changed before display; refreshing frame")
            img = _render_to_img()
            stable_signature = _screen_signature()

        invert = _should_invert_display()
        now = time.time()
        do_full, clear_first = _take_display_flags(force_full, now)
        screen_name = _screen_name()

        if do_full and screen_name == "schedule":
            clear_first = True

        if do_full:
            display_waveshare.show_full(
                img,
                invert=invert,
                clear_first=clear_first,
            )
            _last_full_refresh = time.time()
            logger.info(
                "Display updated full — screen=%s invert=%s clear=%s",
                screen_name,
                invert,
                clear_first,
            )
        else:
            display_waveshare.show_partial_fullscreen(img, invert=invert)
            logger.debug(
                "Display updated partial fullscreen — screen=%s invert=%s",
                screen_name,
                invert,
            )

        _last_frame_img = img
        _last_frame_signature = stable_signature
        _finish_button_action()


# ---------------------------------------------------------------------------
# Schedule positioning
# ---------------------------------------------------------------------------

def _position_schedule():
    games = _load_games()

    idx, _ = sync_manager.find_next_game(games)

    with _state_lock:
        if idx is not None:
            state.jump_to_game(idx)

        state.schedule_game_count = len(games)


# ---------------------------------------------------------------------------
# Data changed
# ---------------------------------------------------------------------------

def _data_changed(old_summary, new_summary, old_games, new_games):
    if old_summary is None or new_summary is None:
        return True

    if old_games is None or new_games is None:
        return True

    if old_summary.get("record") != new_summary.get("record"):
        return True

    if old_summary.get("ws_index") != new_summary.get("ws_index"):
        return True

    if old_summary.get("nl_west_rank") != new_summary.get("nl_west_rank"):
        return True

    if old_summary.get("mlb_rank") != new_summary.get("mlb_rank"):
        return True

    old_statuses = {
        g.get("game_pk"): g.get("status")
        for g in old_games
    }

    new_statuses = {
        g.get("game_pk"): g.get("status")
        for g in new_games
    }

    if old_statuses != new_statuses:
        return True

    old_scores = {
        g.get("game_pk"): (
            g.get("dodgers_score"),
            g.get("opponent_score")
        )
        for g in old_games
    }

    new_scores = {
        g.get("game_pk"): (
            g.get("dodgers_score"),
            g.get("opponent_score")
        )
        for g in new_games
    }

    return old_scores != new_scores


# ---------------------------------------------------------------------------
# Button handlers
# ---------------------------------------------------------------------------

def _on_center_short():
    if not _begin_button_action("CENTER short"):
        return

    with _state_lock:
        if state.config_mode:
            logger.info("CENTER short — exit config screen")
            exit_config = True
            exit_live = False
            exit_pregame = False
        elif state.live_mode:
            logger.info("CENTER short — exit live mode")
            exit_config = False
            exit_live = True
            exit_pregame = False
        elif state.pregame_mode:
            logger.info("CENTER short — exit pregame screen")
            exit_config = False
            exit_live = False
            exit_pregame = True
        else:
            exit_config = False
            exit_live = False
            exit_pregame = False

    if exit_config:
        _exit_config_mode()
        return

    if exit_live:
        _exit_live_mode(suppress_current=True)
        return

    if exit_pregame:
        _exit_pregame_mode()
        return

    with _state_lock:
        logger.info("CENTER short — current page before toggle: %d", state.page)
        state.toggle_page()
        logger.info("CENTER short — changed to page %d", state.page)
        is_schedule = state.page == config.PAGE_SCHEDULE
        needs_clear = state.page in (config.PAGE_BRIEFING, config.PAGE_SCHEDULE)

    if is_schedule:
        _position_schedule()

    _request_display(full=True, clear=needs_clear)


def _on_center_long():
    if not _begin_button_action("CENTER long"):
        return

    logger.info("CENTER long — force sync")

    online = sync_manager.check_connectivity()
    _set_online_state(online)

    if online:
        _do_sync()
        _position_schedule()
        _handle_auto_live(_load_games())
    else:
        with _state_lock:
            state.stale = True
        logger.warning("Force sync failed — offline")

    _request_display(full=True)


def _on_left_short():
    if not _begin_button_action("LEFT short"):
        return

    with _state_lock:
        if state.config_mode or state.live_mode or state.pregame_mode or state.page != config.PAGE_SCHEDULE:
            _finish_button_action()
            return
        logger.info("LEFT short — schedule back")
        state.scroll_schedule_back()

    _request_display(full=True, clear=True)


def _on_right_short():
    if not _begin_button_action("RIGHT short"):
        return

    with _state_lock:
        if state.config_mode or state.live_mode or state.pregame_mode or state.page != config.PAGE_SCHEDULE:
            _finish_button_action()
            return
        logger.info("RIGHT short — schedule forward")
        state.scroll_schedule_forward()

    _request_display(full=True, clear=True)


def _on_left_long():
    if not _begin_button_action("LEFT long"):
        return

    with _state_lock:
        if state.config_mode or state.live_mode or state.pregame_mode or state.page != config.PAGE_SCHEDULE:
            _finish_button_action()
            return
        logger.info("LEFT long — jump to schedule start")
        state.jump_to_game(0)

    _request_display(full=True, clear=True)


def _on_right_long():
    if not _begin_button_action("RIGHT long"):
        return

    with _state_lock:
        if state.config_mode or state.live_mode or state.pregame_mode or state.page != config.PAGE_SCHEDULE:
            _finish_button_action()
            return

    logger.info("RIGHT long — jump to next game")

    games = _load_games()
    idx, _ = sync_manager.find_next_game(games)

    if idx is not None:
        with _state_lock:
            state.jump_to_game(idx)

    _request_display(full=True, clear=True)


def _on_live():
    if not _begin_button_action("LIVE"):
        return

    with _state_lock:
        in_live_mode = state.live_mode
        in_pregame_mode = state.pregame_mode

    if in_live_mode:
        logger.info("LIVE button pressed — exit live mode")
        _exit_live_mode(suppress_current=True)
        return

    if in_pregame_mode:
        logger.info("LIVE button pressed — exit pregame screen")
        _exit_pregame_mode()
        return

    games = _load_games()
    game_pk = _find_live_game_pk(games)

    if not game_pk:
        upcoming_game = _find_next_upcoming_game(games)
        if upcoming_game:
            logger.info("LIVE button pressed — showing next upcoming pregame screen")
            now_utc = datetime.now(timezone.utc)
            try:
                start_utc = datetime.fromisoformat(
                    upcoming_game["date_utc"].replace("Z", "+00:00")
                )
                seconds_remaining = max(
                    0,
                    int((start_utc - now_utc).total_seconds()),
                )
            except Exception:
                seconds_remaining = 0

            with _state_lock:
                state.page = config.PAGE_BRIEFING
                state.live_mode = False
                state.live_game_pk = None
                state.live_game_data = None
                state.pregame_mode = True
                state.pregame_manual = True
                state.pregame_game = upcoming_game
                state.pregame_seconds_remaining = seconds_remaining
            _request_display(full=True, clear=True)
            return

        logger.info("LIVE button pressed — showing no-live-game screen")
        with _state_lock:
            state.live_mode = True
            state.live_game_pk = None
            state.live_game_data = None
            state.pregame_mode = False
            state.pregame_manual = False
            state.pregame_game = None
            state.pregame_seconds_remaining = None
        _request_display(full=True)
        return

    with _state_lock:
        state.live_suppressed_game_pk = None
        state.pregame_manual = False

    _enter_live_mode(game_pk, auto=False)


def _on_config_combo():
    if not _begin_button_action("LEFT+RIGHT config"):
        return

    logger.info("LEFT+RIGHT hold — show config screen")
    url = config_server.start(on_saved=_restart_after_config_save)

    with _state_lock:
        state.config_mode = True
        state.config_url = url
        state.live_mode = False
        state.live_game_pk = None
        state.live_game_data = None
        state.pregame_mode = False
        state.pregame_manual = False
        state.pregame_game = None
        state.pregame_seconds_remaining = None

    _request_display(full=True, clear=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    logger.info("Tracker starting up — team: %s", config.TEAM_NAME)
    logger.info(
        "Display loop: %ss tick, %ss live poll, %ss sync, %ss full refresh",
        DISPLAY_TICK_SECONDS,
        LIVE_POLL_INTERVAL,
        SYNC_INTERVAL,
        FULL_REFRESH_INTERVAL,
    )

    if BOOT_DELAY > 0:
        logger.info("Boot delay %ds...", BOOT_DELAY)
        time.sleep(BOOT_DELAY)

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.CACHE_DIR, exist_ok=True)

    display_waveshare.init_display(clear=True)
    _position_schedule()

    input_controls.setup(
        on_center_short=_on_center_short,
        on_center_long=_on_center_long,
        on_left_short=_on_left_short,
        on_left_long=_on_left_long,
        on_right_short=_on_right_short,
        on_right_long=_on_right_long,
        on_live=_on_live,
        on_config_combo=_on_config_combo,
    )

    logger.info("Initial render from cache")
    _do_render(force_full=True)

    online = sync_manager.check_connectivity()
    _set_online_state(online)

    if online:
        _do_sync()
        _position_schedule()
        _handle_auto_live(_load_games())
        _request_display(full=True)
    else:
        logger.warning("Offline on startup — showing cached data")
        with _state_lock:
            state.stale = True

    last_sync_time = time.time()
    last_live_poll_time = 0.0

    logger.info("Entering main loop")

    try:
        while True:
            loop_start = time.time()

            with _state_lock:
                live_mode = state.live_mode
                live_game_pk = state.live_game_pk

            if (
                live_game_pk
                and _get_online_state()
                and loop_start - last_live_poll_time >= LIVE_POLL_INTERVAL
            ):
                if _start_live_poll_async():
                    last_live_poll_time = loop_start

            if loop_start - last_sync_time >= SYNC_INTERVAL:
                if _start_sync_async():
                    last_sync_time = loop_start

            _do_render()

            now = time.time()
            elapsed = now - loop_start

            if elapsed >= DISPLAY_TICK_SECONDS:
                logger.debug(
                    "Display loop overran %.2fs tick by %.2fs; rendering next frame immediately",
                    DISPLAY_TICK_SECONDS,
                    elapsed - DISPLAY_TICK_SECONDS,
                )
                time.sleep(0.01)
            else:
                sleep_for = DISPLAY_TICK_SECONDS - (now % DISPLAY_TICK_SECONDS)
                time.sleep(max(0.01, min(sleep_for, DISPLAY_TICK_SECONDS - elapsed)))

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt — shutting down")

    finally:
        input_controls.cleanup()
        display_waveshare.sleep()
        logger.info("Tracker stopped")


if __name__ == "__main__":
    main()

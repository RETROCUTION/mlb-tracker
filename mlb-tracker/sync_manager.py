import socket
import math
import logging
from datetime import datetime, timezone
import config
import mlb_api
import cache

logger = logging.getLogger(__name__)


def check_connectivity():
    try:
        socket.create_connection(
            (config.CONNECTIVITY_HOST, config.CONNECTIVITY_PORT),
            timeout=config.CONNECTIVITY_TIMEOUT
        )
        return True
    except OSError:
        return False


def sync():
    season_data = _fetch_display_season()
    if not season_data:
        return False

    season = season_data["season"]
    games = season_data["games"]
    nl_west = season_data["nl_west"]
    all_teams = season_data["all_teams"]
    season_not_started = season_data["season_not_started"]
    upcoming_season = season_data["upcoming_season"]
    season_start_date = season_data.get("season_start_date")
    season_starts_in_days = season_data.get("season_starts_in_days")
    world_series = _fetch_world_series_summary(season) if season_not_started else None

    team = next(
        (t for t in all_teams if t["team_id"] == config.TEAM_ID),
        None
    )
    if not team:
        logger.error("%s not found in standings", config.TEAM_NAME)
        return False

    division_id = team.get("division_id")
    division_teams = [
        t for t in all_teams
        if t.get("division_id") == division_id
    ]
    division_teams.sort(
        key=lambda t: (
            -t.get("pct", 0),
            -t.get("wins", 0),
            -t.get("run_differential", 0),
        )
    )
    division_rank = next(
        (i + 1 for i, t in enumerate(division_teams)
         if t["team_id"] == config.TEAM_ID),
        0
    )

    now_iso = datetime.now(timezone.utc).isoformat()

    cache.write_schedule({
        "fetched_at": now_iso,
        "season": season,
        "upcoming_season": upcoming_season,
        "season_not_started": season_not_started,
        "season_start_date": season_start_date,
        "season_starts_in_days": season_starts_in_days,
        "games": games,
    })

    index = compute_ws_index(
        record={"wins": team["wins"], "losses": team["losses"]},
        mlb_rank=team["mlb_rank"],
        mlb_total=len(all_teams),
        nl_west_rank=division_rank,
        nl_west_count=len(division_teams),
        last_10={
            "wins": team["last_10_wins"],
            "losses": team["last_10_losses"]
        },
        run_diff=team["run_differential"],
    )

    cache.write_summary({
        "fetched_at": now_iso,
        "season": season,
        "upcoming_season": upcoming_season,
        "season_not_started": season_not_started,
        "season_message": _season_message(season, upcoming_season, season_not_started),
        "season_start_date": season_start_date,
        "season_starts_in_days": season_starts_in_days,
        "world_series": world_series,
        "record": {"wins": team["wins"], "losses": team["losses"]},
        "pct": team["pct"],
        "division_rank": division_rank,
        "division_count": len(division_teams),
        "division_id": division_id,
        "division_name": team.get("division_name", ""),
        "nl_west_rank": division_rank,
        "nl_west_games_back": team["games_back"],
        "mlb_rank": team["mlb_rank"],
        "mlb_total_teams": len(all_teams),
        "last_10_wins": team["last_10_wins"],
        "last_10_losses": team["last_10_losses"],
        "run_differential": team["run_differential"],
        "streak": team["streak"],
        "ws_index": index,
        "ws_label": ws_label(index),
        "nl_west_standings": nl_west,
        "all_teams": all_teams,
    })

    return True


def _fetch_display_season():
    current = int(config.CURRENT_SEASON)
    candidates = [current]
    if getattr(config, "SEASON_OVERRIDE", None) is None:
        candidates.append(current - 1)

    first_valid = None
    upcoming_start_date = None
    upcoming_starts_in_days = None

    for season in candidates:
        try:
            raw_schedule = mlb_api.fetch_schedule(season)
            raw_standings = mlb_api.fetch_standings(season)
        except Exception as e:
            logger.error("Fetch failed for %s season: %s", season, e)
            continue

        games = mlb_api.parse_schedule(raw_schedule)
        nl_west, all_teams = mlb_api.parse_standings(raw_standings)
        team = next((t for t in all_teams if t["team_id"] == config.TEAM_ID), None)
        if not team:
            logger.warning("%s not found in %s standings", config.TEAM_NAME, season)
            continue

        data = {
            "season": season,
            "games": games,
            "nl_west": nl_west,
            "all_teams": all_teams,
            "season_not_started": False,
            "upcoming_season": None,
            "season_start_date": None,
            "season_starts_in_days": None,
        }

        if first_valid is None:
            first_valid = data

        if season == current and _season_has_not_started(games):
            upcoming_start_date, upcoming_starts_in_days = _next_season_start(games)
            logger.info("%s season has not started; checking prior season", season)
            continue

        if season != current:
            data["season_not_started"] = True
            data["upcoming_season"] = current
            data["season_start_date"] = upcoming_start_date
            data["season_starts_in_days"] = upcoming_starts_in_days

        return data

    if first_valid:
        first_valid["season_not_started"] = _season_has_not_started(first_valid["games"])
        first_valid["upcoming_season"] = current if first_valid["season_not_started"] else None
        if first_valid["season_not_started"]:
            start_date, starts_in_days = _next_season_start(first_valid["games"])
            first_valid["season_start_date"] = start_date
            first_valid["season_starts_in_days"] = starts_in_days
        return first_valid

    return None


def _season_has_not_started(games):
    if not games:
        return True

    if any(g.get("status") in ("Live", "Final") for g in games):
        return False

    today = datetime.now(config.LOCAL_TZ).date()
    first_game_date = None

    for g in games:
        try:
            start_utc = datetime.fromisoformat(g["date_utc"].replace("Z", "+00:00"))
        except Exception:
            continue

        game_date = start_utc.astimezone(config.LOCAL_TZ).date()
        if first_game_date is None or game_date < first_game_date:
            first_game_date = game_date

    return first_game_date is None or today < first_game_date


def _next_season_start(games):
    today = datetime.now(config.LOCAL_TZ).date()
    first_game_date = None

    for g in games:
        if g.get("status") not in ("Preview", "Pre-Game", "Scheduled"):
            continue

        try:
            start_utc = datetime.fromisoformat(g["date_utc"].replace("Z", "+00:00"))
        except Exception:
            continue

        game_date = start_utc.astimezone(config.LOCAL_TZ).date()
        if first_game_date is None or game_date < first_game_date:
            first_game_date = game_date

    if first_game_date is None:
        return None, None

    return first_game_date.isoformat(), max(0, (first_game_date - today).days)


def _season_message(season, upcoming_season, season_not_started):
    if not season_not_started or not upcoming_season:
        return ""

    return (
        f"{upcoming_season} season has not started yet - "
        f"showing final {season} data"
    )


def _fetch_world_series_summary(season):
    try:
        raw = mlb_api.fetch_world_series_schedule(season)
        return mlb_api.parse_world_series_summary(raw, season)
    except Exception as e:
        logger.warning("World Series summary unavailable for %s: %s", season, e)
        return None


def compute_ws_index(record, mlb_rank, mlb_total, nl_west_rank,
                     nl_west_count, last_10, run_diff):
    games_played = record["wins"] + record["losses"]
    win_pct = record["wins"] / games_played if games_played > 0 else 0.0

    wp_score   = _clamp((win_pct - 0.400) / (0.650 - 0.400) * 30, 0, 30)
    rank_score = _clamp((mlb_total - mlb_rank) / (mlb_total - 1) * 25, 0, 25)
    div_score  = _clamp((nl_west_count - nl_west_rank) / (nl_west_count - 1) * 20, 0, 20)
    l10_score  = _clamp(last_10["wins"] / 10.0 * 15, 0, 15)
    rd_score   = _clamp((run_diff + 100) / 200.0 * 10, 0, 10)

    return round(wp_score + rank_score + div_score + l10_score + rd_score)


def ws_label(index):
    if index >= 90:
        return "ABSOLUTELY"
    elif index >= 75:
        return "VERY LIKELY"
    elif index >= 60:
        return "GOOD CHANCE"
    elif index >= 45:
        return "POSSIBLE"
    elif index >= 30:
        return "UNLIKELY"
    else:
        return "NOT LOOKING GOOD"


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def find_next_game(games):
    for i, g in enumerate(games):
        if g["status"] in ("Preview", "Pre-Game", "Scheduled"):
            return i, g
    return None, None


def find_last_completed_game(games):
    last = None
    last_idx = None
    for i, g in enumerate(games):
        if g["status"] == "Final":
            last = g
            last_idx = i
    return last_idx, last


def is_game_live(games):
    return any(g["status"] == "Live" for g in games)


def sync_interval(games):
    if is_game_live(games):
        return config.SYNC_INTERVAL_GAME_DAY
    return config.SYNC_INTERVAL_NORMAL

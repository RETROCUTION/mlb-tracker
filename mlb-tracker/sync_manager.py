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
    try:
        raw_schedule = mlb_api.fetch_schedule()
        raw_standings = mlb_api.fetch_standings()
    except Exception as e:
        logger.error("Fetch failed: %s", e)
        return False

    games = mlb_api.parse_schedule(raw_schedule)
    nl_west, all_teams = mlb_api.parse_standings(raw_standings)

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
        "season": config.CURRENT_SEASON,
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

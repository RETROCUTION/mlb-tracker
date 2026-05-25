#!/usr/bin/env python3
"""Generate README screenshots from the current layout code."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import ImageOps


APP_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = APP_DIR.parent
OUT_DIR = REPO_DIR / "docs" / "screenshots"
SETTINGS_PATH = APP_DIR / "settings.json"


SAMPLE_SETTINGS = {
    "team_id": 119,
    "team_name": "Los Angeles Dodgers",
    "team_abbr": "LAD",
    "timezone": "America/Los_Angeles",
    "logo": "LAD.png",
}


def ensure_sample_settings():
    if SETTINGS_PATH.exists():
        return False
    SETTINGS_PATH.write_text(json.dumps(SAMPLE_SETTINGS, indent=2), encoding="utf-8")
    return True


def remove_sample_settings(created):
    if created:
        try:
            SETTINGS_PATH.unlink()
        except OSError:
            pass


created_settings = ensure_sample_settings()
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

import config  # noqa: E402
import settings_loader  # noqa: E402
from layouts import draw_utils  # noqa: E402
from layouts import (  # noqa: E402
    layout_briefing,
    layout_config,
    layout_live,
    layout_pregame,
    layout_schedule,
    layout_standings,
)
from state import AppState  # noqa: E402


draw_utils.wifi_signal_quality = lambda: 82


def team_stat(team, rank, wins, losses, div_id, div_name, l10, rdiff, streak):
    return {
        "team_id": team["team_id"],
        "team_abbr": team["team_abbr"],
        "team_name": team["team_name"],
        "wins": wins,
        "losses": losses,
        "pct": wins / max(1, wins + losses),
        "games_back": "-" if rank == 1 else f"{(rank - 1) * 1.5:.1f}",
        "last_10_wins": l10,
        "last_10_losses": 10 - l10,
        "run_differential": rdiff,
        "streak": streak,
        "mlb_rank": rank,
        "division_id": div_id,
        "division_name": div_name,
    }


def sample_teams():
    divs = {
        "LAD": (203, "National League West"),
        "SD": (203, "National League West"),
        "SF": (203, "National League West"),
        "ARI": (203, "National League West"),
        "COL": (203, "National League West"),
        "ATL": (204, "National League East"),
        "PHI": (204, "National League East"),
        "NYM": (204, "National League East"),
        "MIA": (204, "National League East"),
        "WSH": (204, "National League East"),
        "CHC": (205, "National League Central"),
        "MIL": (205, "National League Central"),
        "STL": (205, "National League Central"),
        "CIN": (205, "National League Central"),
        "PIT": (205, "National League Central"),
        "NYY": (201, "American League East"),
        "BAL": (201, "American League East"),
        "BOS": (201, "American League East"),
        "TB": (201, "American League East"),
        "TOR": (201, "American League East"),
        "DET": (202, "American League Central"),
        "KC": (202, "American League Central"),
        "MIN": (202, "American League Central"),
        "CLE": (202, "American League Central"),
        "CWS": (202, "American League Central"),
        "SEA": (200, "American League West"),
        "TEX": (200, "American League West"),
        "HOU": (200, "American League West"),
        "LAA": (200, "American League West"),
        "ATH": (200, "American League West"),
    }
    order = [
        "LAD", "SD", "SF", "ARI", "COL", "ATL", "PHI", "NYM", "MIA", "WSH",
        "CHC", "MIL", "STL", "CIN", "PIT", "NYY", "BAL", "BOS", "TB", "TOR",
        "DET", "KC", "MIN", "CLE", "CWS", "SEA", "TEX", "HOU", "LAA", "ATH",
    ]
    by_abbr = {t["team_abbr"]: t for t in settings_loader.ALL_TEAMS}

    teams = []
    for idx, abbr in enumerate(order, start=1):
        team = by_abbr[abbr]
        wins = max(18, 39 - (idx // 3) - (idx % 5))
        losses = 58 - wins
        if abbr == "LAD":
            wins, losses = 38, 20
        if abbr == "MIL":
            wins, losses = 33, 25
        div_id, div_name = divs[abbr]
        l10 = [8, 7, 6, 5, 9][idx % 5]
        teams.append(
            team_stat(
                team,
                idx,
                wins,
                losses,
                div_id,
                div_name,
                l10,
                90 - idx * 5,
                "W2" if idx % 2 else "L1",
            )
        )
    return teams


def sample_summary():
    teams = sample_teams()
    return {
        "season": 2026,
        "record": {"wins": 38, "losses": 20},
        "pct": 38 / 58,
        "division_rank": 1,
        "division_name": "National League West",
        "mlb_rank": 1,
        "mlb_total_teams": 30,
        "last_10_wins": 8,
        "last_10_losses": 2,
        "run_differential": 86,
        "ws_index": 81,
        "ws_label": "STRONG POSTSEASON POSITION",
        "all_teams": teams,
    }


def sample_games():
    return [
        {
            "game_pk": 1001,
            "date_utc": "2026-05-22T23:40:00Z",
            "status": "Final",
            "home_away": "away",
            "opponent_id": 158,
            "opponent_name": "Milwaukee Brewers",
            "opponent_abbr": "MIL",
            "venue": "American Family Field",
            "dodgers_score": 6,
            "opponent_score": 3,
            "result": "W",
            "decision_winner": "Yamamoto",
            "decision_loser": "Peralta",
            "game_number": 1,
        },
        {
            "game_pk": 1002,
            "date_utc": "2026-05-23T23:40:00Z",
            "status": "Final",
            "home_away": "away",
            "opponent_id": 158,
            "opponent_name": "Milwaukee Brewers",
            "opponent_abbr": "MIL",
            "venue": "American Family Field",
            "dodgers_score": 2,
            "opponent_score": 4,
            "result": "L",
            "decision_winner": "Quintana",
            "decision_loser": "Glasnow",
            "game_number": 2,
        },
        {
            "game_pk": 1003,
            "date_utc": "2026-05-24T23:10:00Z",
            "status": "Scheduled",
            "home_away": "home",
            "opponent_id": 158,
            "opponent_name": "Milwaukee Brewers",
            "opponent_abbr": "MIL",
            "venue": "Dodger Stadium",
            "probable_pitcher_dodgers": "Tyler Glasnow",
            "probable_pitcher_opponent": "Freddy Peralta",
            "game_number": 3,
        },
        {
            "game_pk": 1004,
            "date_utc": "2026-05-25T23:40:00Z",
            "status": "Scheduled",
            "home_away": "away",
            "opponent_id": 135,
            "opponent_name": "San Diego Padres",
            "opponent_abbr": "SD",
            "venue": "Petco Park",
            "probable_pitcher_dodgers": "Yoshinobu Yamamoto",
            "probable_pitcher_opponent": "Dylan Cease",
            "game_number": 1,
        },
        {
            "game_pk": 1005,
            "date_utc": "2026-05-26T23:40:00Z",
            "status": "Scheduled",
            "home_away": "home",
            "opponent_id": 137,
            "opponent_name": "San Francisco Giants",
            "opponent_abbr": "SF",
            "venue": "Dodger Stadium",
            "probable_pitcher_dodgers": "Shohei Ohtani",
            "probable_pitcher_opponent": "Logan Webb",
            "game_number": 1,
        },
        {
            "game_pk": 1006,
            "date_utc": "2026-05-27T23:40:00Z",
            "status": "Scheduled",
            "home_away": "away",
            "opponent_id": 109,
            "opponent_name": "Arizona Diamondbacks",
            "opponent_abbr": "ARI",
            "venue": "Chase Field",
            "game_number": 1,
        },
        {
            "game_pk": 1007,
            "date_utc": "2026-05-28T23:40:00Z",
            "status": "Scheduled",
            "home_away": "home",
            "opponent_id": 112,
            "opponent_name": "Chicago Cubs",
            "opponent_abbr": "CHC",
            "venue": "Dodger Stadium",
            "game_number": 1,
        },
    ]


def live_game():
    return {
        "away_name": "Milwaukee Brewers",
        "away_abbr": "MIL",
        "home_name": "Los Angeles Dodgers",
        "home_abbr": "LAD",
        "away_score": 3,
        "home_score": 5,
        "inning": 7,
        "inning_half": "Bot",
        "status_detail": "In Progress",
        "outs": 1,
        "balls": 2,
        "strikes": 2,
        "pitch_number": 7,
        "on_1b": True,
        "on_2b": True,
        "on_3b": False,
        "runner_1b_name": "Will Smith",
        "runner_2b_name": "Mookie Betts",
        "batter_name": "Freddie Freeman",
        "batter_avg": ".315",
        "batter_ab_today": 3,
        "batter_h_today": 2,
        "pitcher_name": "Freddy Peralta",
        "pitcher_era": "3.42",
        "pitch_count": 88,
        "last_pitch_speed": 96,
        "last_pitch_type": "4-Seam Fastball",
        "last_play": "Freeman fouls off another fastball. The count stays 2-2.",
        "away_innings": [0, 0, 1, 0, 2, 0, 0, None, None],
        "home_innings": [1, 0, 0, 2, 0, 1, None, None, None],
        "away_hits": 7,
        "home_hits": 9,
        "away_errors": 0,
        "home_errors": 1,
    }


def save(img, name, invert=False):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if invert:
        img = ImageOps.invert(img.convert("L"))
    img.save(OUT_DIR / name)


def main():
    state = AppState()
    state.stale = False
    state.last_sync_time = datetime.now(timezone.utc)
    state.display_season = 2026
    state.schedule_game_count = len(sample_games())

    summary = sample_summary()
    games = sample_games()

    save(layout_briefing.render(state, summary, games), "briefing.png")

    state.page = config.PAGE_SCHEDULE
    save(layout_schedule.render(state, games), "schedule.png", invert=True)

    state.page = config.PAGE_STANDINGS
    save(layout_standings.render(state, summary), "rankings.png", invert=True)

    state.page = config.PAGE_BRIEFING
    state.pregame_mode = True
    state.pregame_game = games[2]
    state.pregame_seconds_remaining = 2 * 3600 + 14 * 60 + 33
    save(layout_pregame.render(state, state.pregame_game, state.pregame_seconds_remaining), "pregame.png")
    state.pregame_mode = False

    state.live_mode = True
    state.live_game_data = live_game()
    save(layout_live.render(state, state.live_game_data), "live.png")
    state.live_mode = False

    state.config_mode = True
    state.config_url = "http://mlb-tracker.local:8765"
    save(layout_config.render(state), "config.png")

    print(f"Generated screenshots in {OUT_DIR}")


if __name__ == "__main__":
    try:
        main()
    finally:
        remove_sample_settings(created_settings)

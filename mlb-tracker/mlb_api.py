import requests
import config

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "mlb-tracker/1.0"})


def fetch_schedule():
    url = (
        f"{config.MLB_BASE_URL}/schedule"
        f"?sportId=1"
        f"&teamId={config.TEAM_ID}"
        f"&startDate={config.CURRENT_SEASON}-03-20"
        f"&endDate={config.CURRENT_SEASON}-11-15"
        f"&hydrate=team,linescore,probablePitcher,decisions"
    )
    resp = SESSION.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_standings():
    url = (
        f"{config.MLB_BASE_URL}/standings"
        f"?leagueId=103,104"
        f"&season={config.CURRENT_SEASON}"
        f"&standingsTypes=regularSeason"
        f"&hydrate=team,league,division,sport,record,standings"
    )
    resp = SESSION.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_live_game(game_pk):
    """
    Fetch the full live game feed for a given gamePk.
    Returns the raw JSON from the live feed endpoint.
    Poll this every 5-10 seconds during a live game.
    """
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    resp = SESSION.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def parse_live_game(raw):
    """
    Parse the live game feed into a flat dict that layout_live.py can use.
    Returns None if the game is not live.
    """
    try:
        game_data  = raw.get("gameData", {})
        live_data  = raw.get("liveData", {})

        # Game status
        status      = game_data.get("status", {})
        abstract    = status.get("abstractGameState", "")
        detail      = status.get("detailedState", "")

        # Teams — get both full name and abbreviation
        teams       = game_data.get("teams", {})
        away_team   = teams.get("away", {})
        home_team   = teams.get("home", {})

        # Try teamName (short like "Dodgers") first, fall back to full name
        away_name   = away_team.get("teamName") or away_team.get("name", "Away")
        home_name   = home_team.get("teamName") or home_team.get("name", "Home")
        away_abbr   = away_team.get("abbreviation") or away_team.get("abbrev", "AWY")
        home_abbr   = home_team.get("abbreviation") or home_team.get("abbrev", "HME")

        # Linescore
        linescore   = live_data.get("linescore", {})
        inning      = linescore.get("currentInning", 1)
        inning_half = linescore.get("inningHalf", "Top")
        outs        = linescore.get("outs", 0)

        ls_teams    = linescore.get("teams", {})
        away_score  = ls_teams.get("away", {}).get("runs", 0) or 0
        home_score  = ls_teams.get("home", {}).get("runs", 0) or 0
        away_hits   = ls_teams.get("away", {}).get("hits", 0) or 0
        home_hits   = ls_teams.get("home", {}).get("hits", 0) or 0
        away_errors = ls_teams.get("away", {}).get("errors", 0) or 0
        home_errors = ls_teams.get("home", {}).get("errors", 0) or 0

        # Count
        offense     = linescore.get("offense", {})
        defense     = linescore.get("defense", {})
        balls       = linescore.get("balls", 0)
        strikes     = linescore.get("strikes", 0)

        # Runners on base
        runner_1b = offense.get("first")
        runner_2b = offense.get("second")
        runner_3b = offense.get("third")
        on_1b = runner_1b is not None
        on_2b = runner_2b is not None
        on_3b = runner_3b is not None

        def runner_name(player):
            if not player:
                return ""
            return player.get("fullName") or player.get("lastName") or ""

        # Inning-by-inning line score
        innings_data = linescore.get("innings", [])
        away_innings = []
        home_innings = []
        for inn in innings_data:
            away_inn = inn.get("away", {})
            home_inn = inn.get("home", {})
            away_innings.append(away_inn.get("runs"))
            home_innings.append(home_inn.get("runs"))

        try:
            current_idx = max(0, int(inning or 1) - 1)
        except (TypeError, ValueError):
            current_idx = 0
        while len(away_innings) <= current_idx:
            away_innings.append(None)
        while len(home_innings) <= current_idx:
            home_innings.append(None)

        def completed_runs(values, skip_idx):
            return sum(
                int(v)
                for i, v in enumerate(values)
                if i != skip_idx and v is not None
            )

        def current_inning_runs(total, values):
            return max(0, int(total or 0) - completed_runs(values, current_idx))

        half = inning_half.lower()
        if half in ("top", "t"):
            away_innings[current_idx] = None
        else:
            away_innings[current_idx] = current_inning_runs(away_score, away_innings)
            home_innings[current_idx] = None

        # Current batter
        plays       = live_data.get("plays", {})
        current     = plays.get("currentPlay", {})
        matchup     = current.get("matchup", {})

        batter      = matchup.get("batter", {})
        batter_name = batter.get("fullName", "—")
        batter_id   = batter.get("id")

        pitcher     = matchup.get("pitcher", {})
        pitcher_name = pitcher.get("fullName", "—")

        # Batter stats today (from boxscore)
        boxscore    = live_data.get("boxscore", {})
        box_teams   = boxscore.get("teams", {})

        def get_batter_stats(side_key, pid):
            if not pid:
                return ".---", 0, 0
            players = box_teams.get(side_key, {}).get("players", {})
            p = players.get(f"ID{pid}", {})
            stats = p.get("stats", {}).get("batting", {})
            season = p.get("seasonStats", {}).get("batting", {})
            avg    = season.get("avg", ".---")
            ab     = stats.get("atBats", 0)
            hits   = stats.get("hits", 0)
            return avg, ab, hits

        # Figure out which side is batting
        if inning_half.lower() in ("top", "t"):
            batting_side = "away"
        else:
            batting_side = "home"

        batter_avg, batter_ab, batter_h = get_batter_stats(batting_side, batter_id)

        # Pitcher pitch count
        pitcher_id  = pitcher.get("id")
        def get_pitcher_stats(side_key, pid):
            if not pid:
                return "-.--", 0
            players = box_teams.get(side_key, {}).get("players", {})
            p = players.get(f"ID{pid}", {})
            stats  = p.get("stats", {}).get("pitching", {})
            season = p.get("seasonStats", {}).get("pitching", {})
            era    = season.get("era", "-.--")
            pitches = stats.get("pitchesThrown", 0)
            return era, pitches

        fielding_side = "home" if batting_side == "away" else "away"
        pitcher_era, pitch_count = get_pitcher_stats(fielding_side, pitcher_id)

        # Last pitch
        play_events = current.get("playEvents", [])
        pitch_number = sum(1 for ev in play_events if ev.get("isPitch"))
        last_pitch_speed = None
        last_pitch_type  = None
        for ev in reversed(play_events):
            if ev.get("isPitch"):
                pd = ev.get("pitchData", {})
                last_pitch_speed = pd.get("startSpeed")
                if last_pitch_speed:
                    last_pitch_speed = round(last_pitch_speed)
                details = ev.get("details", {})
                pt = details.get("type", {})
                last_pitch_type = pt.get("description")
                break

        # Last play description
        all_plays   = plays.get("allPlays", [])
        last_play   = ""
        if all_plays:
            last_completed = None
            for p in reversed(all_plays):
                if p.get("about", {}).get("isComplete"):
                    last_completed = p
                    break
            if last_completed:
                result = last_completed.get("result", {})
                last_play = result.get("description", "")

        return {
            "game_pk":       raw.get("gamePk"),
            "status":        abstract,
            "status_detail": detail,
            "away_name":     away_name,
            "away_abbr":     away_abbr,
            "home_name":     home_name,
            "home_abbr":     home_abbr,
            "away_score":    away_score,
            "home_score":    home_score,
            "away_hits":     away_hits,
            "home_hits":     home_hits,
            "away_errors":   away_errors,
            "home_errors":   home_errors,
            "inning":        inning,
            "inning_half":   inning_half,
            "outs":          outs,
            "balls":         balls,
            "strikes":       strikes,
            "on_1b":         on_1b,
            "on_2b":         on_2b,
            "on_3b":         on_3b,
            "runner_1b_name": runner_name(runner_1b),
            "runner_2b_name": runner_name(runner_2b),
            "runner_3b_name": runner_name(runner_3b),
            "away_innings":  away_innings,
            "home_innings":  home_innings,
            "batter_name":   batter_name,
            "batter_avg":    batter_avg,
            "batter_ab_today": batter_ab,
            "batter_h_today":  batter_h,
            "pitcher_name":  pitcher_name,
            "pitcher_era":   pitcher_era,
            "pitch_count":   pitch_count,
            "pitch_number":  pitch_number,
            "last_pitch_speed": last_pitch_speed,
            "last_pitch_type":  last_pitch_type,
            "last_play":     last_play,
        }

    except Exception as e:
        import logging
        logging.getLogger(__name__).error("parse_live_game failed: %s", e)
        return None


def parse_schedule(raw):
    games = []
    for date_entry in raw.get("dates", []):
        for g in date_entry.get("games", []):
            teams = g.get("teams", {})
            home = teams.get("home", {})
            away = teams.get("away", {})
            is_home = (home.get("team", {}).get("id") == config.TEAM_ID)
            my_side  = home if is_home else away
            opp_side = away if is_home else home
            status = g.get("status", {})
            game_state    = status.get("abstractGameState", "Preview")
            status_detail = status.get("detailedState", "")
            linescore = g.get("linescore", {})
            ls_teams  = linescore.get("teams", {})

            if is_home:
                my_score  = ls_teams.get("home", {}).get("runs")
                opp_score = ls_teams.get("away", {}).get("runs")
            else:
                my_score  = ls_teams.get("away", {}).get("runs")
                opp_score = ls_teams.get("home", {}).get("runs")

            if game_state == "Final":
                if my_score is not None and opp_score is not None:
                    result = "W" if my_score > opp_score else "L"
                else:
                    result = None
            else:
                result = None

            def probable(side):
                p = side.get("probablePitcher")
                return p.get("fullName") if p else None

            decisions = g.get("decisions", {})
            winner = decisions.get("winner", {}).get("fullName")
            loser  = decisions.get("loser", {}).get("fullName")

            inning      = linescore.get("currentInning", "")
            inning_half = linescore.get("inningHalf", "")

            games.append({
                "game_pk":     g.get("gamePk"),
                "game_number": g.get("gameNumber", 1),
                "date_utc":    g.get("gameDate", ""),
                "status":      game_state,
                "status_detail": status_detail,
                "home_away":   "home" if is_home else "away",
                "venue":       g.get("venue", {}).get("name", ""),
                "opponent_id":    opp_side.get("team", {}).get("id"),
                "opponent_name":  opp_side.get("team", {}).get("name", ""),
                "opponent_abbr":  opp_side.get("team", {}).get("abbreviation", ""),
                "dodgers_score":  my_score,
                "opponent_score": opp_score,
                "result":      result,
                "probable_pitcher_dodgers":  probable(my_side),
                "probable_pitcher_opponent": probable(opp_side),
                "decision_winner": winner,
                "decision_loser":  loser,
                "inning":      inning,
                "inning_half": inning_half,
            })

    games.sort(key=lambda g: (g["date_utc"], g["game_number"]))
    return games


def parse_standings(raw):
    nl_west   = []
    all_teams = []

    for record in raw.get("records", []):
        division    = record.get("division", {})
        division_id = division.get("id")
        is_nl_west  = division_id == 203

        for tr in record.get("teamRecords", []):
            wins   = tr.get("wins", 0)
            losses = tr.get("losses", 0)
            pct    = wins / (wins + losses) if (wins + losses) > 0 else 0.0

            split_records = tr.get("records", {}).get("splitRecords", [])
            last_10 = next(
                (s for s in split_records if s.get("type") == "lastTen"), {}
            )

            entry = {
                "team_id":      tr.get("team", {}).get("id"),
                "team_name":    tr.get("team", {}).get("name", ""),
                "team_abbr":    tr.get("team", {}).get("abbreviation", ""),
                "wins":         wins,
                "losses":       losses,
                "pct":          pct,
                "games_back":   tr.get("gamesBack", "-"),
                "last_10_wins":   last_10.get("wins", 0),
                "last_10_losses": last_10.get("losses", 0),
                "run_differential": tr.get("runDifferential", 0),
                "streak":       tr.get("streak", {}).get("streakCode", ""),
                "division_id":  division_id,
                "division_name": division.get("name", ""),
            }
            all_teams.append(entry)
            if is_nl_west:
                nl_west.append(entry)

    all_teams.sort(key=lambda t: (-t["pct"], -t["wins"], -t["run_differential"]))
    for i, t in enumerate(all_teams):
        t["mlb_rank"] = i + 1

    nl_west.sort(key=lambda t: (-t["pct"], -t["wins"]))

    return nl_west, all_teams

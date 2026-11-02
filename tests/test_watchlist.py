import polars as pl

from src.watchlist.scoring import (
    WatchlistParams,
    avg_fdr_by_team,
    build_watchlist,
    next_gameweek,
)

GW_ROUNDS = [1, 2, 3, 4, 5]


def make_fixtures():
    # team 1 has easy fixtures (2), team 2 has hard fixtures (5).
    # Event 5 is finished and must be ignored.
    rows = [
        # event, team_h, team_a, h_diff, a_diff, finished
        (5, 1, 2, 2, 5, True),
        (6, 1, 3, 2, 4, False),
        (7, 2, 1, 5, 2, False),
        (8, 1, 2, 2, 5, False),
        (9, 2, 1, 5, 2, False),
    ]
    return pl.DataFrame(
        rows,
        schema=["event", "team_h", "team_a", "team_h_difficulty", "team_a_difficulty", "finished"],
    )


def make_teams():
    return pl.DataFrame({"id": [1, 2, 3], "short_name": ["AAA", "BBB", "CCC"]})


def player(pid, name, team, pos, status="a", cost=60, own=10.0):
    return {
        "id": pid, "web_name": name, "team": team, "element_type": pos,
        "status": status, "now_cost": cost, "selected_by_percent": own,
    }


def history(pid, points=6, minutes=90, starts=1, xgi=0.5, xgc=1.0, rounds=GW_ROUNDS):
    return [
        {
            "element": pid, "round": r, "total_points": points, "minutes": minutes,
            "starts": starts, "expected_goal_involvements": xgi, "expected_goals_conceded": xgc,
        }
        for r in rounds
    ]


def build(players, hist_rows, params=None):
    return build_watchlist(
        pl.DataFrame(players),
        pl.DataFrame(hist_rows),
        make_fixtures(),
        make_teams(),
        params or WatchlistParams(fixture_window=3),
    )


def test_next_gameweek_is_first_unfinished_event():
    assert next_gameweek(make_fixtures()) == 6


def test_avg_fdr_uses_only_unfinished_fixtures_within_window():
    out = avg_fdr_by_team(make_fixtures(), window=3).sort("team")
    fdr = dict(zip(out["team"].to_list(), out["avg_fdr"].to_list()))
    # team 1: events 6,7,8 -> 2,2,2 ; team 2: events 7,8,9 -> 5,5,5
    assert fdr[1] == 2.0
    assert fdr[2] == 5.0


def test_better_player_ranks_first_within_position():
    players = [player(1, "Good", 1, 3), player(2, "Bad", 2, 3)]
    hist = history(1, points=8, xgi=1.0) + history(2, points=2, xgi=0.1)
    out = build(players, hist)
    assert out["web_name"].to_list() == ["Good", "Bad"]
    assert out["score"][0] > out["score"][1]


def test_defender_prefers_lower_xgc():
    players = [player(1, "Tight", 1, 2), player(2, "Leaky", 1, 2)]
    hist = history(1, points=5, xgc=0.3) + history(2, points=5, xgc=2.0)
    out = build(players, hist)
    assert out["web_name"].to_list() == ["Tight", "Leaky"]


def test_goalkeepers_are_excluded():
    players = [player(1, "Keeper", 1, 1), player(2, "Mid", 1, 3)]
    hist = history(1) + history(2)
    out = build(players, hist)
    assert out["web_name"].to_list() == ["Mid"]


def test_non_available_players_are_excluded():
    players = [
        player(1, "Fit", 1, 3),
        player(2, "Doubtful", 1, 3, status="d"),
        player(3, "Injured", 1, 3, status="i"),
    ]
    hist = history(1) + history(2) + history(3)
    out = build(players, hist)
    assert out["web_name"].to_list() == ["Fit"]


def test_rotation_players_with_fewer_than_3_starts_are_excluded():
    players = [player(1, "Regular", 1, 3), player(2, "Rotation", 1, 3)]
    hist = history(1, starts=1) + [
        {**row, "starts": 1 if row["round"] <= 2 else 0, "minutes": 90 if row["round"] <= 2 else 15}
        for row in history(2)
    ]
    out = build(players, hist)
    assert out["web_name"].to_list() == ["Regular"]


def test_top_n_per_position():
    players = [player(i, f"M{i}", 1, 3) for i in range(1, 8)]
    hist = [row for i in range(1, 8) for row in history(i, points=i)]
    out = build(players, hist, WatchlistParams(fixture_window=3, top_n=5))
    assert len(out) == 5
    assert out["web_name"][0] == "M7"


def test_output_columns_and_price_in_millions():
    out = build([player(1, "Good", 1, 3, cost=75, own=12.5)], history(1))
    assert out.columns == [
        "element_type", "web_name", "team", "price", "ownership", "score",
        "ppg", "xg_p90", "avg_fdr", "minutes_reliability",
    ]
    row = out.row(0, named=True)
    assert row["price"] == 7.5
    assert row["ownership"] == 12.5
    assert row["team"] == "AAA"
    assert row["minutes_reliability"] == 1.0


def test_minutes_reliability_counts_gameweeks_with_60_plus_minutes():
    hist = [
        {**row, "minutes": 90 if row["round"] <= 4 else 30, "starts": 1}
        for row in history(1)
    ]
    out = build([player(1, "P", 1, 3)], hist)
    assert out["minutes_reliability"][0] == 0.8

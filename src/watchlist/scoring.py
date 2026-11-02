"""
Watchlist scoring: pure Polars functions, no I/O.

Ranks DEF/MID/FWD players on recent form, underlying stats, upcoming
fixtures and minutes reliability. See DESIGN.md.
"""

from typing import Optional
import polars as pl
from config import WatchlistConfig, config

DEFENDER, MIDFIELDER, FORWARD = 2, 3, 4
NEUTRAL_FDR = 3.0  # used when a team has no upcoming fixtures

OUTPUT_COLUMNS = [
    "element_type", "web_name", "team", "price", "ownership", "score",
    "ppg", "xg_p90", "avg_fdr", "minutes_reliability",
]


WatchlistParams = WatchlistConfig


def next_gameweek(fixtures: pl.DataFrame) -> Optional[int]:
    """First gameweek that still has an unfinished fixture"""
    upcoming = fixtures.filter(~pl.col("finished") & pl.col("event").is_not_null())
    return None if upcoming.is_empty() else int(upcoming["event"].min())


def avg_fdr_by_team(fixtures: pl.DataFrame, window: int) -> pl.DataFrame:
    """Average FDR of each team's next `window` unfinished fixtures"""
    upcoming = fixtures.filter(~pl.col("finished") & pl.col("event").is_not_null())
    home = upcoming.select(
        pl.col("team_h").alias("team"), "event", pl.col("team_h_difficulty").alias("fdr")
    )
    away = upcoming.select(
        pl.col("team_a").alias("team"), "event", pl.col("team_a_difficulty").alias("fdr")
    )
    return (
        pl.concat([home, away])
        .filter(pl.col("event").rank("ordinal").over("team") <= window)
        .group_by("team")
        .agg(pl.col("fdr").mean().alias("avg_fdr"))
    )


def _recent_form(history: pl.DataFrame, params: WatchlistParams) -> pl.DataFrame:
    """Per-player form stats over the last `history_window` gameweeks"""
    last_round = history["round"].max()
    first_round = last_round - params.history_window + 1
    window = history.filter(pl.col("round") >= first_round)
    return window.group_by("element").agg(
        pl.col("starts").sum().alias("starts"),
        pl.col("total_points").filter(pl.col("minutes") > 0).mean().alias("ppg"),
        pl.col("expected_goal_involvements").sum().alias("_xgi"),
        pl.col("expected_goals_conceded").sum().alias("_xgc"),
        pl.col("minutes").sum().alias("_minutes"),
        (
            (pl.col("minutes") >= params.reliable_minutes).sum() / params.history_window
        ).alias("minutes_reliability"),
    )


def _minmax(col: str) -> pl.Expr:
    """Min-max normalise a column within each position (0 if all equal)"""
    low = pl.col(col).min().over("element_type")
    high = pl.col(col).max().over("element_type")
    return pl.when(high == low).then(0.0).otherwise((pl.col(col) - low) / (high - low))


def build_watchlist(
    players: pl.DataFrame,
    history: pl.DataFrame,
    fixtures: pl.DataFrame,
    teams: pl.DataFrame,
    params: Optional[WatchlistParams] = None,
) -> pl.DataFrame:
    """
    Build the watchlist: top `top_n` players per position, best first.

    Args:
        players: bootstrap-static players (id, web_name, team, element_type,
            now_cost, selected_by_percent, status)
        history: per-gameweek player history (element, round, minutes, starts,
            total_points, expected_goal_involvements, expected_goals_conceded)
        fixtures: FPL fixtures (event, team_h, team_a, team_h_difficulty,
            team_a_difficulty, finished)
        teams: teams (id, short_name)
        params: scoring parameters (defaults to config.watchlist)
    """
    params = params or config.watchlist

    df = (
        players.filter(
            pl.col("element_type").is_in([DEFENDER, MIDFIELDER, FORWARD])
            & (pl.col("status") == "a")
        )
        .join(_recent_form(history, params), left_on="id", right_on="element", how="inner")
        .filter(pl.col("starts") >= params.min_starts)
        .join(avg_fdr_by_team(fixtures, params.fixture_window), on="team", how="left")
        .with_columns(pl.col("avg_fdr").fill_null(NEUTRAL_FDR))
        .join(teams.select(pl.col("id").alias("team"), pl.col("short_name")), on="team", how="left")
        .with_columns(
            pl.when(pl.col("element_type") == DEFENDER)
            .then(pl.col("_xgc"))
            .otherwise(pl.col("_xgi"))
            .alias("_xg_sum")
        )
        .with_columns(
            pl.when(pl.col("_minutes") > 0)
            .then(pl.col("_xg_sum") / pl.col("_minutes") * 90)
            .otherwise(0.0)
            .alias("xg_p90")
        )
    )

    # Higher is better, except xGC for defenders and FDR
    xg_norm = (
        pl.when(pl.col("element_type") == DEFENDER)
        .then(1 - _minmax("xg_p90"))
        .otherwise(_minmax("xg_p90"))
    )
    score = (
        params.weight_points * _minmax("ppg")
        + params.weight_xg * xg_norm
        + params.weight_fixtures * (1 - _minmax("avg_fdr"))
        + params.weight_minutes * _minmax("minutes_reliability")
    )

    return (
        df.with_columns((score * 100).alias("score"))
        .filter(pl.col("score").rank("ordinal", descending=True).over("element_type") <= params.top_n)
        .sort(["element_type", "score"], descending=[False, True])
        .select(
            "element_type",
            "web_name",
            pl.col("short_name").alias("team"),
            (pl.col("now_cost") / 10).alias("price"),
            pl.col("selected_by_percent").alias("ownership"),
            "score",
            "ppg",
            "xg_p90",
            "avg_fdr",
            "minutes_reliability",
        )
    )

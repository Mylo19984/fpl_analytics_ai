"""
Data loading functions for FPL Analytics Streamlit app.
Handles loading and caching of parquet data.
"""

from pathlib import Path
from typing import List, Optional
import streamlit as st
import polars as pl


@st.cache_data
def get_available_dates() -> List[str]:
    """
    Get list of available data dates from player_history directory.

    Returns:
        List of date strings in YYYY-MM-DD format, sorted newest first
    """
    data_root = Path("./data/player_history")

    if not data_root.exists():
        return []

    dates = []
    for d in data_root.iterdir():
        if d.is_dir() and d.name.startswith("date="):
            date_str = d.name.replace("date=", "")
            dates.append(date_str)

    return sorted(dates, reverse=True)


def get_latest_date() -> Optional[str]:
    """
    Get the most recent data date.

    Returns:
        Latest date string or None if no dates found
    """
    dates = get_available_dates()
    return dates[0] if dates else None


@st.cache_data(ttl=3600)
def load_fpl_data(date: str) -> pl.DataFrame:
    """
    Load and join player history with metadata for a given date.

    Args:
        date: Date string in YYYY-MM-DD format

    Returns:
        Polars DataFrame with player history and metadata columns:
        - player_id, web_name, team, element_type
        - round, minutes, goals_scored, assists, total_points
        - expected_goals, expected_assists, expected_goal_involvements

    Raises:
        FileNotFoundError: If data files for the date don't exist
        Exception: For other data loading errors
    """
    # Define paths
    bootstrap_path = f"./data/bootstrap_static/date={date}/data.parquet"
    history_path = f"./data/player_history/date={date}/*.parquet"

    # Check if bootstrap file exists
    if not Path(bootstrap_path).exists():
        raise FileNotFoundError(f"Bootstrap data not found for date {date}")

    # Check if history directory exists
    history_dir = Path(f"./data/player_history/date={date}")
    if not history_dir.exists():
        raise FileNotFoundError(f"Player history directory not found for date {date}")

    try:
        # Load bootstrap static for player metadata
        bootstrap = pl.read_parquet(bootstrap_path)

        # Select relevant metadata columns
        metadata = bootstrap.select([
            pl.col("id").alias("player_id"),
            "web_name",
            "first_name",
            "second_name",
            "team",
            "element_type"
        ])

        # Load ALL player history files using glob pattern
        history = pl.read_parquet(history_path)

        # Join history with metadata
        # history.element corresponds to bootstrap.id (player_id)
        df = history.join(
            metadata,
            left_on="element",
            right_on="player_id",
            how="left"
        )

        # Select and order final columns
        result = df.select([
            "player_id",
            "web_name",
            "team",
            "element_type",
            "round",
            "minutes",
            "goals_scored",
            "assists",
            "total_points",
            "expected_goals",
            "expected_assists",
            "expected_goal_involvements",
            "opponent_team",
            "was_home",
            "kickoff_time"
        ])

        return result

    except Exception as e:
        raise Exception(f"Error loading data for {date}: {str(e)}")


def get_team_name(team_id: int) -> str:
    """
    Get team name from team ID.

    Args:
        team_id: Team ID (1-20)

    Returns:
        Team name string
    """
    TEAM_MAP = {
        1: "Arsenal",
        2: "Aston Villa",
        3: "Bournemouth",
        4: "Brentford",
        5: "Brighton",
        6: "Chelsea",
        7: "Crystal Palace",
        8: "Everton",
        9: "Fulham",
        10: "Ipswich",
        11: "Leicester",
        12: "Liverpool",
        13: "Man City",
        14: "Man Utd",
        15: "Newcastle",
        16: "Nott'm Forest",
        17: "Southampton",
        18: "Spurs",
        19: "West Ham",
        20: "Wolves"
    }
    return TEAM_MAP.get(team_id, f"Team {team_id}")


def get_position_name(element_type: int) -> str:
    """
    Get position name from element_type.

    Args:
        element_type: Position type (1=GK, 2=DEF, 3=MID, 4=FWD)

    Returns:
        Position name string
    """
    POSITION_MAP = {
        1: "GK",
        2: "DEF",
        3: "MID",
        4: "FWD"
    }
    return POSITION_MAP.get(element_type, "Unknown")

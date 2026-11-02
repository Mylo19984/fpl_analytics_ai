"""Load the latest stored data needed by the watchlist from Parquet"""

from pathlib import Path
from typing import Dict, Optional, Tuple
import polars as pl
from config import config
from src.storage.parquet_manager import ParquetManager


def load_latest_history() -> pl.DataFrame:
    """
    Load each player's history from the most recent partition containing them.

    Incremental fetches only write changed players into the newest date
    partition, so the latest partition alone is not complete.
    """
    paths: Dict[str, Path] = {}
    date_dirs = sorted(config.storage.player_history_path.glob("date=*"), reverse=True)
    for date_dir in date_dirs:
        for file_path in date_dir.glob("*.parquet"):
            paths.setdefault(file_path.stem, file_path)

    if not paths:
        return pl.DataFrame()
    return pl.concat([pl.read_parquet(p) for p in paths.values()], how="diagonal")


def load_watchlist_inputs() -> Optional[Tuple[str, pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]]:
    """
    Load (data_date, players, history, fixtures, teams) from the latest snapshot.

    Returns:
        None if any of the required data is missing
    """
    pm = ParquetManager()
    date = pm.get_latest_partition_date(config.storage.bootstrap_static_path)
    if date is None:
        return None

    players = pm.read_bootstrap_static(date)
    teams = pm.read_teams(date)
    fixtures_path = config.storage.fixtures_path / f"date={date}" / "data.parquet"
    history = load_latest_history()
    if players is None or teams is None or not fixtures_path.exists() or history.is_empty():
        return None

    return date, players, history, pl.read_parquet(fixtures_path), teams

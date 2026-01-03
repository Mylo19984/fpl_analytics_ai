from typing import Dict, Any
from datetime import datetime
import polars as pl
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


class DataProcessor:
    """
    Transforms API JSON responses into Polars DataFrames.
    """

    def process_player_history(self, player_id: int, raw_data: Dict[str, Any], fetch_date: str) -> pl.DataFrame:
        """
        Process player history data from API response.

        Args:
            player_id: Player ID
            raw_data: Raw JSON response from element-summary endpoint
            fetch_date: Date of fetch in YYYY-MM-DD format

        Returns:
            Polars DataFrame with player history
        """
        history = raw_data.get("history", [])

        if not history:
            logger.warning(f"Player {player_id} has no history data")
            return pl.DataFrame()

        try:
            # Convert to DataFrame
            df = pl.DataFrame(history)

            # Add metadata columns
            df = df.with_columns([
                pl.lit(player_id).alias("player_id"),
                pl.lit(fetch_date).alias("fetch_date")
            ])

            # Parse datetime columns if present
            if "kickoff_time" in df.columns:
                df = df.with_columns([
                    pl.col("kickoff_time").str.strptime(pl.Datetime, format="%Y-%m-%dT%H:%M:%SZ", strict=False)
                ])

            # Convert string numeric fields to proper types if needed
            numeric_fields = [
                "element", "fixture", "round", "total_points", "minutes",
                "goals_scored", "assists", "clean_sheets", "goals_conceded",
                "saves", "bonus", "bps", "value", "selected",
                "transfers_in", "transfers_out", "opponent_team"
            ]

            for field in numeric_fields:
                if field in df.columns:
                    # Ensure numeric type
                    df = df.with_columns([
                        pl.col(field).cast(pl.Int64, strict=False)
                    ])

            # Convert float fields
            float_fields = [
                "influence", "creativity", "threat", "ict_index",
                "expected_goals", "expected_assists", "expected_goal_involvements",
                "expected_goals_conceded"
            ]

            for field in float_fields:
                if field in df.columns:
                    df = df.with_columns([
                        pl.col(field).cast(pl.Float64, strict=False)
                    ])

            # Handle boolean fields
            if "was_home" in df.columns:
                df = df.with_columns([
                    pl.col("was_home").cast(pl.Boolean, strict=False)
                ])

            logger.debug(f"Processed {len(df)} history records for player {player_id}")
            return df

        except Exception as e:
            logger.error(f"Failed to process player {player_id} history: {str(e)}")
            raise

    def process_bootstrap_static(self, raw_data: Dict[str, Any], fetch_date: str) -> pl.DataFrame:
        """
        Process bootstrap-static data from API response.

        Args:
            raw_data: Raw JSON response from bootstrap-static endpoint
            fetch_date: Date of fetch in YYYY-MM-DD format

        Returns:
            Polars DataFrame with player data from 'elements' array
        """
        elements = raw_data.get("elements", [])

        if not elements:
            logger.error("No elements found in bootstrap-static data")
            raise ValueError("No elements in bootstrap-static response")

        try:
            # Convert to DataFrame
            df = pl.DataFrame(elements)

            # Add fetch date
            df = df.with_columns([
                pl.lit(fetch_date).alias("fetch_date")
            ])

            # Parse datetime columns if present
            datetime_fields = ["news_added"]
            for field in datetime_fields:
                if field in df.columns:
                    df = df.with_columns([
                        pl.col(field).str.strptime(pl.Datetime, format="%Y-%m-%dT%H:%M:%SZ", strict=False)
                    ])

            # Ensure numeric fields are proper types
            int_fields = [
                "id", "code", "element_type", "team", "now_cost",
                "total_points", "minutes", "goals_scored", "assists",
                "clean_sheets", "goals_conceded", "own_goals",
                "penalties_saved", "penalties_missed", "yellow_cards",
                "red_cards", "saves", "bonus", "bps", "transfers_in",
                "transfers_in_event", "transfers_out", "transfers_out_event",
                "cost_change_event", "cost_change_event_fall",
                "cost_change_start", "cost_change_start_fall",
                "dreamteam_count", "squad_number"
            ]

            for field in int_fields:
                if field in df.columns:
                    df = df.with_columns([
                        pl.col(field).cast(pl.Int64, strict=False)
                    ])

            # Float fields
            float_fields = [
                "form", "points_per_game", "selected_by_percent",
                "influence", "creativity", "threat", "ict_index",
                "expected_goals", "expected_assists", "expected_goal_involvements",
                "expected_goals_conceded", "value_form", "value_season"
            ]

            for field in float_fields:
                if field in df.columns:
                    df = df.with_columns([
                        pl.col(field).cast(pl.Float64, strict=False)
                    ])

            # Boolean fields
            bool_fields = [
                "can_transact", "can_select", "in_dreamteam",
                "removed", "special", "has_temporary_code"
            ]

            for field in bool_fields:
                if field in df.columns:
                    df = df.with_columns([
                        pl.col(field).cast(pl.Boolean, strict=False)
                    ])

            logger.info(f"Processed bootstrap-static data: {len(df)} players")
            return df

        except Exception as e:
            logger.error(f"Failed to process bootstrap-static data: {str(e)}")
            raise

    def extract_player_bootstrap_map(self, bootstrap_df: pl.DataFrame) -> Dict[int, Dict[str, Any]]:
        """
        Extract a mapping of player_id to their bootstrap data.

        Args:
            bootstrap_df: Bootstrap-static DataFrame

        Returns:
            Dictionary mapping player_id to bootstrap data dict
        """
        player_map = {}

        for row in bootstrap_df.iter_rows(named=True):
            player_id = row["id"]
            player_map[player_id] = row

        logger.debug(f"Created bootstrap map for {len(player_map)} players")
        return player_map

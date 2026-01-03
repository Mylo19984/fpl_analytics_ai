from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import polars as pl
from config import config
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


class FetchMetadataTracker:
    """
    Tracks fetch history to enable efficient incremental updates.
    """

    def __init__(self):
        self.metadata_path = config.storage.metadata_path
        self.metadata_file = self.metadata_path / "fetch_tracker.parquet"
        self._ensure_directory()

    def _ensure_directory(self):
        """Create metadata directory if it doesn't exist"""
        self.metadata_path.mkdir(parents=True, exist_ok=True)

    def _create_empty_metadata(self) -> pl.DataFrame:
        """Create empty metadata DataFrame with correct schema"""
        return pl.DataFrame({
            "player_id": pl.Series([], dtype=pl.Int64),
            "last_fetch_timestamp": pl.Series([], dtype=pl.Datetime),
            "last_total_points": pl.Series([], dtype=pl.Int64),
            "last_history_count": pl.Series([], dtype=pl.Int64),
            "latest_gameweek": pl.Series([], dtype=pl.Int64),
            "data_signature": pl.Series([], dtype=pl.Utf8),
            "fetch_status": pl.Series([], dtype=pl.Utf8),
            "error_message": pl.Series([], dtype=pl.Utf8)
        })

    def load_metadata(self) -> pl.DataFrame:
        """
        Load fetch metadata from parquet file.

        Returns:
            Polars DataFrame with metadata
        """
        if not self.metadata_file.exists():
            logger.info("No existing metadata found, creating new tracker")
            return self._create_empty_metadata()

        try:
            df = pl.read_parquet(self.metadata_file)
            logger.info(f"Loaded metadata for {len(df)} players")
            return df
        except Exception as e:
            logger.error(f"Failed to load metadata: {str(e)}")
            raise

    def save_metadata(self, df: pl.DataFrame):
        """
        Save metadata to parquet file.

        Args:
            df: Polars DataFrame with metadata
        """
        try:
            df.write_parquet(
                self.metadata_file,
                compression=config.storage.compression
            )
            logger.info(f"Saved metadata for {len(df)} players")
        except Exception as e:
            logger.error(f"Failed to save metadata: {str(e)}")
            raise

    def create_signature(self, total_points: int, history_count: int, latest_gameweek: int) -> str:
        """
        Create a data signature for change detection.

        Args:
            total_points: Player's total points
            history_count: Number of gameweek records
            latest_gameweek: Most recent gameweek played

        Returns:
            Signature string
        """
        return f"{total_points}_{history_count}_{latest_gameweek}"

    def get_players_to_fetch(
        self,
        all_player_ids: List[int],
        bootstrap_data: Dict[int, Dict[str, Any]]
    ) -> List[int]:
        """
        Determine which players need fetching based on metadata.

        Args:
            all_player_ids: List of all player IDs from bootstrap-static
            bootstrap_data: Dictionary mapping player_id to their bootstrap data

        Returns:
            List of player IDs that need fetching
        """
        metadata = self.load_metadata()

        if len(metadata) == 0:
            logger.info(f"First run: all {len(all_player_ids)} players need fetching")
            return all_player_ids

        players_to_fetch = []

        for player_id in all_player_ids:
            # Get player's bootstrap data
            player_data = bootstrap_data.get(player_id)
            if not player_data:
                logger.warning(f"Player {player_id} not found in bootstrap data")
                continue

            # Check if player has existing metadata
            player_metadata = metadata.filter(pl.col("player_id") == player_id)

            if len(player_metadata) == 0:
                # Never fetched before
                players_to_fetch.append(player_id)
                logger.debug(f"Player {player_id}: never fetched")
                continue

            # Get stored values
            stored_row = player_metadata.row(0, named=True)
            stored_signature = stored_row["data_signature"]
            fetch_status = stored_row["fetch_status"]

            # Retry failed fetches
            if fetch_status == "failed":
                players_to_fetch.append(player_id)
                logger.debug(f"Player {player_id}: retrying failed fetch")
                continue

            # Calculate current signature from bootstrap data
            total_points = player_data.get("total_points", 0)
            # Estimate history count from current event (assuming player has played most games)
            # We'll get exact count after fetching
            current_event = player_data.get("current_event", 0)
            latest_gameweek = current_event if current_event > 0 else 0

            # Use a simplified signature for comparison (just total points as proxy)
            # More accurate would require fetching, but that defeats incremental purpose
            current_signature = f"{total_points}_*_{latest_gameweek}"

            # Check if data has changed (simplified check)
            if not stored_signature.startswith(str(total_points)):
                players_to_fetch.append(player_id)
                logger.debug(f"Player {player_id}: data changed ({stored_signature} -> {current_signature})")

        logger.info(f"Players needing update: {len(players_to_fetch)} of {len(all_player_ids)}")
        return players_to_fetch

    def update_player_metadata(
        self,
        player_id: int,
        status: str,
        total_points: int = 0,
        history_count: int = 0,
        latest_gameweek: int = 0,
        error_message: str = ""
    ):
        """
        Update metadata for a single player.

        Args:
            player_id: Player ID
            status: Fetch status ('success' or 'failed')
            total_points: Player's total points
            history_count: Number of gameweek records
            latest_gameweek: Most recent gameweek played
            error_message: Error message if failed
        """
        metadata = self.load_metadata()

        # Create signature
        signature = self.create_signature(total_points, history_count, latest_gameweek)

        # Create or update player record
        new_record = pl.DataFrame({
            "player_id": [player_id],
            "last_fetch_timestamp": [datetime.now()],
            "last_total_points": [total_points],
            "last_history_count": [history_count],
            "latest_gameweek": [latest_gameweek],
            "data_signature": [signature],
            "fetch_status": [status],
            "error_message": [error_message]
        })

        # Remove existing record if present
        metadata = metadata.filter(pl.col("player_id") != player_id)

        # Append new record
        metadata = pl.concat([metadata, new_record])

        self.save_metadata(metadata)
        logger.debug(f"Updated metadata for player {player_id}: {status}")

    def get_fetch_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics from metadata.

        Returns:
            Dictionary with summary stats
        """
        metadata = self.load_metadata()

        if len(metadata) == 0:
            return {
                "total_players": 0,
                "successful_fetches": 0,
                "failed_fetches": 0,
                "last_fetch_time": None
            }

        successful = len(metadata.filter(pl.col("fetch_status") == "success"))
        failed = len(metadata.filter(pl.col("fetch_status") == "failed"))
        last_fetch = metadata["last_fetch_timestamp"].max()

        return {
            "total_players": len(metadata),
            "successful_fetches": successful,
            "failed_fetches": failed,
            "last_fetch_time": last_fetch
        }

from pathlib import Path
from typing import List, Optional
import polars as pl
from config import config
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


class ParquetManager:
    """
    Manages Parquet file I/O with Hive-style date partitioning.
    """

    def __init__(self):
        self.data_root = config.storage.data_root
        self.compression = config.storage.compression

    def _ensure_directory(self, path: Path):
        """Create directory if it doesn't exist"""
        path.mkdir(parents=True, exist_ok=True)

    def _get_partition_path(self, base_path: Path, date: str) -> Path:
        """Get Hive-style partition path: data/player_history/date=2026-01-02/"""
        return base_path / f"date={date}"

    def write_player_history(self, player_id: int, data: pl.DataFrame, date: str):
        """
        Write player history data to Hive-partitioned Parquet file.

        Args:
            player_id: Player ID
            data: Polars DataFrame with player history
            date: Date string in YYYY-MM-DD format
        """
        partition_path = self._get_partition_path(
            config.storage.player_history_path, date
        )
        self._ensure_directory(partition_path)

        file_path = partition_path / f"{player_id}.parquet"

        try:
            data.write_parquet(
                file_path,
                compression=self.compression
            )
            logger.debug(f"Wrote player {player_id} history to {file_path}")
        except Exception as e:
            logger.error(f"Failed to write player {player_id} history: {str(e)}")
            raise

    def read_player_history(self, player_id: int, date: str) -> Optional[pl.DataFrame]:
        """
        Read player history from Parquet file.

        Args:
            player_id: Player ID
            date: Date string in YYYY-MM-DD format

        Returns:
            Polars DataFrame or None if file doesn't exist
        """
        partition_path = self._get_partition_path(
            config.storage.player_history_path, date
        )
        file_path = partition_path / f"{player_id}.parquet"

        if not file_path.exists():
            logger.debug(f"Player {player_id} history not found for {date}")
            return None

        try:
            df = pl.read_parquet(file_path)
            logger.debug(f"Read player {player_id} history from {file_path}")
            return df
        except Exception as e:
            logger.error(f"Failed to read player {player_id} history: {str(e)}")
            raise

    def write_bootstrap_static(self, data: pl.DataFrame, date: str):
        """
        Write bootstrap-static data to Parquet file.

        Args:
            data: Polars DataFrame with bootstrap data
            date: Date string in YYYY-MM-DD format
        """
        partition_path = self._get_partition_path(
            config.storage.bootstrap_static_path, date
        )
        self._ensure_directory(partition_path)

        file_path = partition_path / "data.parquet"

        try:
            data.write_parquet(
                file_path,
                compression=self.compression
            )
            logger.info(f"Wrote bootstrap-static data to {file_path}")
        except Exception as e:
            logger.error(f"Failed to write bootstrap-static data: {str(e)}")
            raise

    def read_bootstrap_static(self, date: str) -> Optional[pl.DataFrame]:
        """
        Read bootstrap-static data from Parquet file.

        Args:
            date: Date string in YYYY-MM-DD format

        Returns:
            Polars DataFrame or None if file doesn't exist
        """
        partition_path = self._get_partition_path(
            config.storage.bootstrap_static_path, date
        )
        file_path = partition_path / "data.parquet"

        if not file_path.exists():
            logger.debug(f"Bootstrap-static data not found for {date}")
            return None

        try:
            df = pl.read_parquet(file_path)
            logger.info(f"Read bootstrap-static data from {file_path}")
            return df
        except Exception as e:
            logger.error(f"Failed to read bootstrap-static data: {str(e)}")
            raise

    def list_existing_player_files(self, date: str) -> List[int]:
        """
        List player IDs that have history files for a given date.

        Args:
            date: Date string in YYYY-MM-DD format

        Returns:
            List of player IDs
        """
        partition_path = self._get_partition_path(
            config.storage.player_history_path, date
        )

        if not partition_path.exists():
            return []

        player_ids = []
        for file_path in partition_path.glob("*.parquet"):
            try:
                player_id = int(file_path.stem)
                player_ids.append(player_id)
            except ValueError:
                logger.warning(f"Invalid player file name: {file_path.name}")
                continue

        logger.debug(f"Found {len(player_ids)} player files for {date}")
        return player_ids

    def get_latest_partition_date(self, base_path: Path) -> Optional[str]:
        """
        Get the most recent partition date.

        Args:
            base_path: Base path to search (e.g., player_history_path)

        Returns:
            Date string in YYYY-MM-DD format or None if no partitions exist
        """
        if not base_path.exists():
            return None

        # Find all date= directories
        date_dirs = [d for d in base_path.iterdir() if d.is_dir() and d.name.startswith("date=")]

        if not date_dirs:
            return None

        # Extract dates and sort
        dates = [d.name.replace("date=", "") for d in date_dirs]
        dates.sort(reverse=True)

        return dates[0] if dates else None

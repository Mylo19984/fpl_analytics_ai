from datetime import datetime
from typing import List, Dict, Any
import time
from src.api.client import FPLAPIClient
from src.storage.parquet_manager import ParquetManager
from src.storage.metadata_tracker import FetchMetadataTracker
from src.pipeline.processor import DataProcessor
from src.pipeline.scheduler import BatchScheduler
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


class FetchReport:
    """Summary report from pipeline execution"""

    def __init__(self):
        self.start_time = datetime.now()
        self.end_time = None
        self.bootstrap_fetched = False
        self.total_players = 0
        self.successful_fetches = 0
        self.failed_fetches = 0
        self.failed_player_ids = []
        self.skipped_players = 0

    def mark_complete(self):
        """Mark the report as complete"""
        self.end_time = datetime.now()

    def duration_seconds(self) -> float:
        """Get duration in seconds"""
        if not self.end_time:
            return (datetime.now() - self.start_time).total_seconds()
        return (self.end_time - self.start_time).total_seconds()

    def __str__(self) -> str:
        """String representation of the report"""
        lines = [
            f"\n{'='*60}",
            f"FPL Data Pipeline - Fetch Report",
            f"{'='*60}",
            f"Start time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duration: {self.duration_seconds():.1f} seconds",
            f"",
            f"Bootstrap-static: {'✓ Fetched' if self.bootstrap_fetched else '✗ Failed'}",
            f"Total players: {self.total_players}",
            f"Successful fetches: {self.successful_fetches}",
            f"Failed fetches: {self.failed_fetches}",
            f"Skipped (no changes): {self.skipped_players}",
        ]

        if self.failed_player_ids:
            lines.append(f"\nFailed player IDs: {self.failed_player_ids[:10]}")
            if len(self.failed_player_ids) > 10:
                lines.append(f"... and {len(self.failed_player_ids) - 10} more")

        lines.append(f"{'='*60}\n")
        return "\n".join(lines)


class DataFetcher:
    """
    Main pipeline orchestration class.
    """

    def __init__(self):
        self.api_client = FPLAPIClient()
        self.parquet_manager = ParquetManager()
        self.metadata_tracker = FetchMetadataTracker()
        self.processor = DataProcessor()
        self.scheduler = BatchScheduler()

    def run_full_pipeline(self, date: str = None, force_all: bool = False) -> FetchReport:
        """
        Run the complete data fetch pipeline.

        Args:
            date: Date string in YYYY-MM-DD format (defaults to today)
            force_all: If True, fetch all players regardless of changes

        Returns:
            FetchReport with summary statistics
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        report = FetchReport()

        logger.info(f"Starting FPL data pipeline for {date}")

        try:
            # Step 1: Fetch bootstrap-static
            logger.info("Step 1: Fetching bootstrap-static data")
            bootstrap_data = self.api_client.get_bootstrap_static()
            report.bootstrap_fetched = True

            # Process bootstrap data
            bootstrap_df = self.processor.process_bootstrap_static(bootstrap_data, date)
            self.parquet_manager.write_bootstrap_static(bootstrap_df, date)

            # Extract player map
            player_map = self.processor.extract_player_bootstrap_map(bootstrap_df)
            all_player_ids = list(player_map.keys())
            report.total_players = len(all_player_ids)

            logger.info(f"Found {len(all_player_ids)} players in bootstrap-static")

            # Step 2: Determine which players to fetch
            logger.info("Step 2: Determining players to fetch")

            if force_all:
                players_to_fetch = all_player_ids
                logger.info(f"Force mode: fetching all {len(players_to_fetch)} players")
            else:
                # Check for checkpoint
                checkpoint_players = self.scheduler.load_checkpoint()
                if checkpoint_players:
                    players_to_fetch = checkpoint_players
                    logger.info(f"Resuming from checkpoint: {len(players_to_fetch)} players")
                else:
                    # Incremental mode - only fetch changed players
                    players_to_fetch = self.metadata_tracker.get_players_to_fetch(
                        all_player_ids,
                        player_map
                    )

            report.skipped_players = report.total_players - len(players_to_fetch)

            if len(players_to_fetch) == 0:
                logger.info("No players need updating")
                report.mark_complete()
                return report

            # Step 3: Create batches
            logger.info(f"Step 3: Processing {len(players_to_fetch)} players in batches")
            batches = self.scheduler.create_batches(players_to_fetch)

            # Step 4: Process each batch
            for batch_idx, batch in enumerate(batches, 1):
                logger.info(f"Processing batch {batch_idx}/{len(batches)} ({len(batch)} players)")

                for player_id in batch:
                    try:
                        # Fetch player data
                        player_data = self.api_client.get_player_summary(player_id)

                        # Process to DataFrame
                        history_df = self.processor.process_player_history(
                            player_id,
                            player_data,
                            date
                        )

                        if len(history_df) == 0:
                            logger.warning(f"Player {player_id} has no history data, skipping")
                            continue

                        # Write to parquet
                        self.parquet_manager.write_player_history(player_id, history_df, date)

                        # Update metadata
                        bootstrap_info = player_map.get(player_id, {})
                        total_points = bootstrap_info.get("total_points", 0)
                        history_count = len(history_df)
                        latest_gw = history_df["round"].max() if len(history_df) > 0 else 0

                        self.metadata_tracker.update_player_metadata(
                            player_id=player_id,
                            status="success",
                            total_points=total_points,
                            history_count=history_count,
                            latest_gameweek=latest_gw
                        )

                        report.successful_fetches += 1

                    except Exception as e:
                        logger.error(f"Failed to fetch player {player_id}: {str(e)}")
                        report.failed_fetches += 1
                        report.failed_player_ids.append(player_id)

                        # Update metadata with failure
                        self.metadata_tracker.update_player_metadata(
                            player_id=player_id,
                            status="failed",
                            error_message=str(e)
                        )

                # Save checkpoint after each batch
                remaining_players = [
                    pid for batch in batches[batch_idx:]
                    for pid in batch
                ]
                if remaining_players:
                    self.scheduler.save_checkpoint(remaining_players)

                # Progress update
                progress = (batch_idx / len(batches)) * 100
                logger.info(f"Progress: {progress:.1f}% ({report.successful_fetches} successful, {report.failed_fetches} failed)")

            # Clear checkpoint on successful completion
            self.scheduler.clear_checkpoint()

            report.mark_complete()
            logger.info("Pipeline completed successfully")

            return report

        except Exception as e:
            logger.error(f"Pipeline failed: {str(e)}")
            report.mark_complete()
            raise

    def get_status(self) -> Dict[str, Any]:
        """
        Get current pipeline status.

        Returns:
            Dictionary with status information
        """
        summary = self.metadata_tracker.get_fetch_summary()

        # Check for checkpoint
        checkpoint_players = self.scheduler.load_checkpoint()

        # Get latest partition date
        latest_date = self.parquet_manager.get_latest_partition_date(
            self.parquet_manager.data_root / "player_history"
        )

        return {
            "last_fetch_time": summary["last_fetch_time"],
            "total_players_tracked": summary["total_players"],
            "successful_fetches": summary["successful_fetches"],
            "failed_fetches": summary["failed_fetches"],
            "latest_data_date": latest_date,
            "checkpoint_active": len(checkpoint_players) > 0,
            "checkpoint_remaining": len(checkpoint_players)
        }

    def close(self):
        """Cleanup resources"""
        self.api_client.close()

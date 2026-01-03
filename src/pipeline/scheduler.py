from typing import List
from pathlib import Path
import json
from config import config
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


class BatchScheduler:
    """
    Manages batch processing and checkpoint system.
    """

    def __init__(self):
        self.batch_size = config.pipeline.batch_size
        self.checkpoint_enabled = config.pipeline.checkpoint_enabled
        self.checkpoint_path = config.pipeline.checkpoint_path

    def create_batches(self, player_ids: List[int]) -> List[List[int]]:
        """
        Split player IDs into batches.

        Args:
            player_ids: List of player IDs to process

        Returns:
            List of batches, where each batch is a list of player IDs
        """
        batches = []
        for i in range(0, len(player_ids), self.batch_size):
            batch = player_ids[i:i + self.batch_size]
            batches.append(batch)

        logger.info(f"Created {len(batches)} batches from {len(player_ids)} players")
        return batches

    def save_checkpoint(self, remaining_players: List[int]):
        """
        Save checkpoint of remaining players to process.

        Args:
            remaining_players: List of player IDs not yet processed
        """
        if not self.checkpoint_enabled:
            return

        try:
            checkpoint_data = {
                "remaining_players": remaining_players,
                "count": len(remaining_players)
            }

            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.checkpoint_path, 'w') as f:
                json.dump(checkpoint_data, f)

            logger.info(f"Saved checkpoint: {len(remaining_players)} players remaining")

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {str(e)}")

    def load_checkpoint(self) -> List[int]:
        """
        Load checkpoint of remaining players to process.

        Returns:
            List of player IDs from checkpoint, or empty list if no checkpoint exists
        """
        if not self.checkpoint_enabled or not self.checkpoint_path.exists():
            return []

        try:
            with open(self.checkpoint_path, 'r') as f:
                checkpoint_data = json.load(f)

            remaining = checkpoint_data.get("remaining_players", [])
            logger.info(f"Loaded checkpoint: {len(remaining)} players to resume")
            return remaining

        except Exception as e:
            logger.error(f"Failed to load checkpoint: {str(e)}")
            return []

    def clear_checkpoint(self):
        """Clear checkpoint file after successful completion"""
        if self.checkpoint_path.exists():
            try:
                self.checkpoint_path.unlink()
                logger.info("Cleared checkpoint")
            except Exception as e:
                logger.warning(f"Failed to clear checkpoint: {str(e)}")

    def prioritize_players(self, player_ids: List[int], failed_players: List[int] = None) -> List[int]:
        """
        Prioritize player IDs for processing.
        Failed players are processed first, then the rest.

        Args:
            player_ids: List of all player IDs to process
            failed_players: List of player IDs that failed previously

        Returns:
            Prioritized list of player IDs
        """
        if not failed_players:
            return player_ids

        # Put failed players first
        failed_set = set(failed_players)
        priority_list = failed_players.copy()

        # Add remaining players
        for player_id in player_ids:
            if player_id not in failed_set:
                priority_list.append(player_id)

        logger.info(f"Prioritized {len(failed_players)} failed players first")
        return priority_list

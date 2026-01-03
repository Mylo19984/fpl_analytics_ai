import time
import requests
from typing import Dict, Any, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from config import config
from src.utils.logger import setup_logger
from src.api import endpoints


logger = setup_logger(__name__)


class FPLAPIClient:
    """
    HTTP client for FPL API with rate limiting and retry logic.
    """

    def __init__(self):
        self.base_url = config.api.base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.api.user_agent
        })
        self.last_request_time = 0
        self.rate_limit_delay = config.api.rate_limit_delay

    def _apply_rate_limit(self):
        """Apply rate limiting between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - elapsed
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout)),
        before_sleep=before_sleep_log(logger, logger.level)
    )
    def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic.

        Args:
            endpoint: API endpoint path
            params: Optional query parameters

        Returns:
            JSON response as dictionary

        Raises:
            requests.exceptions.RequestException: On request failures
        """
        self._apply_rate_limit()

        url = f"{self.base_url}{endpoint}"
        logger.debug(f"Requesting: {url}")

        try:
            response = self.session.get(
                url,
                params=params,
                timeout=config.api.request_timeout
            )

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                logger.warning(f"Rate limit hit (429). Waiting {retry_after}s")
                time.sleep(retry_after)
                raise requests.exceptions.RequestException("Rate limit exceeded")

            # Handle server errors (5xx)
            if 500 <= response.status_code < 600:
                logger.error(f"Server error {response.status_code}: {url}")
                raise requests.exceptions.RequestException(f"Server error: {response.status_code}")

            # Handle client errors (4xx) - don't retry these
            if 400 <= response.status_code < 500:
                logger.error(f"Client error {response.status_code}: {url}")
                response.raise_for_status()

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            logger.error(f"Request timeout: {url}")
            raise

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {url} - {str(e)}")
            raise

    def get_bootstrap_static(self) -> Dict[str, Any]:
        """
        Fetch bootstrap-static data containing all players, teams, and gameweek info.

        Returns:
            Dictionary with keys: 'elements', 'teams', 'events', etc.
        """
        logger.info("Fetching bootstrap-static data")
        try:
            data = self._request(endpoints.BOOTSTRAP_STATIC)
            player_count = len(data.get('elements', []))
            logger.info(f"Successfully fetched bootstrap-static ({player_count} players)")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch bootstrap-static: {str(e)}")
            raise

    def get_player_summary(self, player_id: int) -> Dict[str, Any]:
        """
        Fetch detailed history for a specific player.

        Args:
            player_id: Player ID

        Returns:
            Dictionary with keys: 'history', 'fixtures', 'history_past'
        """
        logger.debug(f"Fetching player {player_id} summary")
        try:
            endpoint = endpoints.get_player_summary_url(player_id)
            data = self._request(endpoint)
            history_count = len(data.get('history', []))
            logger.debug(f"Player {player_id}: {history_count} gameweek records")
            return data
        except requests.exceptions.RequestException as e:
            if "404" in str(e):
                logger.warning(f"Player {player_id} not found (404)")
            else:
                logger.error(f"Failed to fetch player {player_id}: {str(e)}")
            raise

    def close(self):
        """Close the session"""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

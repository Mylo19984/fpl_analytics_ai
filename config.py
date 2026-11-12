from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class APIConfig:
    """API configuration settings"""
    base_url: str = "https://fantasy.premierleague.com/api/"
    rate_limit_delay: float = 0.5  # seconds between requests
    request_timeout: int = 30  # seconds
    max_retries: int = 3
    user_agent: str = "FPL-Analytics-Pipeline/1.0"


@dataclass
class StorageConfig:
    """Storage configuration settings"""
    data_root: Path = Path("./data")
    compression: str = "snappy"
    parquet_version: str = "2.6"

    @property
    def player_history_path(self) -> Path:
        return self.data_root / "player_history"

    @property
    def bootstrap_static_path(self) -> Path:
        return self.data_root / "bootstrap_static"

    @property
    def teams_path(self) -> Path:
        return self.data_root / "teams"

    @property
    def fixtures_path(self) -> Path:
        return self.data_root / "fixtures"

    @property
    def metadata_path(self) -> Path:
        return self.data_root / "metadata"


@dataclass
class PipelineConfig:
    """Pipeline configuration settings"""
    batch_size: int = 50  # players per batch
    max_workers: int = 1  # sequential processing for rate limiting
    checkpoint_enabled: bool = True
    checkpoint_path: Path = Path("./data/.checkpoint")


@dataclass
class LoggingConfig:
    """Logging configuration settings"""
    log_dir: Path = Path("./logs")
    log_file: str = "pipeline.log"
    log_level_console: str = "INFO"
    log_level_file: str = "DEBUG"
    rotation_days: int = 7


@dataclass
class WatchlistConfig:
    """Watchlist scoring settings"""
    history_window: int = 5  # last N gameweeks used for form
    fixture_window: int = 5  # next N fixtures used for FDR (3 to 5)
    top_n: int = 7  # players shown per position
    min_starts: int = 3  # min starts within the history window
    reliable_minutes: int = 60  # minutes that count as a reliable appearance
    weight_points: float = 0.4
    weight_xg: float = 0.3
    weight_fixtures: float = 0.2
    weight_minutes: float = 0.1


@dataclass
class Config:
    """Main configuration container"""
    api: APIConfig = field(default_factory=APIConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    watchlist: WatchlistConfig = field(default_factory=WatchlistConfig)


# Global config instance
config = Config()

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
class Config:
    """Main configuration container"""
    api: APIConfig = field(default_factory=APIConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


# Global config instance
config = Config()

# FPL Analytics Data Pipeline

A robust data pipeline for fetching and storing Fantasy Premier League (FPL) player data in Hive-partitioned Parquet files with intelligent incremental updates.

## Features

- **Incremental Updates**: Smart change detection to only fetch updated player data
- **Hive-Style Partitioning**: Organized data storage by date for efficient querying
- **Rate Limiting**: Built-in API rate limiting to respect FPL API limits
- **Retry Logic**: Automatic retry with exponential backoff for failed requests
- **Checkpoint System**: Resume capability after interruptions
- **Comprehensive Logging**: Dual logging to console and file with rotation
- **Parquet Format**: Efficient columnar storage with Polars

## Project Structure

```
fpl_analytics/
├── main.py                          # CLI entry point
├── config.py                        # Configuration settings
├── requirements.txt                 # Python dependencies
├── src/
│   ├── api/
│   │   ├── client.py               # API client with rate limiting
│   │   └── endpoints.py            # API endpoint definitions
│   ├── storage/
│   │   ├── parquet_manager.py      # Parquet I/O operations
│   │   └── metadata_tracker.py     # Fetch tracking for incremental updates
│   ├── pipeline/
│   │   ├── fetcher.py              # Main pipeline orchestration
│   │   ├── processor.py            # Data transformation
│   │   └── scheduler.py            # Batch processing
│   └── utils/
│       └── logger.py               # Logging configuration
├── data/                           # Data storage (gitignored)
│   ├── player_history/
│   │   └── date=YYYY-MM-DD/
│   │       └── {player_id}.parquet
│   ├── bootstrap_static/
│   │   └── date=YYYY-MM-DD/
│   │       └── data.parquet
│   └── metadata/
│       └── fetch_tracker.parquet
└── logs/
    └── pipeline.log
```

## Installation

1. Clone the repository:
```bash
cd /Users/mylo/ai/fpl_analytics
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Fetch All Players (Initial Run)

For the first run or to force fetch all players:

```bash
python main.py fetch-all
```

This will:
- Fetch bootstrap-static data (all player info)
- Fetch individual player history for all ~600 players
- Store data in Hive-partitioned Parquet files
- Takes approximately 5-10 minutes due to rate limiting

### Incremental Update

For subsequent runs to only fetch changed data:

```bash
python main.py fetch-updates
```

This will:
- Check which players have new data
- Only fetch players with changes
- Much faster than full fetch

### Check Status

View pipeline status and statistics:

```bash
python main.py status
```

### Specify Custom Date

By default, data is stored with today's date. To specify a different date:

```bash
python main.py fetch-all --date 2026-01-15
python main.py fetch-updates --date 2026-01-15
```

## Configuration

Edit [config.py](config.py) to customize:

- **API Settings**: Rate limits, timeouts, retries
- **Storage Settings**: Data paths, compression settings
- **Pipeline Settings**: Batch size, checkpoint behavior
- **Logging Settings**: Log levels, rotation

Key configuration options:

```python
# API Configuration
rate_limit_delay = 0.5  # seconds between requests
request_timeout = 30     # seconds
max_retries = 3

# Pipeline Configuration
batch_size = 50          # players per batch
checkpoint_enabled = True
```

## Data Schema

### Player History (per gameweek)

Each player file contains their gameweek-by-gameweek performance:

```
player_id, fetch_date, element, fixture, round, total_points,
minutes, goals_scored, assists, clean_sheets, goals_conceded,
saves, bonus, bps, influence, creativity, threat, ict_index,
expected_goals, expected_assists, was_home, opponent_team, ...
```

### Bootstrap Static (all players)

Complete player information snapshot:

```
id, web_name, team, element_type, now_cost, total_points,
form, points_per_game, selected_by_percent, minutes,
goals_scored, assists, clean_sheets, influence, creativity,
threat, ict_index, expected_goals, expected_assists, ...
```

## Data Access

### Using Polars

```python
import polars as pl

# Read a specific player's history
df = pl.read_parquet("data/player_history/date=2026-01-02/123.parquet")
print(df)

# Read all players for a date (requires scanning all files)
df_all = pl.read_parquet("data/player_history/date=2026-01-02/*.parquet")

# Read bootstrap static
df_bootstrap = pl.read_parquet("data/bootstrap_static/date=2026-01-02/data.parquet")
```

### Using Pandas

```python
import pandas as pd

# Read player history
df = pd.read_parquet("data/player_history/date=2026-01-02/123.parquet")
```

## How It Works

### Incremental Update Strategy

1. **Fetch Bootstrap-Static**: Get current snapshot of all players
2. **Load Metadata**: Check what was fetched previously
3. **Compare Signatures**: Create signature from `total_points + history_count + latest_gameweek`
4. **Identify Changes**: Only fetch players with changed signatures
5. **Batch Processing**: Process in batches of 50 with rate limiting
6. **Update Metadata**: Track fetch status for next incremental run

### Rate Limiting

- 0.5 second delay between API requests
- Maximum ~120 requests per minute
- Full fetch of 600 players: ~5 minutes
- Exponential backoff on errors

### Error Handling

- **Network Errors**: Automatic retry with exponential backoff
- **Rate Limiting (429)**: Wait and retry with longer delay
- **Player Fetch Fails**: Log error, continue with next player
- **Checkpoint System**: Resume from last successful batch

## Logging

Logs are written to both console and file:

- **Console**: INFO level and above
- **File**: DEBUG level and above (logs/pipeline.log)
- **Rotation**: Daily rotation, keeps 7 days

View logs:
```bash
tail -f logs/pipeline.log
```

## API Endpoints

The pipeline uses the following FPL API endpoints:

- **bootstrap-static**: `https://fantasy.premierleague.com/api/bootstrap-static/`
  - All players, teams, gameweeks
- **element-summary**: `https://fantasy.premierleague.com/api/element-summary/{player_id}/`
  - Individual player history

## Performance

- **Initial Full Fetch**: ~5-10 minutes for all players
- **Incremental Update**: 1-3 minutes (only changed players)
- **Storage**: ~50MB per date partition (all players)
- **Compression**: Snappy compression for fast read/write

## Troubleshooting

### Pipeline Interrupted

If the pipeline is interrupted, it saves a checkpoint. Simply run the command again to resume:

```bash
python main.py fetch-updates  # Will resume from checkpoint
```

### Rate Limit Errors

If you encounter persistent rate limiting:
1. Check [config.py](config.py) and increase `rate_limit_delay`
2. Reduce `batch_size` to process fewer players at once

### Failed Players

Check the fetch report for failed player IDs. Failed players are automatically retried on the next run.

View metadata to see which players failed:
```python
import polars as pl
metadata = pl.read_parquet("data/metadata/fetch_tracker.parquet")
failed = metadata.filter(pl.col("fetch_status") == "failed")
print(failed)
```

## Example Output

```
============================================================
FPL Data Pipeline - Fetch Report
============================================================
Start time: 2026-01-02 14:30:00
Duration: 285.3 seconds

Bootstrap-static: ✓ Fetched
Total players: 607
Successful fetches: 605
Failed fetches: 2
Skipped (no changes): 0

Failed player IDs: [123, 456]
============================================================
```

## Development

### Adding New Features

The modular design makes it easy to extend:

- **New API endpoints**: Add to `src/api/endpoints.py`
- **Custom processing**: Modify `src/pipeline/processor.py`
- **Different storage**: Implement new manager in `src/storage/`

### Running in Production

For automated daily runs, set up a cron job:

```bash
# Run daily at 2 AM
0 2 * * * cd /path/to/fpl_analytics && python main.py fetch-updates
```

## License

MIT License - Feel free to use and modify

## Contributing

Contributions welcome! Please ensure:
- Code follows existing patterns
- Add logging for new operations
- Handle errors gracefully

## Data Source

All data is sourced from the official Fantasy Premier League API:
https://fantasy.premierleague.com/api/

Please be respectful of the API and don't modify rate limiting settings to be more aggressive.

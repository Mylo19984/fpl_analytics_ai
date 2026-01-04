import polars as pl

# Read entire Parquet file
df = pl.read_parquet("data/player_history/date=2026-01-02/1.parquet")

print(df)
print(df.shape)
print(df.columns)

# team


df_meta = pl.read_parquet("data/bootstrap_static/date=2026-01-02/data.parquet")
# data/bootstrap_static

print(df_meta)
print(f"team is: {df_meta['team'].unique()}")
print(df_meta.shape)
print(df_meta.columns)


df_log = pl.read_parquet("data/metadata/fetch_tracker.parquet")
# data/metadata

print(df_log)
print(df_log.shape)
print(df_log.columns)

df_teams = pl.read_parquet("data/teams/date=2026-01-04/data.parquet")

print(df_teams)
print(df_teams.shape)
print(df_teams.columns)

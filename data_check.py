import polars as pl

# Read entire Parquet file
df = pl.read_parquet("data/player_history/date=2026-01-02/1.parquet")

print(df)
print(df.shape)
print(df.columns)


df_meta = pl.read_parquet("data/bootstrap_static/date=2026-01-02/data.parquet")
# data/bootstrap_static

print(df_meta)
print(df_meta.shape)
print(df_meta.columns)


df_log = pl.read_parquet("data/metadata/fetch_tracker.parquet")
# data/metadata

print(df_log)
print(df_log.shape)
print(df_log.columns)
"""
Watchlist tab: top players per position to consider transferring in.
Always uses the latest stored snapshot (see DESIGN.md).
"""

import io
import sys
from pathlib import Path

# streamlit_app/ is on sys.path when run via `streamlit run`, the repo root is not
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import polars as pl
from src.watchlist.loader import load_watchlist_inputs
from src.watchlist.insights import generate_pros_cons
from src.watchlist.scoring import build_watchlist, next_gameweek, DEFENDER, MIDFIELDER, FORWARD

SECTIONS = [
    (DEFENDER, "🛡️ Defenders", "xGC/90"),
    (MIDFIELDER, "🎯 Midfielders", "xGI/90"),
    (FORWARD, "⚽ Forwards", "xGI/90"),
]


@st.cache_data(ttl=3600)
def _load_watchlist():
    inputs = load_watchlist_inputs()
    if inputs is None:
        return None
    date, players, history, fixtures, teams = inputs
    return date, next_gameweek(fixtures), build_watchlist(players, history, fixtures, teams)


@st.cache_data(ttl=3600, show_spinner="Generating AI pros & cons…")
def _pros_cons(section_json: str, xg_label: str) -> dict[str, dict[str, str]]:
    # JSON string is hashable (polars DataFrames are not) and serves as the cache key
    return generate_pros_cons(pl.read_json(io.StringIO(section_json)), xg_label)


def render_watchlist_tab():
    result = _load_watchlist()
    if result is None:
        st.warning("Watchlist data not available. Fetch data first (this also fetches fixtures):")
        st.code("python main.py fetch-updates")
        return

    date, next_gw, watchlist = result
    st.caption(f"Data as of {date} · Next gameweek: {next_gw if next_gw else 'n/a'}")

    for element_type, title, xg_label in SECTIONS:
        st.subheader(title)
        section = (
            watchlist.filter(pl.col("element_type") == element_type)
            .drop("element_type")
            .with_columns(pl.col("minutes_reliability") * 100)
        )
        try:
            notes = _pros_cons(section.write_json(row_oriented=True), xg_label)
        except Exception as e:
            notes = {}
            st.caption(f"AI pros/cons unavailable: {e}")
        section = section.with_columns(
            pl.col("web_name").map_elements(lambda n: notes.get(n, {}).get("pros", ""), return_dtype=pl.Utf8).alias("pros"),
            pl.col("web_name").map_elements(lambda n: notes.get(n, {}).get("cons", ""), return_dtype=pl.Utf8).alias("cons"),
        )
        st.dataframe(
            section.to_pandas(),
            hide_index=True,
            use_container_width=True,
            column_config={
                "web_name": "Player",
                "team": "Team",
                "price": st.column_config.NumberColumn("Price (£m)", format="%.1f"),
                "ownership": st.column_config.NumberColumn("Owned %", format="%.1f"),
                "score": st.column_config.NumberColumn("Score", format="%.1f"),
                "ppg": st.column_config.NumberColumn("Pts/game", format="%.1f"),
                "xg_p90": st.column_config.NumberColumn(xg_label, format="%.2f"),
                "avg_fdr": st.column_config.NumberColumn("Avg FDR", format="%.1f"),
                "minutes_reliability": st.column_config.NumberColumn("60+ min share", format="%.0f%%"),
                "pros": st.column_config.TextColumn("✅ AI pros", width="large"),
                "cons": st.column_config.TextColumn("❌ AI cons", width="large"),
            },
        )

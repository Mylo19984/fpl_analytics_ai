"""
FPL Analytics Streamlit Application
Main entry point for the web interface
"""

import streamlit as st
import polars as pl
from pathlib import Path
from data_loader import (
    get_available_dates,
    get_latest_date,
    load_fpl_data,
    get_team_name,
    get_position_name
)


# Position mapping for filtering
POSITION_MAP = {
    "GK": 1,
    "DEF": 2,
    "MID": 3,
    "FWD": 4
}


def apply_filters(
    df: pl.DataFrame,
    player_name: str,
    position: str,
    team: str,
    gw: int
) -> pl.DataFrame:
    """
    Apply user-selected filters to dataframe.

    Args:
        df: Input DataFrame
        player_name: Selected player name or "All"
        position: Selected position or "All"
        team: Selected team or "All"

    Returns:
        Filtered DataFrame
    """
    filtered = df

    # Player name filter
    if player_name != "All":
        filtered = filtered.filter(pl.col("web_name") == player_name)

    # Position filter
    if position != "All":
        pos_id = POSITION_MAP[position]
        filtered = filtered.filter(pl.col("element_type") == pos_id)

    # Team filter
    if team != "All":
        # Extract team ID from "Team Name" or "Team X" string
        if team.startswith("Team "):
            team_id = int(team.replace("Team ", ""))
        else:
            # Reverse lookup team name to ID
            team_map_reverse = {v: k for k, v in {
                1: "Arsenal", 2: "Aston Villa", 3: "Bournemouth", 4: "Brentford",
                5: "Brighton", 6: "Chelsea", 7: "Crystal Palace", 8: "Everton",
                9: "Fulham", 10: "Ipswich", 11: "Leicester", 12: "Liverpool",
                13: "Man City", 14: "Man Utd", 15: "Newcastle", 16: "Nott'm Forest",
                17: "Southampton", 18: "Spurs", 19: "West Ham", 20: "Wolves"
            }.items()}
            team_id = team_map_reverse.get(team, 0)

        if team_id > 0:
            filtered = filtered.filter(pl.col("team") == team_id)

    # GW name filter
    
    filtered = filtered.filter(pl.col("round").is_in(gw))

    return filtered


def render_overview_metrics(df: pl.DataFrame):
    """
    Display overview KPI metrics.

    Args:
        df: DataFrame to compute metrics from
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if len(df) > 0:
            total_gameweeks = df.select("round").max()[0, 0]
        else:
            total_gameweeks = 0
        st.metric("Total Gameweeks", total_gameweeks)

    with col2:
        if len(df) > 0:
            avg_minutes = df.select("minutes").mean()[0, 0]
            st.metric("Avg Minutes", f"{avg_minutes:.1f}")
        else:
            st.metric("Avg Minutes", "0.0")

    with col3:
        if len(df) > 0:
            max_points = df.select("total_points").max()[0, 0]
        else:
            max_points = 0
        st.metric("Highest GW Score", max_points)

    with col4:
        if len(df) > 0:
            total_goals = df.select("goals_scored").sum()[0, 0]
        else:
            total_goals = 0
        st.metric("Total Goals", total_goals)


def render_data_table(df: pl.DataFrame):
    """
    Render the main data table with formatted columns.

    Args:
        df: DataFrame to display
    """
    if len(df) == 0:
        st.warning("No data matches the selected filters.")
        return

    # Convert to pandas for display and format columns
    display_df = df.to_pandas()

    # Round expected stats to 2 decimals
    display_df['xG'] = display_df['expected_goals'].round(2)
    display_df['xA'] = display_df['expected_assists'].round(2)
    display_df['xGI'] = display_df['expected_goal_involvements'].round(2)

    # Select and rename columns for display
    display_df = display_df[[
        'round', 'web_name', 'minutes', 'goals_scored', 'assists',
        'total_points', 'xG', 'xA', 'xGI'
    ]]

    # Sort by gameweek and player name
    display_df = display_df.sort_values(['round', 'web_name'])

    # Display with Streamlit dataframe
    st.dataframe(
        display_df,
        use_container_width=True,
        height=600,
        column_config={
            "round": st.column_config.NumberColumn("GW", format="%d"),
            "web_name": st.column_config.TextColumn("Player", width="medium"),
            "minutes": st.column_config.NumberColumn("Mins", format="%d"),
            "goals_scored": st.column_config.NumberColumn("Goals", format="%d"),
            "assists": st.column_config.NumberColumn("Assists", format="%d"),
            "total_points": st.column_config.NumberColumn("Points", format="%d"),
            "xG": st.column_config.NumberColumn("xG", format="%.2f"),
            "xA": st.column_config.NumberColumn("xA", format="%.2f"),
            "xGI": st.column_config.NumberColumn("xGI", format="%.2f"),
        },
        hide_index=True
    )


def main():
    """Main Streamlit application"""

    # Page configuration
    st.set_page_config(
        page_title="FPL Analytics",
        page_icon="⚽",
        layout="wide"
    )

    # Check if data directory exists
    if not Path("./data").exists():
        st.error("Data directory not found. Run the pipeline first:")
        st.code("python main.py fetch-all")
        return

    # Get available dates
    available_dates = get_available_dates()

    if not available_dates:
        st.warning("No data available. Fetch data first:")
        st.code("python main.py fetch-all")
        return

    # Sidebar
    st.sidebar.title("⚽ FPL Analytics")

    # Date selector
    st.sidebar.subheader("📅 Data Date")
    selected_date = st.sidebar.selectbox(
        "Select Date",
        available_dates,
        index=0,
        label_visibility="collapsed"
    )

    # Load data
    try:
        with st.spinner(f"Loading data for {selected_date}..."):
            df = load_fpl_data(selected_date)
    except FileNotFoundError as e:
        st.error(f"Data not found: {str(e)}")
        return
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        st.exception(e)
        return

    # Sidebar filters
    st.sidebar.subheader("🔍 Filters")

    # Player name filter
    unique_players = df.select("web_name").unique().sort("web_name")
    player_options = ["All"] + unique_players["web_name"].to_list()
    player_name = st.sidebar.selectbox("Player", player_options)

    # Position filter
    position_options = ["All", "GK", "DEF", "MID", "FWD"]
    position = st.sidebar.selectbox("Position", position_options)

    # Team filter
    unique_teams = df.select("team").unique().sort("team")
    team_names = ["All"] + [get_team_name(t) for t in unique_teams["team"].to_list()]
    team = st.sidebar.selectbox("Team", team_names)

    # GW filter, updated to mulyieselect
    unique_gw = df.select("round").unique().sort("round")
    gw_names = unique_gw["round"].to_list()
    #gw = st.sidebar.selectbox("GW", gw_names)
    gw = st.sidebar.multiselect("GW", options=gw_names, default=gw_names[-3:])

    # Apply filters
    filtered_df = apply_filters(df, player_name, position, team, gw)

    # Display record count in sidebar
    st.sidebar.metric("Records", f"{len(filtered_df):,}")

    # Main area
    st.title("📊 FPL Player Analytics")

    # Overview metrics
    render_overview_metrics(filtered_df)

    st.markdown("---")

    # Data table
    st.subheader(f"Player Performance by Gameweek")
    render_data_table(filtered_df)

    # Download button
    if len(filtered_df) > 0:
        csv = filtered_df.to_pandas().to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"fpl_data_{selected_date}.csv",
            mime="text/csv"
        )


if __name__ == "__main__":
    main()

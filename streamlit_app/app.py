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
            filtered = filtered.filter(pl.col("short_name") == team)

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


def aggregate_by_player(df: pl.DataFrame) -> pl.DataFrame:
    """
    Aggregate player data by player, calculating totals and averages.

    Args:
        df: DataFrame with player gameweek data

    Returns:
        Aggregated DataFrame grouped by player
    """
    if len(df) == 0:
        return df

    aggregated = df.group_by(["web_name", "team", "element_type"]).agg([
        pl.col("round").count().alias("gameweeks"),
        pl.col("minutes").sum().alias("total_minutes"),
        pl.col("minutes").mean().alias("avg_minutes"),
        pl.col("goals_scored").sum().alias("total_goals"),
        pl.col("goals_scored").mean().alias("avg_goals"),
        pl.col("assists").sum().alias("total_assists"),
        pl.col("assists").mean().alias("avg_assists"),
        pl.col("total_points").sum().alias("total_points"),
        pl.col("total_points").mean().alias("avg_points"),
        pl.col("expected_goals").sum().alias("total_xG"),
        pl.col("expected_goals").mean().alias("avg_xG"),
        pl.col("expected_assists").sum().alias("total_xA"),
        pl.col("expected_assists").mean().alias("avg_xA"),
        pl.col("expected_goal_involvements").sum().alias("total_xGI"),
        pl.col("expected_goal_involvements").mean().alias("avg_xGI"),
    ])

    return aggregated


def aggregate_performance_metrics(
    filtered_df: pl.DataFrame,
    unfiltered_df: pl.DataFrame
) -> pl.DataFrame:
    """
    Aggregate performance metrics by player with focus on consistency and point averages.

    Args:
        filtered_df: DataFrame with GW filter applied (for last 6/10 calculations)
        unfiltered_df: Full season data (for season-wide calculations)

    Returns:
        Aggregated DataFrame with performance metrics per player
    """
    if len(filtered_df) == 0:
        return filtered_df

    # Process each player separately to calculate "last N gameweeks" metrics
    players = []

    for player_name in filtered_df.select("web_name").unique()["web_name"]:
        player_df = filtered_df.filter(pl.col("web_name") == player_name)

        # Sort by round to get chronological order
        player_df = player_df.sort("round")

        # Get player metadata (from first row)
        team = player_df["short_name"][0]
        element_type = player_df["element_type"][0]

        # Total and average points
        total_points = player_df["total_points"].sum()
        avg_points = player_df["total_points"].mean()

        # Average points for games >55 minutes
        games_55min = player_df.filter(pl.col("minutes") > 55)
        if len(games_55min) > 0:
            avg_points_55min = games_55min["total_points"].mean()
        else:
            avg_points_55min = None

        # Get last 6 and 10 gameweeks
        last_6 = player_df.tail(6)
        last_10 = player_df.tail(10)

        # Count games >6 and >10 points
        games_6pts_last6 = len(last_6.filter(pl.col("total_points") > 6))
        games_10pts_last6 = len(last_6.filter(pl.col("total_points") > 10))
        games_6pts_last10 = len(last_10.filter(pl.col("total_points") > 6))
        games_10pts_last10 = len(last_10.filter(pl.col("total_points") > 10))

        # Season-wide metrics from unfiltered data
        player_season = unfiltered_df.filter(pl.col("web_name") == player_name)
        games_6pts_season = len(player_season.filter(pl.col("total_points") > 6))

        players.append({
            "web_name": player_name,
            "team": team,
            "element_type": element_type,
            "total_points": total_points,
            "avg_points": avg_points,
            "avg_points_55min": avg_points_55min,
            "games_6pts_last6": games_6pts_last6,
            "games_10pts_last6": games_10pts_last6,
            "games_6pts_last10": games_6pts_last10,
            "games_10pts_last10": games_10pts_last10,
            "games_6pts_season": games_6pts_season,
        })

    # Convert to Polars DataFrame
    result = pl.DataFrame(players)

    return result


def render_player_summary(df: pl.DataFrame):
    """
    Render player summary table with totals and averages.

    Args:
        df: Aggregated DataFrame grouped by player
    """
    if len(df) == 0:
        st.warning("No data matches the selected filters.")
        return

    # Convert to pandas for display
    display_df = df.to_pandas()

    # Add team and position names
    display_df['Team'] = display_df['team']
    display_df['Position'] = display_df['element_type'].apply(get_position_name)

    # Select and order columns for display
    display_df = display_df[[
        'web_name', 'Team', 'Position', 'gameweeks',
        'total_minutes', 'avg_minutes',
        'total_goals', 'avg_goals',
        'total_assists', 'avg_assists',
        'total_points', 'avg_points',
        'total_xG', 'avg_xG',
        'total_xA', 'avg_xA',
        'total_xGI', 'avg_xGI'
    ]]

    # Sort by total points descending
    display_df = display_df.sort_values('total_points', ascending=False)

    # Display with Streamlit dataframe
    st.dataframe(
        display_df,
        use_container_width=True,
        height=600,
        column_config={
            "web_name": st.column_config.TextColumn("Player", width="medium"),
            "Team": st.column_config.TextColumn("Team", width="small"),
            "Position": st.column_config.TextColumn("Pos", width="small"),
            "gameweeks": st.column_config.NumberColumn("GWs", format="%d"),
            "total_minutes": st.column_config.NumberColumn("Total Mins", format="%d"),
            "avg_minutes": st.column_config.NumberColumn("Avg Mins", format="%.1f"),
            "total_goals": st.column_config.NumberColumn("Total Goals", format="%d"),
            "avg_goals": st.column_config.NumberColumn("Avg Goals", format="%.2f"),
            "total_assists": st.column_config.NumberColumn("Total Assists", format="%d"),
            "avg_assists": st.column_config.NumberColumn("Avg Assists", format="%.2f"),
            "total_points": st.column_config.NumberColumn("Total Pts", format="%d"),
            "avg_points": st.column_config.NumberColumn("Avg Pts", format="%.2f"),
            "total_xG": st.column_config.NumberColumn("Total xG", format="%.2f"),
            "avg_xG": st.column_config.NumberColumn("Avg xG", format="%.2f"),
            "total_xA": st.column_config.NumberColumn("Total xA", format="%.2f"),
            "avg_xA": st.column_config.NumberColumn("Avg xA", format="%.2f"),
            "total_xGI": st.column_config.NumberColumn("Total xGI", format="%.2f"),
            "avg_xGI": st.column_config.NumberColumn("Avg xGI", format="%.2f"),
        },
        hide_index=True
    )


def render_performance_metrics(df: pl.DataFrame):
    """
    Render performance metrics table with consistency and point average stats.

    Args:
        df: Aggregated DataFrame with performance metrics
    """
    if len(df) == 0:
        st.warning("No data matches the selected filters.")
        return

    # Convert to pandas for display
    display_df = df.to_pandas()

    # Add team and position names
    display_df['Team'] = display_df['team']
    display_df['Position'] = display_df['element_type'].apply(get_position_name)

    # Select and order columns for display
    display_df = display_df[[
        'web_name', 'Team', 'Position',
        'total_points', 'avg_points', 'avg_points_55min',
        'games_6pts_last6', 'games_6pts_last10', 'games_6pts_season',
        'games_10pts_last6', 'games_10pts_last10'
    ]]

    # Sort by games >6pts in last 6 GW descending, then total points
    display_df = display_df.sort_values(
        ['games_6pts_last6', 'total_points'],
        ascending=[False, False]
    )

    # Display with Streamlit dataframe
    st.dataframe(
        display_df,
        use_container_width=True,
        height=600,
        column_config={
            "web_name": st.column_config.TextColumn("Player", width="medium"),
            "Team": st.column_config.TextColumn("Team", width="small"),
            "Position": st.column_config.TextColumn("Pos", width="small"),
            "total_points": st.column_config.NumberColumn("Total Pts", format="%d"),
            "avg_points": st.column_config.NumberColumn("Avg Pts", format="%.2f"),
            "avg_points_55min": st.column_config.NumberColumn("Avg Pts (>55m)", format="%.2f"),
            "games_6pts_last6": st.column_config.NumberColumn(">6pts (L6)", format="%d"),
            "games_6pts_last10": st.column_config.NumberColumn(">6pts (L10)", format="%d"),
            "games_6pts_season": st.column_config.NumberColumn(">6pts (Season)", format="%d"),
            "games_10pts_last6": st.column_config.NumberColumn(">10pts (L6)", format="%d"),
            "games_10pts_last10": st.column_config.NumberColumn(">10pts (L10)", format="%d"),
        },
        hide_index=True
    )


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
            # Store unfiltered copy for season metrics
            df_unfiltered = load_fpl_data(selected_date)
            df = df_unfiltered  # Base for filtering
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
    #unique_teams = df.select("team").unique().sort("team")
    #team_names = ["All"] + [get_team_name(t) for t in unique_teams["team"].to_list()]
    #team = st.sidebar.selectbox("Team", team_names)

    # Team 2nd filter
    unique_teams = df.select("short_name").unique().sort("short_name")
    team_names = ["All"] + [t for t in unique_teams["short_name"].to_list()]
    team = st.sidebar.selectbox("Team", team_names)

    # GW filter, updated to mulyieselect
    unique_gw = df.select("round").unique().sort("round")
    gw_names = unique_gw["round"].to_list()
    #gw = st.sidebar.selectbox("GW", gw_names)
    gw = st.sidebar.multiselect("GW", options=gw_names, default=gw_names[-3:])

    # Apply filters
    filtered_df = apply_filters(df, player_name, position, team, gw)

    # Create unfiltered version (only player/position/team filters, no GW filter)
    # This is for season-wide metrics
    all_gws = df_unfiltered.select("round").unique()["round"].to_list()
    unfiltered_with_filters = apply_filters(
        df_unfiltered, player_name, position, team, all_gws
    )

    # Display record count in sidebar
    st.sidebar.metric("Records", f"{len(filtered_df):,}")

    # Main area
    st.title("📊 FPL Player Analytics")

    # Overview metrics
    render_overview_metrics(filtered_df)

    st.markdown("---")

    # Create tabs for different views
    tab1, tab2, tab3 = st.tabs([
        "📅 By Gameweek",
        "👤 Player Summary",
        "📈 Performance Metrics"
    ])

    with tab1:
        st.subheader(f"Player Performance by Gameweek")
        render_data_table(filtered_df)

        # Download button
        if len(filtered_df) > 0:
            csv = filtered_df.to_pandas().to_csv(index=False)
            st.download_button(
                label="📥 Download Gameweek Data CSV",
                data=csv,
                file_name=f"fpl_gameweek_data_{selected_date}.csv",
                mime="text/csv"
            )

    with tab2:
        st.subheader(f"Player Summary (Totals & Averages)")

        # Aggregate data by player
        player_summary = aggregate_by_player(filtered_df)
        render_player_summary(player_summary)

        # Download button for aggregated data
        if len(player_summary) > 0:
            csv = player_summary.to_pandas().to_csv(index=False)
            st.download_button(
                label="📥 Download Player Summary CSV",
                data=csv,
                file_name=f"fpl_player_summary_{selected_date}.csv",
                mime="text/csv"
            )

    with tab3:
        st.subheader("Performance Metrics")

        # Calculate performance metrics
        performance_metrics = aggregate_performance_metrics(
            unfiltered_with_filters,
            #filtered_df,
            unfiltered_with_filters
        )

        # Render table
        render_performance_metrics(performance_metrics)

        # Download button
        if len(performance_metrics) > 0:
            csv = performance_metrics.to_pandas().to_csv(index=False)
            st.download_button(
                label="📥 Download Performance Metrics CSV",
                data=csv,
                file_name=f"fpl_performance_metrics_{selected_date}.csv",
                mime="text/csv"
            )


if __name__ == "__main__":
    main()

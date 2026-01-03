"""FPL API endpoint definitions"""

BOOTSTRAP_STATIC = "bootstrap-static/"
PLAYER_SUMMARY = "element-summary/{player_id}/"


def get_player_summary_url(player_id: int) -> str:
    """Get the URL for a specific player's summary endpoint"""
    return PLAYER_SUMMARY.format(player_id=player_id)

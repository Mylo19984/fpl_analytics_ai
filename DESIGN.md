# FPL Watchlist MVP: Design

Base repo: https://github.com/Mylo19984/fpl_analytics_ai

## Goal

A "Watchlist" tab in the existing Streamlit app. It suggests the 7 best players per position to consider transferring in before the next deadline.

## Scope

- DEF, MID and FWD only, 7 players each. No goalkeepers.
- A general list, not tied to your squad. No price cap or controls.
- The same for everyone, and read-only.

## Data (existing repo, reusing the Parquet storage)

- Uses existing data: `bootstrap-static` (price, ownership, status, xG/xA/xGC, team) and player history for the last 5 gameweeks.
- **One new fetch:** the FPL `fixtures/` endpoint, added to the API client and stored as Parquet by date. It gives each team's next 5 fixtures with their FDR. The window is a constant in `config.py` (`FIXTURE_WINDOW`, 3 to 5, default 5).
- Refresh is manual: `python main.py fetch-updates`.
- The tab always uses the latest snapshot and ignores the date selector. It shows "data as of <date>" and the next gameweek number.

## Exclusions

- Anyone whose FPL `status` is not "a" (injured, suspended, unavailable, doubtful).
- Anyone with fewer than 3 starts in the last 5 gameweeks (rotation players, new signings).

## Score (per position, no ML)

| Component | Weight |
|---|---|
| Points per game, last 5 gameweeks | 40% |
| xGI per 90 for MID and FWD, or xGC per 90 for DEF (inverted) | 30% |
| Average FDR of the next `FIXTURE_WINDOW` (3-5) fixtures (inverted) | 20% |
| Minutes reliability (share of the last 5 gameweeks with 60+ minutes) | 10% |

- Each component is normalised within its position.
- Weights are constants in `config.py`.

## UI

- Three stacked tables: Defenders, Midfielders, Forwards.
- Columns: name, team, price, ownership %, score, and the four components, so the ranking is explainable.

## Code layout

- New `src/watchlist/` module with pure scoring and filtering functions (Polars frames in, Polars frame out).
- The Streamlit tab only calls that module and renders the result.

## Testing

- A small pytest suite for the scoring and exclusion logic on a hand-made Polars frame.
- No tests for the UI or the API.

## Out of scope (phase 2 or later)

- Linking your squad or team ID
- Goalkeepers
- A price cap or sliders
- A manual add/remove watchlist
- Saved history of past watchlists
- Alerts or automation
- An LLM rationale
- Any ML prediction

## Explicitly ignored in the MVP

- Start of season (fewer than 5 gameweeks played): no special handling.
- Double and blank gameweeks: no special handling. The next fixtures per team are used as listed.

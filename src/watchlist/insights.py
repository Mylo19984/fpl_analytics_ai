"""GenAI pros/cons for watchlist players (one batched Claude call per position)."""

import json
import os

import polars as pl

MODEL = "claude-haiku-5-5"
STATS = ["web_name", "team", "price", "ownership", "score", "ppg", "xg_p90", "avg_fdr", "minutes_reliability"]


def generate_pros_cons(section: pl.DataFrame, xg_label: str) -> dict[str, dict[str, str]]:
    """Return {web_name: {'pros': ..., 'cons': ...}}. Raises if no API key or the call fails."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    import anthropic

    rows = section.select([c for c in STATS if c in section.columns]).to_dicts()
    prompt = (
        "You are an FPL (Fantasy Premier League) analyst. For each player below, give concise "
        "pros and cons for transferring them in, based ONLY on the stats given "
        f"(xG metric is {xg_label}; avg_fdr = upcoming fixture difficulty, lower is easier; "
        "minutes_reliability = share of recent games with 60+ minutes). Max ~25 words per side.\n\n"
        f"{json.dumps(rows)}\n\n"
        'Reply with ONLY a JSON object: {"<web_name>": {"pros": "...", "cons": "..."}, ...}'
    )
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL, max_tokens=2000, messages=[{"role": "user", "content": prompt}]
    )
    # The model may emit thinking blocks first; only join the text blocks
    text = "".join(b.text for b in msg.content if b.type == "text")
    data = json.loads(text[text.index("{"): text.rindex("}") + 1])
    return {
        name: {"pros": v.get("pros", ""), "cons": v.get("cons", "")} for name, v in data.items()
    }

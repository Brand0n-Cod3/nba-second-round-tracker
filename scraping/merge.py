"""Merge draft picks with scraped career stats into one per-player dataset.

Reads:
    data/processed/draft_picks.csv     (from scrape_draft.py)
    data/processed/career_seasons.csv  (from scrape_careers.py)

Writes:
    data/exports/players.json          (one object per player)
    dashboard/data.js                  (same data as a JS const the dashboard loads)

For each drafted player we compute career aggregates (games, seasons, total and
peak Win Shares, peak BPM, games-weighted per-game averages) plus a per-season
Win Share "arc" for the dashboard sparklines, then assign an outcome tier.
"""

import os
import sys
import json

import pandas as pd

# Make tier_classifier (in ../analysis) importable.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "analysis"))
from tier_classifier import assign_tier

PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
EXPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "exports")
DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "..", "dashboard")


def to_float(x):
    """Parse a stat cell to float, tolerating blanks and '.645'-style values."""
    try:
        if x is None or x == "" or (isinstance(x, float) and pd.isna(x)):
            return None
        return float(x)
    except (ValueError, TypeError):
        return None

US_AND_TERRITORY_CODES = {
    "US",  # United States
    "PR",  # Puerto Rico
    "VI",  # U.S. Virgin Islands
    "GU",  # Guam
    "AS",  # American Samoa
    "MP",  # Northern Mariana Islands
}


def is_international(country_code):
    """True if born outside the U.S. and its territories.

    Blank/unknown (empty string or NaN) defaults to domestic so players with no
    parsed birthplace don't inflate the international count — noted as a
    limitation.
    """
    if not country_code or (isinstance(country_code, float) and pd.isna(country_code)):
        return False
    return country_code not in US_AND_TERRITORY_CODES


def band(pick):
    if pick <= 40:
        return "31-40"
    if pick <= 50:
        return "41-50"
    return "51-60"


def era(year):
    if year >= 2020:
        return "2020s"
    if year >= 2010:
        return "2010s"
    return "2000s"


def build_player(draft_row, seasons):
    """Combine one player's draft info + season rows into a summary dict."""
    # Keep only rows with real games played (drops 'Did not play' rows).
    played = [s for s in seasons if to_float(s.get("gp")) not in (None, 0)]

    birth_country = next(
        (s["birth_country"] for s in seasons if s.get("birth_country")), ""
    )

    ws_by_season = [to_float(s["ws"]) or 0 for s in played]
    career_gp = sum(to_float(s["gp"]) or 0 for s in played)
    career_ws = sum(ws_by_season)
    peak_ws = max(ws_by_season) if ws_by_season else 0
    bpms = [to_float(s["bpm"]) for s in played if to_float(s["bpm"]) is not None]
    peak_bpm = max(bpms) if bpms else 0
    vorp = sum(to_float(s["vorp"]) or 0 for s in played)
    seasons_played = len(played)

    def wavg(field):
        """Games-weighted career average of a per-game stat."""
        num = den = 0.0
        for s in played:
            v = to_float(s[field])
            g = to_float(s["gp"])
            if v is not None and g:
                num += v * g
                den += g
        return round(num / den, 1) if den else 0

    tier = assign_tier(
        {"career_gp": career_gp, "career_ws": career_ws, "peak_ws": peak_ws}
    )

    pick = int(draft_row["overall_pick"])
    year = int(draft_row["draft_year"])

    return {
        "name": draft_row["player"],
        "slug": draft_row["slug"],
        "pick": pick,
        "year": year,
        "team": draft_row["team"],
        "birth_country": birth_country,
        "international": is_international(birth_country),
        "band": band(pick),
        "era": era(year),
        "gp": int(career_gp),
        "seasons": seasons_played,
        "pts": wavg("pts"),
        "reb": wavg("reb"),
        "ast": wavg("ast"),
        "bpm": round(peak_bpm, 1),
        "vorp": round(vorp, 1),
        "ws": round(career_ws, 1),
        "peak_ws": round(peak_ws, 1),
        "tier": tier,
        "arc": [round(w, 1) for w in ws_by_season],
    }


def main():
    draft = pd.read_csv(os.path.join(PROCESSED_DIR, "draft_picks.csv"), encoding="utf-8")
    careers = pd.read_csv(os.path.join(PROCESSED_DIR, "career_seasons.csv"), encoding="utf-8")

    seasons_by_slug = {}
    for _, row in careers.iterrows():
        seasons_by_slug.setdefault(row["slug"], []).append(row.to_dict())

    players = [
        build_player(draft_row, seasons_by_slug.get(draft_row["slug"], []))
        for _, draft_row in draft.iterrows()
    ]

    # Best outcomes first.
    players.sort(key=lambda p: p["ws"], reverse=True)

    os.makedirs(EXPORTS_DIR, exist_ok=True)
    json_path = os.path.join(EXPORTS_DIR, "players.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(players)} players -> {json_path}")

    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    js_path = os.path.join(DASHBOARD_DIR, "data.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("// Auto-generated by scraping/merge.py — do not edit by hand.\n")
        f.write("const players = ")
        json.dump(players, f, indent=2, ensure_ascii=False)
        f.write(";\n")
    print(f"Wrote dashboard data -> {js_path}")


if __name__ == "__main__":
    main()
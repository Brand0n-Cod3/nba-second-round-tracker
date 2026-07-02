"""Scrape per-season career stats for a list of players.

Reads the draft CSV produced by scrape_draft.py, then for each player with a
Basketball Reference slug, pulls two tables:
  - per_game : points, rebounds, assists, steals, blocks, games played
  - advanced : PER, TS%, WS, WS/48, BPM, VORP, USG%

Basketball Reference embeds the advanced table inside an HTML comment, so we
un-comment before parsing. Players who never appeared in an NBA game have no
tables — we record them with zero games so the "never played" tier is
represented rather than silently dropped.

Usage:
    python scraping/scrape_careers.py                 # all players in draft CSV
    python scraping/scrape_careers.py --year 2014      # just one class
    python scraping/scrape_careers.py --limit 5        # first 5 (for testing)
"""

import argparse
import os
import time
import csv

import requests
from bs4 import BeautifulSoup, Comment

import re

SEASON_RE = re.compile(r"^\d{4}(-\d{2})?$")

PLAYER_URL = "https://www.basketball-reference.com/players/{initial}/{slug}.html"
RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")

REQUEST_DELAY_SECONDS = 3.5

HEADERS = {
    "User-Agent": (
        "nba-second-round-tracker/1.0 (personal analytics project; "
        "contact: your-email@example.com)"
    )
}

# Columns we keep from each table, mapped to friendlier names.
PER_GAME_FIELDS = {
    "year_id": "season",
    "age": "age",
    "team_name_abbr": "team",
    "games": "gp",
    "mp_per_g": "mpg",
    "pts_per_g": "pts",
    "trb_per_g": "reb",
    "ast_per_g": "ast",
    "stl_per_g": "stl",
    "blk_per_g": "blk",
}

ADVANCED_FIELDS = {
    "year_id": "season",
    "per": "per",
    "ts_pct": "ts_pct",
    "usg_pct": "usg_pct",
    "ws": "ws",
    "ws_per_48": "ws_per_48",
    "bpm": "bpm",
    "vorp": "vorp",
}


def fetch_page(url, cache_path):
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()

    print(f"  fetching {url}")
    response = requests.get(url, headers=HEADERS, timeout=30)
    if response.status_code == 404:
        return None  # No page for this player.
    response.raise_for_status()
    response.encoding = "utf-8"
    time.sleep(REQUEST_DELAY_SECONDS)

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(response.text)
    return response.text


def find_table(soup, table_id):
    """Locate a table by id, checking HTML comments too.

    BBRef hides the advanced table (and several others) inside comments. We
    search live markup first, then fall back to comment contents.
    """
    table = soup.find("table", id=table_id)
    if table is not None:
        return table

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        if f'id="{table_id}"' in comment:
            return BeautifulSoup(comment, "lxml").find("table", id=table_id)
    return None


def parse_stat_table(table, field_map, season_key="year_id"):
    """Return {season: {mapped_field: value}} for regular-season rows only."""
    if table is None:
        return {}
    tbody = table.find("tbody")
    if tbody is None:
        return {}

    seasons = {}
    for tr in tbody.find_all("tr"):
        classes = tr.get("class") or []
        if "thead" in classes:
            continue

        season_cell = tr.find(["th", "td"], {"data-stat": season_key})
        if season_cell is None:
            continue
        season = season_cell.get_text(strip=True)
        if not SEASON_RE.match(season):  # skips Career totals, blanks, etc.
            continue

        row = {}
        for stat_key, friendly in field_map.items():
            cell = tr.find(["th", "td"], {"data-stat": stat_key})
            row[friendly] = cell.get_text(strip=True) if cell else ""
        seasons[season] = row

    return seasons


def scrape_player(slug, name):
    """Return a list of per-season dicts for one player.

    A player who never appeared returns a single sentinel row with gp=0 so
    downstream tiering can label them 'never played'.
    """
    if not slug:
        return [{"slug": "", "player": name, "season": "", "gp": "0"}]

    initial = slug[0]  # BBRef groups player pages by first letter of the slug.
    url = PLAYER_URL.format(initial=initial, slug=slug)
    cache_path = os.path.join(RAW_DIR, "players", f"{slug}.html")
    html = fetch_page(url, cache_path)

    if html is None:
        return [{"slug": slug, "player": name, "season": "", "gp": "0"}]

    soup = BeautifulSoup(html, "lxml")
    per_game = parse_stat_table(find_table(soup, "per_game_stats"), PER_GAME_FIELDS)
    advanced = parse_stat_table(find_table(soup, "advanced"), ADVANCED_FIELDS)

    if not per_game:
        return [{"slug": slug, "player": name, "season": "", "gp": "0"}]

    rows = []
    for season, pg in sorted(per_game.items()):
        merged = {"slug": slug, "player": name}
        merged.update(pg)
        merged.update(advanced.get(season, {}))
        rows.append(merged)
    return rows


def load_draft_players(year=None):
    path = os.path.join(PROCESSED_DIR, "draft_picks.csv")
    with open(path, newline="", encoding="utf-8") as f:
        players = list(csv.DictReader(f))
    if year is not None:
        players = [p for p in players if int(p["draft_year"]) == year]
    return players


def main():
    parser = argparse.ArgumentParser(description="Scrape player career stats.")
    parser.add_argument("--year", type=int, help="Only players from this draft year")
    parser.add_argument("--limit", type=int, help="Cap number of players (testing)")
    args = parser.parse_args()

    players = load_draft_players(args.year)
    if args.limit:
        players = players[: args.limit]

    print(f"Scraping careers for {len(players)} players...")
    all_rows = []
    for i, p in enumerate(players, 1):
        print(f"[{i}/{len(players)}] {p['player']}")
        all_rows.extend(scrape_player(p["slug"], p["player"]))

    fieldnames = ["slug", "player", "season", "age", "team", "gp", "mpg",
                  "pts", "reb", "ast", "stl", "blk", "per", "ts_pct",
                  "usg_pct", "ws", "ws_per_48", "bpm", "vorp"]
    out_path = os.path.join(PROCESSED_DIR, "career_seasons.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Wrote {len(all_rows)} player-season rows -> {out_path}")


if __name__ == "__main__":
    main()
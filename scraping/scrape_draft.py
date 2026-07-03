"""Scrape NBA draft class data from Basketball Reference.

Pulls one draft year at a time: overall pick, round, player name, the player's
Basketball Reference slug (needed to fetch career stats later), and drafting team.

Basketball Reference asks scrapers to stay under ~20 requests/minute. We cache
every fetched page to data/raw/ so re-runs never re-hit the server, and sleep
between live requests. Be a good citizen: this is public data, but the server
isn't yours.

Usage:
    python scraping/scrape_draft.py --year 2014
    python scraping/scrape_draft.py --start 2000 --end 2024
"""

import argparse
import os
import time
import csv

import requests
from bs4 import BeautifulSoup, Comment

BASE_URL = "https://www.basketball-reference.com/draft/NBA_{year}.html"
RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")

# Conservative rate limit: ~17 requests/min, comfortably under BBRef's threshold.
REQUEST_DELAY_SECONDS = 3.5

HEADERS = {
    "User-Agent": (
        "nba-second-round-tracker/1.0 (personal analytics project; "
        "contact: your-email@example.com)"
    )
}


def fetch_page(url, cache_path):
    """Return page HTML, using the local cache if present.

    Caching keeps re-runs fast and keeps load off Basketball Reference. Delete
    the cached file to force a fresh pull.
    """
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()

    print(f"  fetching {url}")
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    time.sleep(REQUEST_DELAY_SECONDS)

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(response.text)
    return response.text


def parse_draft_table(html):
    """Extract one row per drafted player from a draft-year page.

    Basketball Reference tucks some tables inside HTML comments to defeat
    naive scrapers. The main draft table (id="stats") is usually live, but we
    check comments too so this keeps working if their markup shifts.
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="stats")

    if table is None:
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            if 'id="stats"' in comment:
                table = BeautifulSoup(comment, "lxml").find("table", id="stats")
                break

    if table is None:
        raise ValueError("Could not locate the draft table on this page.")

    rows = []
    current_round = 1  # Flips to 2 when we pass the "Round 2" divider header.
    for tr in table.find("tbody").find_all("tr"):
        pick_cell = tr.find("td", {"data-stat": "pick_overall"})

        # A round-divider row has no pick cell and carries a "Round N" banner.
        # Detect it and flip the round, then move on. (Every *player* row also
        # has a <th> — the rank number — so we must key on the banner text and
        # the absence of a pick cell, not just the presence of a <th>.)
        if pick_cell is None:
            row_text = tr.get_text(strip=True)
            if "Round 2" in row_text:
                current_round = 2
            elif "Round 1" in row_text:
                current_round = 1
            continue

        player_cell = tr.find("td", {"data-stat": "player"})
        team_cell = tr.find("td", {"data-stat": "team_id"})
        if player_cell is None:
            continue

        link = player_cell.find("a")
        slug = link["href"].split("/")[-1].replace(".html", "") if link else ""

        overall_pick = int(pick_cell.get_text(strip=True))
        rows.append(
            {
                "overall_pick": overall_pick,
                "round": current_round,  # read from page structure, not assumed
                "player": player_cell.get_text(strip=True),
                "slug": slug,
                "team": team_cell.get_text(strip=True) if team_cell else "",
            }
        )

    return rows


def scrape_year(year, second_round_only=True):
    """Scrape one draft year and return a list of player dicts."""
    print(f"Draft {year}:")
    url = BASE_URL.format(year=year)
    cache_path = os.path.join(RAW_DIR, f"draft_{year}.html")
    html = fetch_page(url, cache_path)

    rows = parse_draft_table(html)
    for row in rows:
        row["draft_year"] = year

    if second_round_only:
        rows = [r for r in rows if r["round"] == 2]

    print(f"  parsed {len(rows)} players")
    return rows


def save_rows(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = ["draft_year", "overall_pick", "round", "player", "slug", "team"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {path}")


def main():
    parser = argparse.ArgumentParser(description="Scrape NBA draft classes.")
    parser.add_argument("--year", type=int, help="Single draft year, e.g. 2014")
    parser.add_argument("--start", type=int, help="First year (range mode)")
    parser.add_argument("--end", type=int, help="Last year, inclusive (range mode)")
    parser.add_argument(
        "--all-rounds",
        action="store_true",
        help="Keep round 1 too (default: second round only)",
    )
    args = parser.parse_args()

    if args.year:
        years = [args.year]
    elif args.start and args.end:
        years = range(args.start, args.end + 1)
    else:
        parser.error("Provide --year, or both --start and --end.")

    all_rows = []
    for year in years:
        all_rows.extend(scrape_year(year, second_round_only=not args.all_rounds))

    out_path = os.path.join(PROCESSED_DIR, "draft_picks.csv")
    save_rows(all_rows, out_path)


if __name__ == "__main__":
    main()
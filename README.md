# NBA Second-Round Draft Analysis

**A study of all 742 NBA second-round draft picks from 2000 to 2024, and how their careers turned out.**

🔗 **[View the live dashboard](https://brand0n-cod3.github.io/nba-second-round-tracker/dashboard/)**

---

## Research question

**Are second-round draft picks worth it in the long run?**

Second-round picks get thrown around in trade deals as if they're worth almost
nothing — and very few players from that round ever truly make it in the league.
This project scrapes every second-round pick from 2000 to 2024, reconstructs each
player's season-by-season career, and asks whether the round produces real NBA
value or mostly churns through players who never stick.

## Hypothesis

The second round is primarily made up of players who do very little in the league,
with a few exceptions that are usually (a) international players or (b) picks taken
right after the first round.

## Key findings

- **Most second-rounders don't pan out.** Roughly 80% of picks land in the two
  lowest career tiers (Fringe or Bust). The base-rate skepticism holds.
- **Value declines steadily by pick, without a cliff.** Hit rate falls from 29.4%
  (picks 31–40) to 20.8% (41–50) to 9.3% (51–60). The early second round is
  stronger — but solid value extends into the 41–50 range, not just the first ten
  picks.
- **International players are a boom-or-bust bet.** They make up 31.9% of all picks
  but are overrepresented among *both* Stars (37.5%) and Busts (43.1%) — a U-shaped
  outcome the original hypothesis didn't anticipate, likely reflecting how teams use
  late picks to draft-and-stash international prospects.

Full write-up in the dashboard's **Conclusion** tab.

## Dashboard

An interactive dashboard (vanilla HTML/JS + Chart.js) with five views:

- **Overview** — hit rates, tier distribution, and career-arc trajectories
- **Player Explorer** — filterable table of all 742 picks with career Win-Share sparklines
- **Team Intelligence** — a value-vs-volume scatter showing which franchises find
  second-round value, with per-team drill-down
- **Steals** — the ten biggest second-round finds by career Win Shares
- **Conclusion** — the hypothesis revisited against the data

## How it works

```
scraping/scrape_draft.py     → draft_picks.csv     (picks, players, teams by year)
scraping/scrape_careers.py   → career_seasons.csv  (per-season stats + birth country)
scraping/merge.py            → players.json, data.js  (per-player aggregates + tiers)
analysis/tier_classifier.py  → career-outcome tiers (Star → Bust)
dashboard/index.html         → the dashboard (reads data.js)
```

Data is scraped from [Basketball Reference](https://www.basketball-reference.com/),
with response caching and rate-limiting. The pipeline handles the site's real-world
messiness: UTF-8 encoding of international names, tables hidden inside HTML comments,
column-name changes across eras, and round-boundary differences in pre-expansion
(29-team) draft years.

## Method notes & limitations

- **Tiers** are assigned from career Win Shares, games played, and peak season
  (Star ≥ 60 career WS; Hit = rotation level or better, ≥ ~8 WS). These cutoffs are
  a deliberate, transparent choice, not a league standard.
- **"International"** means born outside the U.S. and its territories, read from each
  player's Basketball Reference birthplace. This is a birth-country proxy — it counts
  Canadians and dual nationals as international, and can't capture where a player
  actually developed.
- **Team Win Shares** are credited to the *drafting* team regardless of where a player
  later played, so Team Intelligence measures draft *evaluation*, not roster retention.
- **Relocated franchises** appear under their historical Basketball Reference codes
  (e.g. Seattle and Oklahoma City are listed separately).
- Two 2024 picks with no Basketball Reference page were excluded (740 players with
  career data; 742 picks total, including two later-recovered pre-2005 pick-30
  second-rounders).

## Tech

Python (requests, BeautifulSoup, pandas) for the pipeline; vanilla JavaScript +
Chart.js for the dashboard; hosted on GitHub Pages.

## Running it yourself

```bash
pip install -r requirements.txt
python scraping/scrape_draft.py --start 2000 --end 2024
python scraping/scrape_careers.py
python scraping/merge.py
# then open dashboard/index.html
```

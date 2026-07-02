"""Assign a career-outcome tier to each second-round pick.

Tiers, best to worst:
    Star            - franchise-level or high-end starter
    Key contributor - long-term starter / high-value role player
    Rotation        - steady rotation piece
    Fringe          - marginal NBA player, in and out of the league
    Bust            - never stuck (minimal or no NBA games)

The cutoffs here are RULES-BASED STARTING POINTS, keyed mainly on career Win
Shares plus games played and peak single-season impact. They are intentionally
simple and meant to be validated and tuned against the full dataset in the EDA
notebook (analysis/eda.ipynb) once all 25 draft classes are scraped. If the
data suggests cleaner breakpoints, adjust the thresholds in this one place.
"""


def assign_tier(career):
    """Return a tier string for one player's career-aggregate dict.

    Expected keys in `career`:
        career_gp : total regular-season games played
        career_ws : total career Win Shares
        peak_ws   : best single-season Win Shares
    """
    gp = career.get("career_gp", 0) or 0
    ws = career.get("career_ws", 0) or 0
    peak_ws = career.get("peak_ws", 0) or 0

    # Never stuck in the league.
    if gp < 30:
        return "Bust"

    # A monster peak marks a star even if the career total is still climbing
    # (helps young players mid-career).
    if peak_ws >= 10:
        return "Star"

    # Played, but never provided real value.
    if ws < 8:
        return "Fringe"

    # Steady rotation contributor.
    if ws < 25:
        return "Rotation"

    # Long-term starter / high-value role player.
    if ws < 60:
        return "Key contributor"

    # Franchise-level outcome.
    return "Star"
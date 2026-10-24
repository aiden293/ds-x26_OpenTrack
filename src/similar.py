"""Phase 7: real similar past cases for a new request.

Usage: .venv/bin/python -m src.similar   (prints examples for the demo types)
Candidates are valid closures (cases_for_app.parquet) of the same type closed before
reference_date. Matching never uses resolution time. Match levels, tried in order:
  1 same_neighborhood_season: same neighborhood, day-of-year within +-60 days
  2 any_neighborhood_season:  any neighborhood, day-of-year within +-60 days
  3 any_time:                 any neighborhood, any time of year
Within a level: day-of-year distance in weekly buckets, then most recent first.
closure_reason is shown without its "Case Closed. Closed date: ..." header and with
emails / phone numbers redacted. No coordinates are returned.
"""
from datetime import datetime
from functools import lru_cache

import numpy as np
import pandas as pd

from src.features import PROC

SEASON_DAYS = 60
COLUMNS = ["case_enquiry_id", "type", "neighborhood", "open_dt", "closed_dt",
           "resolution_days", "closure_reason", "match_level"]
LEVELS = ["same_neighborhood_season", "any_neighborhood_season", "any_time"]
HEADER_RE = r"^Case Closed\.?\s*(?:Closed date\s*:\s*(?:\w{3} \w{3} \d{2} [\d:]+ \w{3} \d{4}|[\d-]+ [\d:.]+))?\s*"
EMAIL_RE = r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*"
PHONE_RE = r"\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"


def clean_reason(s: pd.Series) -> pd.Series:
    return (s.fillna("").str.replace(HEADER_RE, "", regex=True)
            .str.replace(EMAIL_RE, "[email]", regex=True)
            .str.replace(PHONE_RE, "[phone]", regex=True)
            .str.replace(r"\s+", " ", regex=True).str.strip())


@lru_cache(maxsize=1)
def _by_type() -> dict:
    cols = ["case_enquiry_id", "type", "neighborhood", "open_dt", "closed_dt",
            "resolution_days", "closure_reason"]
    df = pd.read_parquet(PROC / "cases_for_app.parquet", columns=cols)
    df["doy"] = df["open_dt"].dt.day_of_year
    return {t: g.sort_values("closed_dt").reset_index(drop=True) for t, g in df.groupby("type")}


def similar_cases(type: str, neighborhood: str, open_date: datetime, k: int = 10,
                  reference_date: datetime | None = None) -> pd.DataFrame:
    open_date = pd.Timestamp(open_date)
    ref = pd.Timestamp(reference_date) if reference_date is not None else open_date
    g = _by_type().get(type)
    if g is None:
        return pd.DataFrame(columns=COLUMNS)
    g = g.iloc[: np.searchsorted(g["closed_dt"].values, ref.to_datetime64(), "left")]  # closed < ref

    diff = np.abs(g["doy"].values - open_date.day_of_year)
    diff = np.minimum(diff, 365 - diff)  # circular day-of-year distance
    in_season = diff <= SEASON_DAYS
    same_nb = (g["neighborhood"] == neighborhood).values
    level = np.select([in_season & same_nb, in_season], [0, 1], default=2)

    ranked = g.assign(level=level, week=diff // 7).sort_values(
        ["level", "week", "open_dt"], ascending=[True, True, False]).head(k)
    out = ranked.assign(match_level=[LEVELS[i] for i in ranked["level"]],
                        closure_reason=clean_reason(ranked["closure_reason"]))
    return out[COLUMNS].reset_index(drop=True)


def main() -> None:
    from src.clean import DEMO_TYPES
    pd.set_option("display.width", 200, "display.max_colwidth", 60)
    examples = [(DEMO_TYPES[0], "Dorchester"), (DEMO_TYPES[1], "Hyde Park"), (DEMO_TYPES[3], "Charlestown")]
    for t, nb in examples:
        res = similar_cases(t, nb, datetime(2026, 10, 24, 10, 0), k=5)
        print(f"\n=== {t} | {nb} | open 2026-10-24")
        print(res.assign(open_dt=res.open_dt.dt.date, closed_dt=res.closed_dt.dt.date,
                         resolution_days=res.resolution_days.round(1)).to_string(index=False))


if __name__ == "__main__":
    main()

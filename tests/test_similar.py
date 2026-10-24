"""Sanity test for similar_cases.

Usage: .venv/bin/python -m tests.test_similar
Checks for random (type, neighborhood, date) queries: same type, closed before the
reference date, k rows when enough history, match levels in order, no coordinates,
neighborhood preference honored, and redaction applied.
"""
import numpy as np
import pandas as pd

from src.similar import COLUMNS, LEVELS, SEASON_DAYS, _by_type, similar_cases


def main() -> None:
    rng = np.random.default_rng(0)
    groups = _by_type()
    types = [t for t, g in groups.items() if len(g) > 500]
    n = 0
    for _ in range(100):
        t = types[rng.integers(len(types))]
        g = groups[t]
        row = g.iloc[rng.integers(len(g))]
        q_date, nb = row.open_dt, row.neighborhood
        res = similar_cases(t, nb, q_date, k=10)
        assert list(res.columns) == COLUMNS
        assert (res["type"] == t).all()
        assert (res["closed_dt"] < q_date).all(), "leak: closed at/after reference date"
        avail = (g["closed_dt"] < q_date).sum()
        assert len(res) == min(10, avail)
        lv = res["match_level"].map(LEVELS.index).values
        assert (np.diff(lv) >= 0).all(), "levels out of order"
        same = res["match_level"] == LEVELS[0]
        assert (res.loc[same, "neighborhood"] == nb).all()
        doy = res["open_dt"].dt.day_of_year
        d = np.minimum(abs(doy - q_date.day_of_year), 365 - abs(doy - q_date.day_of_year))
        assert (d[res["match_level"] != LEVELS[2]] <= SEASON_DAYS).all()
        # level-1 must be exhausted before level-2 appears
        if (res["match_level"] == LEVELS[1]).any():
            prior = g[(g.closed_dt < q_date) & (g.neighborhood == nb)]
            pd_ = np.abs(prior.open_dt.dt.day_of_year - q_date.day_of_year)
            assert (np.minimum(pd_, 365 - pd_) <= SEASON_DAYS).sum() == same.sum()
        assert not res["closure_reason"].str.contains(r"@\w", regex=True).any()
        n += 1

    # explicit reference_date earlier than open_date
    t = "Request for Pothole Repair"
    res = similar_cases(t, "Dorchester", pd.Timestamp("2025-06-01"), reference_date=pd.Timestamp("2023-01-01"))
    assert (res["closed_dt"] < pd.Timestamp("2023-01-01")).all()
    assert similar_cases("No Such Type", "Dorchester", pd.Timestamp("2025-01-01")).empty
    print(f"OK: {n} random queries + reference_date + unknown type checks passed")


if __name__ == "__main__":
    main()

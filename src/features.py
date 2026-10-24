"""Phase 3: intake-time features for every valid closed case.

Usage: .venv/bin/python -m src.features
Reads data/processed/all_cases.parquet (every case, for queue state) and clean.parquet
(valid closures, for targets and recent performance). Writes data/processed/features.parquet.

Every feature uses only information available at the case's open_dt:
- backlog_*: cases of the same group opened before t and not closed before t. Uses ALL
  cases (open, excluded and bulk closures too) because they occupy the queue until closed.
  Exact at t via searchsorted. Cases opened before 2021 are not in the data, so 2021 is
  warm-up only (training starts 2022).
- backlog_90d_type: same, but only counting cases opened in the 90 days before t's day.
  Stale cases that are never closed (e.g. ~30% of potholes) make the plain backlog drift up
  over time; this version ignores them. Computed at the start of the open day.
- roll_*: median / p80 / count of resolution_days among VALID closures of the same group
  closed in the 30 days before the start of the open day (strictly before t).
"""
from pathlib import Path

import holidays
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"

CAT_FEATURES = ["type", "neighborhood", "source", "hour_bucket"]
NUM_FEATURES = [
    "month", "weekday", "is_holiday", "target_days",
    "backlog_type", "backlog_type_nbhd", "backlog_90d_type",
    "roll_p50_type", "roll_p80_type", "roll_n_type",
    "roll_p50_type_nbhd", "roll_n_type_nbhd",
]
FEATURES = CAT_FEATURES + NUM_FEATURES
ROLL_DAYS, RECENT_DAYS, MIN_NBHD_N = 30, 90, 5
MA_HOLIDAYS = holidays.country_holidays("US", subdiv="MA", years=range(2020, 2028))


def _groups(df: pd.DataFrame, keys: list[str]) -> dict:
    return df.groupby(keys, observed=True).indices


def backlog(cases: pd.DataFrame, keys: list[str], query: pd.DataFrame) -> np.ndarray:
    """count(open_dt < t) - count(closed_dt < t) within each group, t = query.open_dt."""
    out = np.zeros(len(query))
    o_all, c_all = cases["open_dt"].values, cases["closed_dt"].values
    cgroups = _groups(cases, keys)
    t_all = query["open_dt"].values
    for k, qidx in _groups(query, keys).items():
        if k not in cgroups:
            continue
        cidx = cgroups[k]
        opens = np.sort(o_all[cidx])
        closes = c_all[cidx]
        closes = np.sort(closes[~np.isnat(closes)])
        t = t_all[qidx]
        out[qidx] = np.searchsorted(opens, t, "left") - np.searchsorted(closes, t, "left")
    return out


def backlog_recent(cases: pd.DataFrame, keys: list[str], query: pd.DataFrame,
                   days: int = RECENT_DAYS) -> np.ndarray:
    """Cases opened in [d - days, d) and not closed before d, d = start of query's open day."""
    out = np.zeros(len(query))
    o_all, c_all = cases["open_dt"].values, cases["closed_dt"].values
    cgroups = _groups(cases, keys)
    qday = query["open_dt"].dt.floor("D").values
    win = np.timedelta64(days, "D")
    for k, qidx in _groups(query, keys).items():
        if k not in cgroups:
            continue
        cidx = cgroups[k]
        order = np.argsort(o_all[cidx])
        opens, closes = o_all[cidx][order], c_all[cidx][order]
        ud, inv = np.unique(qday[qidx], return_inverse=True)
        lo, hi = np.searchsorted(opens, ud - win), np.searchsorted(opens, ud)
        # NaT compares False with >=, so treat never-closed explicitly
        vals = [np.sum(np.isnat(closes[a:b]) | (closes[a:b] >= d)) for a, b, d in zip(lo, hi, ud)]
        out[qidx] = np.asarray(vals)[inv]
    return out


def rolling(closures: pd.DataFrame, keys: list[str], query: pd.DataFrame,
            days: int = ROLL_DAYS, min_n: int = 1) -> np.ndarray:
    """[p50, p80, n] of resolution_days for closures in [d - days, d), d = start of open day."""
    out = np.full((len(query), 3), np.nan)
    c_all, v_all = closures["closed_dt"].values, closures["resolution_days"].values
    cgroups = _groups(closures, keys)
    qday = query["open_dt"].dt.floor("D").values
    win = np.timedelta64(days, "D")
    for k, qidx in _groups(query, keys).items():
        if k not in cgroups:
            out[qidx, 2] = 0
            continue
        cidx = cgroups[k]
        order = np.argsort(c_all[cidx])
        closed, vals = c_all[cidx][order], v_all[cidx][order]
        ud, inv = np.unique(qday[qidx], return_inverse=True)
        lo, hi = np.searchsorted(closed, ud - win), np.searchsorted(closed, ud)
        stats = np.full((len(ud), 3), np.nan)
        stats[:, 2] = hi - lo
        for i, (a, b) in enumerate(zip(lo, hi)):
            if b - a >= min_n:
                stats[i, :2] = np.quantile(vals[a:b], [0.5, 0.8])
        out[qidx] = stats[inv]
    return out


def calendar_features(query: pd.DataFrame) -> pd.DataFrame:
    t = query["open_dt"]
    return pd.DataFrame({
        "month": t.dt.month,
        "weekday": t.dt.day_of_week,
        "hour_bucket": pd.cut(t.dt.hour, [-1, 5, 11, 17, 23],
                              labels=["night", "morning", "afternoon", "evening"]).astype(str),
        "is_holiday": t.dt.date.map(lambda d: d in MA_HOLIDAYS).astype(int),
    }, index=query.index)


def build_features(query: pd.DataFrame, cases: pd.DataFrame, closures: pd.DataFrame) -> pd.DataFrame:
    """query needs type, neighborhood, source, open_dt and (optionally) target_dt."""
    q = query.reset_index(drop=True)
    f = q[["type", "neighborhood", "source"]].copy()
    f = f.join(calendar_features(q))
    f["target_days"] = ((q["target_dt"] - q["open_dt"]).dt.total_seconds() / 86400
                        if "target_dt" in q else np.nan)
    f["backlog_type"] = backlog(cases, ["type"], q)
    f["backlog_type_nbhd"] = backlog(cases, ["type", "neighborhood"], q)
    f["backlog_90d_type"] = backlog_recent(cases, ["type"], q)
    r = rolling(closures, ["type"], q)
    f["roll_p50_type"], f["roll_p80_type"], f["roll_n_type"] = r.T
    r = rolling(closures, ["type", "neighborhood"], q, min_n=MIN_NBHD_N)
    f["roll_p50_type_nbhd"], f["roll_n_type_nbhd"] = r[:, 0], r[:, 2]
    return f[FEATURES]


def main() -> None:
    cases = pd.read_parquet(PROC / "all_cases.parquet",
                            columns=["type", "neighborhood", "open_dt", "closed_dt"])
    clean = pd.read_parquet(PROC / "clean.parquet")
    feats = build_features(clean, cases, clean)
    keep = ["case_enquiry_id", "open_dt", "closed_dt", "target_dt", "year", "reason",
            "closure_reason", "resolution_days"]
    out = pd.concat([clean[keep].reset_index(drop=True), feats], axis=1)
    out.to_parquet(PROC / "features.parquet", index=False)
    print(f"Saved features.parquet: {len(out):,} rows, features={FEATURES}")
    print(out[NUM_FEATURES].describe().T.round(2).to_string())
    print("\nmissing %:\n" + (out[FEATURES].isna().mean() * 100).round(1).to_string())


if __name__ == "__main__":
    main()

"""Brute-force sanity test for backlog and rolling features.

Usage: .venv/bin/python -m tests.test_features   (run src.features first)
Recomputes features for random cases with plain boolean filters and asserts equality
with data/processed/features.parquet. Also checks no closure at/after open_dt is used.
"""
import numpy as np
import pandas as pd

from src.features import MIN_NBHD_N, PROC, RECENT_DAYS, ROLL_DAYS

N_SAMPLES = 300


def main() -> None:
    cases = pd.read_parquet(PROC / "all_cases.parquet",
                            columns=["type", "neighborhood", "open_dt", "closed_dt"])
    clean = pd.read_parquet(PROC / "clean.parquet",
                            columns=["case_enquiry_id", "type", "neighborhood", "closed_dt", "resolution_days"])
    feats = pd.read_parquet(PROC / "features.parquet")
    sample = feats.sample(N_SAMPLES, random_state=42)

    for _, r in sample.iterrows():
        t, ty, nb = r.open_dt, r.type, r.neighborhood
        d = t.floor("D")
        same = cases[cases.type == ty]
        exp = (same.open_dt < t).sum() - (same.closed_dt < t).sum()
        assert r.backlog_type == exp, (r.case_enquiry_id, r.backlog_type, exp)

        sn = same[same.neighborhood == nb]
        exp = (sn.open_dt < t).sum() - (sn.closed_dt < t).sum()
        assert r.backlog_type_nbhd == exp, (r.case_enquiry_id, r.backlog_type_nbhd, exp)

        rec = same[(same.open_dt >= d - pd.Timedelta(days=RECENT_DAYS)) & (same.open_dt < d)]
        exp = (rec.closed_dt.isna() | (rec.closed_dt >= d)).sum()
        assert r.backlog_90d_type == exp, (r.case_enquiry_id, r.backlog_90d_type, exp)

        win = clean[(clean.type == ty) & (clean.closed_dt >= d - pd.Timedelta(days=ROLL_DAYS))
                    & (clean.closed_dt < d)]
        assert (win.closed_dt < t).all()  # leakage guard
        assert r.roll_n_type == len(win)
        if len(win):
            assert np.isclose(r.roll_p50_type, win.resolution_days.quantile(0.5))
            assert np.isclose(r.roll_p80_type, win.resolution_days.quantile(0.8))
        else:
            assert np.isnan(r.roll_p50_type)

        wn = win[win.neighborhood == nb]
        assert r.roll_n_type_nbhd == len(wn)
        if len(wn) >= MIN_NBHD_N:
            assert np.isclose(r.roll_p50_type_nbhd, wn.resolution_days.quantile(0.5))
        else:
            assert np.isnan(r.roll_p50_type_nbhd)

    print(f"OK: {N_SAMPLES} random cases match brute-force backlog / rolling features")


if __name__ == "__main__":
    main()

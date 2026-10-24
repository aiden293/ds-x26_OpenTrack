"""Final app artifacts: refit on 2022-2025 and export everything src/predict.py needs.

Usage: .venv/bin/python -m src.export
Reported metrics stay the Phase 6 numbers from train-only models (models/eval/).
Model settings (feature set, hyperparameters, per-type ML/baseline choice) are the ones
chosen on 2024 validation (reports/val_metrics.json). Writes:
  models/baseline.json, models/p50.joblib, models/p80.joblib, models/ontime.joblib
  models/state_snapshot.parquet  queue / recent-performance features per (type, neighborhood)
                                 at STATE_TIME, computed with the same build_features code
  models/target_days.json        estimated SLA days per (type, weekday) from 2025 cases
  models/meta.json               fit years, state time, data range, policy
  data/processed/cases_for_app.parquet, models/choices.json
"""
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from src.clean import DEMO_TYPES
from src.features import PROC, build_features
from src.policy import ONTIME_TYPES, P80_BASELINE_TYPES
from src.train import (EVAL_DIR, MIN_TYPE_N, MODELS, PARAM_GRID, REPORTS, category_levels,
                       fit_baseline, fit_quantile, make_X, ontime_data)

FINAL_YEARS = (2022, 2025)
TARGET_YEAR = 2025          # SLA rules for target_days lookup
DEFAULT_SOURCE = "Citizens Connect App"   # resident filing through the app
# Queue state for new requests is taken just before the Oct 2025 311 system change.
# After it, closures stop being recorded in this data for some queues (Street Light
# valid closures: Sep 279, Oct 183, Nov 59, Dec 1), so a later snapshot is distorted.
STATE_TIME = pd.Timestamp("2025-10-01")
APP_COLUMNS = ["case_enquiry_id", "type", "neighborhood", "source", "open_dt", "closed_dt",
               "target_dt", "resolution_days", "closure_reason", "year"]


def state_snapshot(cases: pd.DataFrame, clean: pd.DataFrame, state_time: pd.Timestamp) -> pd.DataFrame:
    """Features that depend on the queue, for every (type, neighborhood) at state_time."""
    types = sorted(clean["type"].unique())
    nbhds = sorted(clean["neighborhood"].unique())
    grid = pd.MultiIndex.from_product([types, nbhds], names=["type", "neighborhood"]).to_frame(index=False)
    grid["source"] = DEFAULT_SOURCE
    grid["open_dt"] = state_time
    f = build_features(grid, cases, clean)
    state_cols = [c for c in f.columns if c.startswith(("backlog", "roll"))]
    return pd.concat([grid[["type", "neighborhood"]], f[state_cols]], axis=1)


def target_days_table(clean_all: pd.DataFrame) -> dict:
    d = clean_all[clean_all["year"] == TARGET_YEAR].dropna(subset=["target_dt"])
    td = (d["target_dt"] - d["open_dt"]).dt.total_seconds() / 86400
    wd = d["open_dt"].dt.day_of_week
    by_wd = td.groupby([d["type"], wd]).median()
    out = {}
    for t, g in by_wd.groupby(level=0):
        out[t] = {str(w): round(float(v), 3) for (_, w), v in g.items()}
    return out


def main() -> None:
    feats = pd.read_parquet(PROC / "features.parquet")
    clean = pd.read_parquet(PROC / "clean.parquet")
    cases = pd.read_parquet(PROC / "all_cases.parquet", columns=["type", "neighborhood", "open_dt", "closed_dt"])
    val = json.loads((REPORTS / "val_metrics.json").read_text())
    fit = feats[feats["year"].between(*FINAL_YEARS)]
    print(f"final fit rows: {len(fit):,} ({FINAL_YEARS[0]}-{FINAL_YEARS[1]})")

    base = fit_baseline(fit)
    (MODELS / "baseline.json").write_text(json.dumps(base, indent=1, default=float))
    levels = category_levels(fit)
    use_model = joblib.load(EVAL_DIR / "p50.joblib")["use_model_by_type"]  # chosen on validation
    for qname, q in [("p50", 0.5), ("p80", 0.8)]:
        ev = joblib.load(EVAL_DIR / f"{qname}.joblib")
        params = val["chosen"][qname]["params"]
        m = fit_quantile(make_X(fit, ev["features"], levels), fit["resolution_days"], q, params)
        joblib.dump({"model": m, "features": ev["features"], "levels": levels,
                     "use_model_by_type": use_model, "fit_years": FINAL_YEARS}, MODELS / f"{qname}.joblib")
        print(f"saved {qname}: params={params}")

    data, n_open, snapshot = ontime_data(feats)
    data = data[data["year"].between(*FINAL_YEARS)]
    ev = joblib.load(EVAL_DIR / "ontime.joblib")
    clf = HistGradientBoostingClassifier(categorical_features="from_dtype", early_stopping=False,
                                         random_state=0, **PARAM_GRID[1])
    clf.fit(make_X(data, ev["features"], levels), data["label"])
    joblib.dump({"model": clf, "features": ev["features"], "levels": levels, "fit_years": FINAL_YEARS},
                MODELS / "ontime.joblib")
    print(f"saved ontime: rows={len(data):,} pos_rate={data['label'].mean():.3f}")

    state_time = STATE_TIME
    snap = state_snapshot(cases, clean, state_time)
    snap.to_parquet(MODELS / "state_snapshot.parquet", index=False)
    (MODELS / "target_days.json").write_text(json.dumps(target_days_table(clean), indent=1))

    app = clean[APP_COLUMNS].merge(feats.drop(columns=[c for c in feats.columns if c in APP_COLUMNS and c != "case_enquiry_id"]),
                                   on="case_enquiry_id", how="left")
    app.to_parquet(PROC / "cases_for_app.parquet", index=False)

    counts = fit["type"].value_counts()
    choices = {
        "types": [{"type": t, "n": int(n), "demo": t in DEMO_TYPES} for t, n in counts.items() if n >= MIN_TYPE_N],
        "demo_types": DEMO_TYPES,
        "neighborhoods": sorted(fit["neighborhood"].unique()),
        "sources": sorted(fit["source"].unique()),
        "default_source": DEFAULT_SOURCE,
    }
    (MODELS / "choices.json").write_text(json.dumps(choices, indent=1))
    meta = {
        "fit_years": FINAL_YEARS, "state_time": str(state_time), "data_snapshot": str(snapshot),
        "open_dt_range": [str(clean["open_dt"].min()), str(clean["open_dt"].max())],
        "default_source": DEFAULT_SOURCE, "ontime_types": sorted(ONTIME_TYPES),
        "p80_baseline_types": sorted(P80_BASELINE_TYPES),
        "reported_metrics": "reports/metrics.json (train-only models, 2025 test)",
        "source": "City of Boston 311 Service Requests, data.boston.gov, PDDL",
    }
    (MODELS / "meta.json").write_text(json.dumps(meta, indent=1, default=str))
    print(f"state_time={state_time}; snapshot rows={len(snap):,}; cases_for_app rows={len(app):,}; "
          f"types in choices={len(choices['types'])}")


if __name__ == "__main__":
    main()

"""Prediction API for the CivicPulse app.

    from src.predict import predict
    predict("Request for Pothole Repair", "Dorchester", datetime(2026, 10, 24, 9, 30))

Needs only files in models/ (run src.export first). Assumptions, also in APP_HANDOFF.md:
- Queue features (backlog_*, roll_*) come from models/state_snapshot.parquet, i.e. the
  queue as of meta.json "state_time" (2025-10-01, just before the Oct 2025 311 system
  change, after which some closures stop appearing in this data), whatever open_date is.
  The data has no requests after 2025, so today's queue cannot be computed.
- Calendar features (month, weekday, hour, holiday) use the given open_date.
- target_days is the 2025 median SLA for (type, weekday of open_date); None if the type
  has no SLA. It is an estimate of the city's target, not the official date.
- source=None means "Citizens Connect App" (a resident filing through the app).
- Unknown neighborhood -> "Unknown / Citywide". Unknown type -> baseline fallback.
Outputs are historical estimates, not official City of Boston deadlines or guarantees.
"""
from datetime import datetime
from functools import lru_cache
import json

import joblib
import numpy as np
import pandas as pd

from src.clean import UNKNOWN_NEIGHBORHOOD
from src.features import calendar_features
from src.policy import ONTIME_TYPES, P80_BASELINE_TYPES
from src.train import MODELS, baseline_lookup, make_X, predict_days


@lru_cache(maxsize=1)
def _load() -> dict:
    meta = json.loads((MODELS / "meta.json").read_text())
    snap = pd.read_parquet(MODELS / "state_snapshot.parquet").set_index(["type", "neighborhood"])
    return {
        "p50": joblib.load(MODELS / "p50.joblib"),
        "p80": joblib.load(MODELS / "p80.joblib"),
        "ontime": joblib.load(MODELS / "ontime.joblib"),
        "baseline": json.loads((MODELS / "baseline.json").read_text()),
        "target_days": json.loads((MODELS / "target_days.json").read_text()),
        "choices": json.loads((MODELS / "choices.json").read_text()),
        "snapshot": snap,
        "meta": meta,
    }


def _target_days(type_: str, open_date: pd.Timestamp) -> float | None:
    by_wd = _load()["target_days"].get(type_)
    if not by_wd:
        return None
    v = by_wd.get(str(open_date.day_of_week))
    return float(v if v is not None else np.median(list(by_wd.values())))


def _features(type_: str, neighborhood: str, open_date: pd.Timestamp, source: str) -> pd.DataFrame:
    q = pd.DataFrame({"type": [type_], "neighborhood": [neighborhood], "source": [source],
                      "open_dt": [open_date]})
    f = pd.concat([q[["type", "neighborhood", "source"]], calendar_features(q)], axis=1)
    td = _target_days(type_, open_date)
    f["target_days"] = np.nan if td is None else td
    snap = _load()["snapshot"]
    key = (type_, neighborhood)
    state = snap.loc[key] if key in snap.index else pd.Series(dtype=float)
    for c in snap.columns:
        f[c] = state.get(c, np.nan)
    return f


def predict(type: str, neighborhood: str, open_date: datetime, source: str | None = None) -> dict:
    L = _load()
    open_date = pd.Timestamp(open_date)
    if neighborhood not in L["choices"]["neighborhoods"]:
        neighborhood = UNKNOWN_NEIGHBORHOOD
    source = source or L["meta"]["default_source"]

    base = baseline_lookup(L["baseline"], type)
    f = _features(type, neighborhood, open_date, source)
    p50b, p80b = L["p50"], L["p80"]
    use_ml = bool(p50b["use_model_by_type"].get(type, False))
    if use_ml:
        p50 = float(predict_days(p50b["model"], make_X(f, p50b["features"], p50b["levels"]))[0])
        p80_ml = float(predict_days(p80b["model"], make_X(f, p80b["features"], p80b["levels"]))[0])
        p80_ml_used = type not in P80_BASELINE_TYPES
        p80 = p80_ml if p80_ml_used else float(base["p80"])
    else:
        p50, p80, p80_ml_used = float(base["p50"]), float(base["p80"]), False
    p80 = max(p80, p50)

    target_days = None if pd.isna(f["target_days"].iat[0]) else float(f["target_days"].iat[0])
    p_ontime = None
    if type in ONTIME_TYPES and target_days is not None:
        ob = L["ontime"]
        p_ontime = float(ob["model"].predict_proba(make_X(f, ob["features"], ob["levels"]))[0, 1])

    return {
        "p50": round(p50, 3), "p80": round(p80, 3),
        "baseline_p50": round(float(base["p50"]), 3), "baseline_p80": round(float(base["p80"]), 3),
        "target_days": None if target_days is None else round(target_days, 3),
        "p_ontime": None if p_ontime is None else round(p_ontime, 3),
        "n_support": int(base["n"]) if base["level"] == "type" else 0,
        "used_model": "ml" if use_ml else "baseline",
        # extensions beyond the contract, safe to ignore
        "p80_used_model": "ml" if p80_ml_used else "baseline",
        "baseline_level": base["level"],
        "state_time": L["meta"]["state_time"],
    }


if __name__ == "__main__":
    from src.clean import DEMO_TYPES
    for t in DEMO_TYPES:
        print(t, predict(t, "Dorchester", datetime(2026, 10, 24, 9, 30)))

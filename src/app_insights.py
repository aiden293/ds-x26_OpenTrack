"""Extra lookups behind the web app's result page (beyond predict() and similar_cases()).

- meta():        request types with resident-friendly groups, featured flag, case counts,
                 and the out-of-sample "Allow longer" hit rate (models/app_accuracy.json)
- insights():    hit-rate details, time-to-close distribution, the neighborhood's own
                 history, and model estimates for the same request in every neighborhood
- cases_page():  every closed request of a type before the request date, with the page's
                 scope / sort / pagination applied server side

Distribution and local history use valid closures filed 2022-2025, the same basis as the
baseline. Closure notes go through src.similar.clean_reason (header removed, contacts redacted).
"""
from datetime import datetime
from functools import lru_cache
import json
import math

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from src.clean import UNKNOWN_NEIGHBORHOOD
from src.features import PROC
from src.similar import clean_reason
from src.train import MODELS

CASES = PROC / "cases_for_app.parquet"
HIST_YEARS = (2022, 2025)
SYSTEM_CHANGE = pd.Timestamp("2025-10-01")   # closures after this are incomplete in the data
SEASON_MONTHS = 2
NOTE_CHARS = 160
BINS = [0, 1, 2, 4, 7, 14, 30, np.inf]
BIN_LABELS = ["<1d", "1–2d", "2–4d", "4–7d", "1–2w", "2–4w", "30d+"]
SORTS = ("rel", "recent", "old", "short", "long")

# Resident-friendly groups over the city's "reason" field (type -> reason from baseline.json).
GROUPS = [
    ("Streets, sidewalks & traffic", ["Highway Maintenance", "Pothole", "Catchbasin", "Sidewalk Cover / Manhole",
                                      "Operations", "Signs & Signals", "Traffic Management & Engineering", "Fire Hydrant"]),
    ("Street lights", ["Street Lights"]),
    ("Trash, recycling & cleanliness", ["Sanitation", "Recycling", "Street Cleaning", "Code Enforcement",
                                        "Graffiti", "Needle Program"]),
    ("Parking, vehicles & bikes", ["Enforcement & Abandoned Vehicles", "Parking Complaints", "Abandoned Bicycle", "Boston Bikes"]),
    ("Parks & trees", ["Park Maintenance & Safety", "Trees", "Cemetery"]),
    ("Rodents, animals & environment", ["Environmental Services", "Animal Issues", "Air Pollution Control"]),
    ("Housing conditions", ["Housing"]),
    ("Construction & buildings", ["Building"]),
    ("Noise", ["Noise Disturbance", "Generic Noise Disturbance", "Neighborhood Services Issues"]),
    ("Food, health & stores", ["Health", "Weights and Measures"]),
    ("General & other", ["Administrative & General Requests", "Employee & General Comments", "General Request", "Quality of Life"]),
]
OTHER_GROUP = len(GROUPS) - 1


def _json(name: str) -> dict:
    return json.loads((MODELS / name).read_text())


@lru_cache(maxsize=1)
def meta() -> dict:
    choices = _json("choices.json")
    type_to_reason = _json("baseline.json")["type_to_reason"]
    acc = _json("app_accuracy.json")
    reason_group = {r: i for i, (_, reasons) in enumerate(GROUPS) for r in reasons}
    types = []
    for item in choices["types"]:
        a = acc.get(item["type"])
        types.append({**item,
                      "group": reason_group.get(type_to_reason.get(item["type"]), OTHER_GROUP),
                      "hit": a["model"] if a and a["n"] >= 100 else None,
                      "hit_n": a["n"] if a else 0,
                      "pct_unclosed_2025": a.get("pct_unclosed_2025") if a else None})
    return {
        "groups": [name for name, _ in GROUPS],
        "types": types,
        "neighborhoods": choices["neighborhoods"],
        "hit_overall": acc["_overall"]["model"],
        "stats": {"cases": pq.ParquetFile(CASES).metadata.num_rows if CASES.is_file() else None,
                  "types": len(types),
                  "neighborhoods": len(choices["neighborhoods"]),
                  "years": "2021–2025"},
    }


@lru_cache(maxsize=1)
def _by_type() -> dict[str, pd.DataFrame]:
    cols = ["case_enquiry_id", "type", "neighborhood", "open_dt", "closed_dt", "resolution_days",
            "closure_reason", "year"]
    df = pd.read_parquet(CASES, columns=cols)
    return {t: g.reset_index(drop=True) for t, g in df.groupby("type")}


def _hist_rows(type_: str) -> pd.DataFrame:
    g = _by_type().get(type_)
    return g[g["year"].between(*HIST_YEARS)] if g is not None else pd.DataFrame(columns=["resolution_days", "neighborhood"])


def hit_info(type_: str) -> dict:
    m = {t["type"]: t for t in meta()["types"]}.get(type_)
    overall = meta()["hit_overall"]
    if not m or m["hit"] is None:
        return {"rate": None, "n": m["hit_n"] if m else 0, "overall": overall, "unclosed_2025": None, "lower": None}
    u = m["pct_unclosed_2025"]
    return {"rate": m["hit"], "n": m["hit_n"], "overall": overall, "unclosed_2025": u,
            "lower": m["hit"] * (1 - u) if u is not None and u >= 0.15 else None}


def distribution(type_: str) -> dict:
    r = _hist_rows(type_)["resolution_days"]
    if r.empty:
        return {"labels": BIN_LABELS, "shares": [], "n": 0}
    counts = pd.cut(r, BINS, right=False, labels=BIN_LABELS).value_counts(sort=False)
    return {"labels": BIN_LABELS, "shares": [round(float(c) / len(r), 4) for c in counts], "n": int(len(r))}


def local_history(type_: str, neighborhood: str) -> dict:
    r = _hist_rows(type_)
    r = r.loc[r["neighborhood"] == neighborhood, "resolution_days"]
    return {"p50": float(r.median()) if len(r) >= 30 else None, "n": int(len(r))}


def compare(type_: str, open_date: datetime) -> list[dict]:
    """Model estimates for the same request, date and time in every named neighborhood."""
    from src.predict import predict
    local = _json("local_counts.json").get(type_, {})
    rows = []
    for nb in meta()["neighborhoods"]:
        if nb == UNKNOWN_NEIGHBORHOOD:
            continue
        p = predict(type_, nb, open_date)
        rows.append({"neighborhood": nb, "p50": p["p50"], "p80": p["p80"], "n": int(local.get(nb, 0))})
    return rows


def insights(type_: str, neighborhood: str, open_date: datetime) -> dict:
    return {"hit": hit_info(type_), "distribution": distribution(type_),
            "local": local_history(type_, neighborhood), "compare": compare(type_, open_date)}


def _month_distance(months: pd.Series, month: int) -> pd.Series:
    d = (months - month).abs()
    return np.minimum(d, 12 - d)


def cases_page(type_: str, neighborhood: str, open_date: datetime, scope: str = "nb",
               sort: str = "rel", page: int = 1, per_page: int = 5) -> dict:
    g = _by_type().get(type_)
    if g is None:
        return {"total": 0, "page": 1, "pages": 1, "cases": []}
    g = g[g["closed_dt"] < pd.Timestamp(open_date)]
    if scope == "nb":
        g = g[g["neighborhood"] == neighborhood]
    total = len(g)
    if total == 0:
        return {"total": 0, "page": 1, "pages": 1, "cases": []}
    # fastest 10% of the current view, as on the static page
    durations = np.sort(g["resolution_days"].values)
    fastest = durations[max(1, math.ceil(total * 0.1)) - 1]
    season = _month_distance(g["open_dt"].dt.month, pd.Timestamp(open_date).month) <= SEASON_MONTHS
    after = g["open_dt"] >= SYSTEM_CHANGE
    if sort == "rel":
        rank = after.astype(int) * 2 + (~season).astype(int)
        g = g.assign(_r=rank).sort_values(["_r", "open_dt"], ascending=[True, False])
    elif sort in ("recent", "old"):
        g = g.sort_values("open_dt", ascending=sort == "old")
    else:
        g = g.sort_values("resolution_days", ascending=sort == "short")
    pages = max(1, math.ceil(total / per_page))
    page = min(max(1, page), pages)
    rows = g.iloc[(page - 1) * per_page: page * per_page]
    out = []
    for _, r in rows.iterrows():
        out.append({
            "case_enquiry_id": str(r["case_enquiry_id"]),
            "neighborhood": r["neighborhood"],
            "open_dt": r["open_dt"].isoformat(), "closed_dt": r["closed_dt"].isoformat(),
            "resolution_days": float(r["resolution_days"]),
            "closure_reason": (clean_reason(pd.Series([r["closure_reason"]])).iat[0][:NOTE_CHARS]) or None,
            "same_neighborhood": r["neighborhood"] == neighborhood,
            "same_season": bool(season.loc[r.name]),
            "after_system_change": bool(after.loc[r.name]),
            "fastest": bool(r["resolution_days"] <= fastest),
        })
    return {"total": int(total), "page": page, "pages": pages, "cases": out}

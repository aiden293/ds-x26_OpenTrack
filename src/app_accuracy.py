"""Out-of-sample hit rates for the app's "Allow longer" (p80) estimate, per request type.

Usage: .venv/bin/python -m src.app_accuracy
Hit rate = share of 2025 valid closures that closed within the p80 the app would have
shown, using only data from before 2025 to build that p80:
  model: train-only models in models/eval/ with the app policy (ML where chosen on
         validation, baseline elsewhere, Street Light p80 from baseline)
  hist:  the static page's fallback, type x weekday p80 built from 2022-2024 closures
Requests never closed in the data are not counted (they have no duration); their share
is reported separately: pct_unclosed (2022-01..2025-09 filings) and pct_unclosed_2025
(the year the hit rate is measured on). Writes models/app_accuracy.json.
"""
import json

import joblib
import numpy as np
import pandas as pd

from src.features import PROC
from src.policy import P80_BASELINE_TYPES
from src.train import EVAL_DIR, MODELS, make_X, predict_baseline, predict_days, split

MIN_WEEKDAY_N = 30   # static page falls back to all-days p80 below this


def hist_p80(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    wd_tr, wd_te = train["open_dt"].dt.day_of_week, test["open_dt"].dt.day_of_week
    g = train.groupby([train["type"], wd_tr])["resolution_days"]
    by_wd = pd.DataFrame({"p80": g.quantile(0.8), "n": g.size()})
    by_wd = by_wd[by_wd.n >= MIN_WEEKDAY_N]["p80"]
    all_days = train.groupby("type")["resolution_days"].quantile(0.8)
    keys = list(zip(test["type"], wd_te))
    return np.array([by_wd.get(k, all_days.get(k[0], np.nan)) for k in keys])


def model_p80(test: pd.DataFrame) -> np.ndarray:
    base = json.loads((EVAL_DIR / "baseline.json").read_text())
    b80 = joblib.load(EVAL_DIR / "p80.joblib")
    use = test["type"].map(joblib.load(EVAL_DIR / "p50.joblib")["use_model_by_type"]).fillna(False).astype(bool)
    use &= ~test["type"].isin(P80_BASELINE_TYPES)
    ml = predict_days(b80["model"], make_X(test, b80["features"], b80["levels"]))
    return np.where(use.values, ml, predict_baseline(base, test)["p80"].values)


def main() -> None:
    feats = pd.read_parquet(PROC / "features.parquet")
    test = split(feats, "test").reset_index(drop=True)
    train_hist = feats[feats["year"].between(2022, 2024)]
    y = test["resolution_days"].values
    hit = pd.DataFrame({"type": test["type"],
                        "model": y <= model_p80(test),
                        "hist": y <= hist_p80(train_hist, test)})
    stats = json.loads((MODELS / "type_stats.json").read_text())
    cases = pd.read_parquet(PROC / "all_cases.parquet", columns=["type", "year", "is_closed"])
    c25 = cases[cases["year"] == 2025]
    unclosed25 = (1 - c25.groupby("type")["is_closed"].mean()).round(4).to_dict()
    out = {"_overall": {"model": float(hit["model"].mean()), "hist": float(hit["hist"].mean()),
                        "n": int(len(hit))}}
    for t, g in hit.groupby("type"):
        out[t] = {"model": round(float(g["model"].mean()), 3), "hist": round(float(g["hist"].mean()), 3),
                  "n": int(len(g)), "pct_unclosed": stats.get(t, {}).get("pct_unclosed"),
                  "pct_unclosed_2025": unclosed25.get(t)}
    (MODELS / "app_accuracy.json").write_text(json.dumps(out, indent=1))
    print(f"overall hit rate (2025, n={len(hit):,}): model {hit['model'].mean():.3f}, hist {hit['hist'].mean():.3f}")
    from src.clean import DEMO_TYPES
    for t in DEMO_TYPES:
        print(f"  {t[:30]:30s} {out[t]}")
    r = pd.DataFrame(out).T.drop("_overall")
    r = r[r.n >= 100]
    print(f"types with n>=100: {len(r)}; model hit rate range {r["model"].min():.2f}-{r["model"].max():.2f}, "
          f"median {r["model"].median():.2f}; hist median {r["hist"].median():.2f}")


if __name__ == "__main__":
    main()

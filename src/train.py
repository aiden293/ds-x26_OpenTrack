"""Phase 4-5: chronological split, baseline, quantile models, on-time classifier.

Usage: .venv/bin/python -m src.train
Split by open_dt year: train 2022-2023, validation 2024, test 2025 (test untouched here).
All model / feature-set choices are made on validation only. Writes:
  models/eval/{baseline.json,p50.joblib,p80.joblib,ontime.joblib} (train-only)
  reports/val_metrics.json
Phase 6 evaluates these on test; src/export.py refits final app models into models/.
"""
from pathlib import Path
import json
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import brier_score_loss, mean_absolute_error, mean_pinball_loss, roc_auc_score

from src.clean import DEMO_TYPES
from src.features import CAT_FEATURES, FEATURES, PROC, build_features

ROOT = Path(__file__).resolve().parents[1]
MODELS, REPORTS = ROOT / "models", ROOT / "reports"
EVAL_DIR = MODELS / "eval"  # train-only models evaluated on test; final app models live in MODELS

SPLITS = {"train": (2022, 2023), "val": (2024, 2024), "test": (2025, 2025)}
QUANTILES = {"p50": 0.5, "p80": 0.8}
MIN_TYPE_N, MIN_REASON_N = 30, 30   # baseline fallback thresholds
MIN_VAL_N = 100                      # per-type model-vs-baseline decision needs this many val cases
FEATURE_SETS = {
    "all": FEATURES,
    "no_backlog_type": [f for f in FEATURES if f != "backlog_type"],
}
# backlog_type drifts upward with never-closed cases (Phase 3), so test values fall outside
# the training range. Prefer the set without it unless "all" is better by more than TIE_TOL.
PREFERRED_SET, TIE_TOL = "no_backlog_type", 0.01
PARAM_GRID = [
    dict(learning_rate=0.1, max_iter=300, max_leaf_nodes=31, min_samples_leaf=20),
    dict(learning_rate=0.1, max_iter=300, max_leaf_nodes=63, min_samples_leaf=100),
    dict(learning_rate=0.05, max_iter=600, max_leaf_nodes=63, min_samples_leaf=100),
    dict(learning_rate=0.05, max_iter=600, max_leaf_nodes=127, min_samples_leaf=200),
]


def split(df: pd.DataFrame, name: str) -> pd.DataFrame:
    lo, hi = SPLITS[name]
    return df[df["year"].between(lo, hi)]


# ---------- baseline ----------
def fit_baseline(train: pd.DataFrame) -> dict:
    def table(key, min_n):
        g = train.groupby(key)["resolution_days"]
        t = pd.DataFrame({"p50": g.quantile(0.5), "p80": g.quantile(0.8), "n": g.size()})
        return {k: r.to_dict() for k, r in t[t.n >= min_n].iterrows()}
    y = train["resolution_days"]
    return {
        "type": table("type", MIN_TYPE_N),
        "reason": table("reason", MIN_REASON_N),
        "global": {"p50": y.quantile(0.5), "p80": y.quantile(0.8), "n": len(y)},
        "type_to_reason": train.groupby("type")["reason"].agg(lambda s: s.mode().iat[0]).to_dict(),
    }


def baseline_lookup(base: dict, type_: str, reason: str | None = None) -> dict:
    """Return {"p50", "p80", "n", "level"} with type -> reason -> global fallback."""
    if type_ in base["type"]:
        return base["type"][type_] | {"level": "type"}
    reason = reason or base["type_to_reason"].get(type_)
    if reason in base["reason"]:
        return base["reason"][reason] | {"level": "reason"}
    return base["global"] | {"level": "global"}


def predict_baseline(base: dict, df: pd.DataFrame) -> pd.DataFrame:
    rows = [baseline_lookup(base, t, r) for t, r in zip(df["type"], df["reason"])]
    return pd.DataFrame(rows, index=df.index)


# ---------- ML ----------
def category_levels(train: pd.DataFrame) -> dict:
    return {c: sorted(train[c].dropna().unique()) for c in CAT_FEATURES}


def make_X(df: pd.DataFrame, features: list[str], levels: dict) -> pd.DataFrame:
    X = df[features].copy()
    for c in CAT_FEATURES:
        if c in X:  # unseen levels become NaN (missing)
            X[c] = pd.Categorical(X[c].where(X[c].isin(levels[c])), categories=levels[c])
    return X


def fit_quantile(X, y_days, q, params) -> HistGradientBoostingRegressor:
    m = HistGradientBoostingRegressor(loss="quantile", quantile=q, categorical_features="from_dtype",
                                      early_stopping=False, random_state=0, **params)
    return m.fit(X, np.log1p(y_days))


def predict_days(model, X) -> np.ndarray:
    return np.clip(np.expm1(model.predict(X)), 0, None)


def scores(y, p50, p80) -> dict:
    return {
        "n": int(len(y)),
        "p50_mae": float(mean_absolute_error(y, p50)),
        "p50_medae": float(np.median(np.abs(y - p50))),
        "p50_pinball": float(mean_pinball_loss(y, p50, alpha=0.5)),
        "p80_coverage": float(np.mean(y <= p80)),
        "p80_pinball": float(mean_pinball_loss(y, p80, alpha=0.8)),
    }


def by_type(df, p50, p80) -> dict:
    out = {"overall": scores(df["resolution_days"].values, p50, p80)}
    for t in DEMO_TYPES:
        m = (df["type"] == t).values
        out[t] = scores(df["resolution_days"].values[m], p50[m], p80[m])
    return out


# ---------- on-time classifier ----------
def ontime_data(feats: pd.DataFrame) -> pd.DataFrame:
    """Valid closures with a target, plus still-open cases whose target already passed
    at the data snapshot (known overdue). Excluded closures (duplicate etc.) are left out."""
    cases = pd.read_parquet(PROC / "all_cases.parquet")
    snapshot = cases["closed_dt"].max()
    clean = pd.read_parquet(PROC / "clean.parquet")
    closed = feats[feats["target_days"].notna()].copy()
    closed["label"] = (closed["closed_dt"] <= closed["target_dt"]).astype(int)
    op = cases[~cases["is_closed"] & cases["target_dt"].notna() & (cases["target_dt"] < snapshot)]
    of = build_features(op, cases[["type", "neighborhood", "open_dt", "closed_dt"]], clean)
    of[["year", "open_dt"]] = op[["year", "open_dt"]].values
    of["label"] = 0
    return pd.concat([closed, of], ignore_index=True), len(of), snapshot


def main() -> None:
    feats = pd.read_parquet(PROC / "features.parquet")
    train, val = split(feats, "train"), split(feats, "val")
    print(f"train={len(train):,} val={len(val):,} test={len(split(feats, 'test')):,} (test untouched)")
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    metrics = {"split": SPLITS, "n": {"train": len(train), "val": len(val)}}

    # Baseline
    base = fit_baseline(train)
    bp = predict_baseline(base, val)
    metrics["val_baseline"] = by_type(val, bp["p50"].values, bp["p80"].values)
    metrics["baseline_levels_val"] = bp["level"].value_counts().to_dict()
    (EVAL_DIR / "baseline.json").write_text(json.dumps(base, indent=1, default=float))
    print("baseline val overall:", {k: round(v, 3) for k, v in metrics["val_baseline"]["overall"].items()})

    # Quantile grid on validation: feature set x params, chosen per quantile by val pinball
    levels = category_levels(train)
    grid, best = [], {}  # best[feature_set][quantile]
    for fs_name, fs in FEATURE_SETS.items():
        best[fs_name] = {}
        Xtr, Xva = make_X(train, fs, levels), make_X(val, fs, levels)
        for i, params in enumerate(PARAM_GRID):
            for qname, q in QUANTILES.items():
                t0 = time.time()
                m = fit_quantile(Xtr, train["resolution_days"], q, params)
                pred = predict_days(m, Xva)
                y = val["resolution_days"].values
                row = {"quantile": qname, "features": fs_name, "params": i,
                       "pinball": float(mean_pinball_loss(y, pred, alpha=q)),
                       "coverage": float(np.mean(y <= pred)), "sec": round(time.time() - t0, 1)}
                grid.append(row)
                print(row)
                b = best[fs_name]
                if qname not in b or row["pinball"] < b[qname]["row"]["pinball"]:
                    b[qname] = {"row": row, "model": m, "pred": pred, "features": fs}
    metrics["val_grid"] = grid

    def total(fs_name):
        return sum(best[fs_name][q]["row"]["pinball"] for q in QUANTILES)
    winner = min(best, key=total)
    if total(PREFERRED_SET) <= total(winner) * (1 + TIE_TOL):
        winner = PREFERRED_SET
    metrics["feature_set_choice"] = {"totals": {k: total(k) for k in best}, "chosen": winner,
                                     "rule": f"prefer {PREFERRED_SET} if within {TIE_TOL:.0%}"}
    print("feature set:", metrics["feature_set_choice"])
    best = best[winner]

    p50, p80 = best["p50"]["pred"], np.maximum(best["p80"]["pred"], best["p50"]["pred"])
    metrics["val_model"] = by_type(val, p50, p80)
    metrics["chosen"] = {q: {**b["row"], "params": PARAM_GRID[b["row"]["params"]]} for q, b in best.items()}

    # Per-type choice on validation: use ML only where it beats baseline on both pinball losses
    use_model = {}
    vb = val.assign(m50=p50, m80=p80, b50=bp["p50"].values, b80=bp["p80"].values)
    for t, g in vb.groupby("type"):
        if len(g) < MIN_VAL_N:
            continue
        y = g["resolution_days"]
        ml = mean_pinball_loss(y, g.m50, alpha=0.5) + mean_pinball_loss(y, g.m80, alpha=0.8)
        bl = mean_pinball_loss(y, g.b50, alpha=0.5) + mean_pinball_loss(y, g.b80, alpha=0.8)
        use_model[t] = bool(ml < bl)
    metrics["use_model_by_type"] = use_model
    for qname, b in best.items():
        joblib.dump({"model": b["model"], "features": b["features"], "levels": levels,
                     "use_model_by_type": use_model, "fit_years": SPLITS["train"]},
                    EVAL_DIR / f"{qname}.joblib")

    # On-time classifier (features from the chosen p50 set)
    data, n_open, snapshot = ontime_data(feats)
    fs = best["p50"]["features"]
    ctr, cva = split(data, "train"), split(data, "val")
    clf = HistGradientBoostingClassifier(categorical_features="from_dtype", early_stopping=False,
                                         random_state=0, **PARAM_GRID[1])
    clf.fit(make_X(ctr, fs, levels), ctr["label"])
    prob = clf.predict_proba(make_X(cva, fs, levels))[:, 1]
    metrics["val_ontime"] = {
        "snapshot": str(snapshot), "open_overdue_added": n_open,
        "train_pos_rate": float(ctr["label"].mean()), "val_pos_rate": float(cva["label"].mean()),
        "auc": float(roc_auc_score(cva["label"], prob)), "brier": float(brier_score_loss(cva["label"], prob)),
        "brier_constant": float(brier_score_loss(cva["label"], np.full(len(cva), ctr["label"].mean()))),
    }
    joblib.dump({"model": clf, "features": fs, "levels": levels, "fit_years": SPLITS["train"]},
                EVAL_DIR / "ontime.joblib")

    (REPORTS / "val_metrics.json").write_text(json.dumps(metrics, indent=1, default=str))
    print(json.dumps({k: metrics[k] for k in ["chosen", "val_ontime"]}, indent=1, default=str))


if __name__ == "__main__":
    main()

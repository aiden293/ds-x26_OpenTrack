"""Recalibrate the on-time classifier with recent (pre-test) data and re-check on 2025 test.

Usage: .venv/bin/python -m src.recalibrate
Calibrators are fit on 2024 only; 2025 test is used for evaluation only.
  A original      train-only classifier (Phase 5)
  B platt_val     A + logistic calibration on logit(p), fit on 2024
  C isotonic_val  A + isotonic calibration, fit on 2024
  D refit_platt   classifier refit on 2022..2024-06, Platt fit on 2024-07..12
B and C are monotone, so their AUC equals A's; only D can change ranking.
Writes reports/recalibration.json and reports/calibration_recal.png.
"""
import json

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from src.clean import DEMO_TYPES
from src.evaluate import BLUE, GRAY, INK, INK2, ORANGE, style
from src.features import PROC
from src.train import MODELS, PARAM_GRID, REPORTS, make_X, ontime_data, split

AQUA, YELLOW = "#1baf7a", "#eda100"  # categorical slots 3, 4
EPS = 1e-6


def logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def fit_platt(p, y):
    return LogisticRegression(C=1e6).fit(logit(p).reshape(-1, 1), y)


def apply_platt(cal, p):
    return cal.predict_proba(logit(p).reshape(-1, 1))[:, 1]


def score(y, p, types) -> dict:
    out = {"auc": roc_auc_score(y, p), "brier": brier_score_loss(y, p), "log_loss": log_loss(y, p),
           "mean_pred": float(p.mean()), "pos_rate": float(y.mean()),
           "ece": ece(y, p)}
    out["auc_by_demo_type"] = {t[:14]: roc_auc_score(y[m], p[m]) if len(set(y[m])) > 1 else None
                               for t in DEMO_TYPES for m in [types == t]}
    return out


def ece(y, p, bins=10) -> float:
    """Expected calibration error over probability deciles."""
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, bins - 1)
    return float(sum(abs(y[idx == b].mean() - p[idx == b].mean()) * (idx == b).mean()
                     for b in range(bins) if (idx == b).any()))


def main() -> None:
    feats = pd.read_parquet(PROC / "features.parquet")
    data, _, _ = ontime_data(feats)
    data["month"] = pd.to_datetime(data["open_dt"]).dt.month
    orig = joblib.load(MODELS / "ontime.joblib")
    fs, lv = orig["features"], orig["levels"]
    val, test = split(data, "val"), split(data, "test")
    yv, yt, types = val["label"].values, test["label"].values, test["type"].values

    pv = orig["model"].predict_proba(make_X(val, fs, lv))[:, 1]
    pt = orig["model"].predict_proba(make_X(test, fs, lv))[:, 1]
    preds = {"A original": pt}
    preds["B platt_val"] = apply_platt(fit_platt(pv, yv), pt)
    preds["C isotonic_val"] = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(pv, yv).predict(pt)

    fit_part = data[data["year"].between(2022, 2023) | ((data["year"] == 2024) & (data["month"] <= 6))]
    cal_part = data[(data["year"] == 2024) & (data["month"] > 6)]
    clf = HistGradientBoostingClassifier(categorical_features="from_dtype", early_stopping=False,
                                         random_state=0, **PARAM_GRID[1])
    clf.fit(make_X(fit_part, fs, lv), fit_part["label"])
    pc = clf.predict_proba(make_X(cal_part, fs, lv))[:, 1]
    platt_d = fit_platt(pc, cal_part["label"].values)
    preds["D refit_platt"] = apply_platt(platt_d, clf.predict_proba(make_X(test, fs, lv))[:, 1])

    res = {"n_test": len(test), "pos_rate_val_2024": float(yv.mean()),
           "pos_rate_2024H2": float(cal_part["label"].mean()), "pos_rate_test_2025": float(yt.mean()),
           "brier_constant_2024H2_rate": brier_score_loss(yt, np.full(len(yt), cal_part["label"].mean())),
           "variants": {k: score(yt, p, types) for k, p in preds.items()}}
    # Diagnosis (post hoc, test-informed): the 0.85-0.93 dip is mostly Parking Enforcement,
    # whose on-time rate fell from 0.46 (2024) to 0.24 (2025). Score without it and on demo types.
    res["subsets"] = {}
    for name, m in [("excl_parking", types != "Parking Enforcement"), ("demo_types", np.isin(types, DEMO_TYPES))]:
        cm = (cal_part["type"] != "Parking Enforcement") if name == "excl_parking" else cal_part["type"].isin(DEMO_TYPES)
        res["subsets"][name] = {
            "n": int(m.sum()), "pos_rate": float(yt[m].mean()),
            "brier_constant_2024H2_rate": brier_score_loss(yt[m], np.full(m.sum(), cal_part.loc[cm, "label"].mean())),
            **{k: {"auc": roc_auc_score(yt[m], p[m]), "brier": brier_score_loss(yt[m], p[m]),
                   "ece": ece(yt[m], p[m]), "mean_pred": float(p[m].mean())}
               for k, p in preds.items() if k[0] in "AD"}}
    (REPORTS / "recalibration.json").write_text(json.dumps(res, indent=1, default=float))
    joblib.dump({"model": clf, "platt": platt_d, "features": fs, "levels": lv,
                 "fit_years": "2022-01..2024-06", "calib": "2024-07..12"},
                MODELS / "ontime_recal_candidate.joblib")

    fig, ax = plt.subplots(figsize=(5.6, 5.2), dpi=150)
    style(ax)
    ax.plot([0, 1], [0, 1], color=GRAY, linewidth=1, linestyle="--", label="Perfect calibration")
    for (name, p), c in zip(preds.items(), [BLUE, ORANGE, AQUA, YELLOW]):
        frac, mp = calibration_curve(yt, p, n_bins=10, strategy="quantile")
        ax.plot(mp, frac, color=c, linewidth=2, marker="o", markersize=6,
                markeredgecolor="white", markeredgewidth=1.5, label=name)
    ax.set_xlabel("Predicted probability of closing by target date", color=INK2)
    ax.set_ylabel("Observed share closed on time", color=INK2)
    ax.set_title("On-time calibration on 2025 test, by recalibration", color=INK, loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK2, loc="upper left")
    ax.set_xlim(0, 1), ax.set_ylim(0, 1)
    fig.tight_layout(), fig.savefig(REPORTS / "calibration_recal.png"), plt.close(fig)

    print(f"pos rate: val2024={res['pos_rate_val_2024']:.3f} 2024H2={res['pos_rate_2024H2']:.3f} "
          f"test2025={res['pos_rate_test_2025']:.3f}; Brier of constant(2024H2 rate)={res['brier_constant_2024H2_rate']:.4f}")
    for k, s in res["variants"].items():
        print(f"{k:15s} AUC={s['auc']:.3f} Brier={s['brier']:.4f} logloss={s['log_loss']:.3f} "
              f"ECE={s['ece']:.3f} mean_pred={s['mean_pred']:.3f}  "
              f"AUC/type={ {t: round(v, 3) for t, v in s['auc_by_demo_type'].items()} }")
    for name, s in res["subsets"].items():
        print(f"\n{name}: n={s['n']:,} pos={s['pos_rate']:.3f} const Brier={s['brier_constant_2024H2_rate']:.4f}")
        for k in ["A original", "D refit_platt"]:
            print(f"  {k:15s} " + " ".join(f"{m}={s[k][m]:.3f}" for m in ["auc", "brier", "ece", "mean_pred"]))


if __name__ == "__main__":
    main()

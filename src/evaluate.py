"""Phase 6: evaluate train-only models on the 2025 test set (first and only look at test).

Usage: .venv/bin/python -m src.evaluate
Writes reports/metrics.json, reports/calibration.png, reports/importance.png.
Three predictors are compared: baseline, ML, and "app" (ML where validation chose it,
baseline elsewhere; the choice was fixed on 2024 validation, not on test).
"""
import json

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.inspection import permutation_importance
from sklearn.metrics import brier_score_loss, mean_absolute_error, mean_pinball_loss, roc_auc_score

from src.clean import DEMO_TYPES
from src.train import (EVAL_DIR, REPORTS, by_type, make_X, ontime_data, predict_baseline,
                       predict_days, split)
from src.features import PROC

BLUE, ORANGE, GRAY, INK, INK2 = "#2a78d6", "#eb6834", "#8a8984", "#0b0b0b", "#52514e"
N_BOOT, IMP_ROWS, IMP_REPEATS = 500, 40_000, 5


def predictions(test: pd.DataFrame) -> dict:
    base = json.loads((EVAL_DIR / "baseline.json").read_text())
    b50, b80 = joblib.load(EVAL_DIR / "p50.joblib"), joblib.load(EVAL_DIR / "p80.joblib")
    bp = predict_baseline(base, test)
    m50 = predict_days(b50["model"], make_X(test, b50["features"], b50["levels"]))
    m80 = np.maximum(predict_days(b80["model"], make_X(test, b80["features"], b80["levels"])), m50)
    use = test["type"].map(b50["use_model_by_type"]).fillna(False).astype(bool).values
    return {
        "baseline": (bp["p50"].values, bp["p80"].values),
        "model": (m50, m80),
        "app": (np.where(use, m50, bp["p50"].values), np.where(use, m80, bp["p80"].values)),
    }, use


def paired_bootstrap(y, a50, a80, b50, b80, rng) -> dict:
    """95% CI of (model - baseline) for p50 MAE and p80 pinball; negative = model better."""
    d50 = np.abs(y - a50) - np.abs(y - b50)
    pin = lambda p: np.where(y >= p, 0.8 * (y - p), 0.2 * (p - y))
    d80 = pin(a80) - pin(b80)
    idx = rng.integers(0, len(y), (N_BOOT, len(y)))
    out = {}
    for name, d in [("p50_mae_diff", d50), ("p80_pinball_diff", d80)]:
        boots = d[idx].mean(axis=1)
        out[name] = {"mean": float(d.mean()), "ci95": [float(np.quantile(boots, 0.025)),
                                                     float(np.quantile(boots, 0.975))]}
    return out


def style(ax):
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(GRAY)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(color="#e6e5e1", linewidth=0.8)
    ax.set_axisbelow(True)


def plot_calibration(y, prob, path) -> list:
    frac, mean_pred = calibration_curve(y, prob, n_bins=10, strategy="quantile")
    fig, ax = plt.subplots(figsize=(5.2, 5), dpi=150)
    style(ax)
    ax.plot([0, 1], [0, 1], color=GRAY, linewidth=1, linestyle="--", label="Perfect calibration")
    ax.plot(mean_pred, frac, color=BLUE, linewidth=2, marker="o", markersize=6,
            markeredgecolor="white", markeredgewidth=1.5, label="On-time classifier")
    ax.set_xlabel("Predicted probability of closing by target date", color=INK2)
    ax.set_ylabel("Observed share closed on time", color=INK2)
    ax.set_title("On-time calibration, 2025 test (deciles)", color=INK, loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK2)
    ax.set_xlim(0, 1), ax.set_ylim(0, 1)
    fig.tight_layout(), fig.savefig(path), plt.close(fig)
    return [{"mean_pred": float(p), "observed": float(f)} for p, f in zip(mean_pred, frac)]


def plot_importance(bundle, test, path, rng) -> dict:
    sub = test.sample(min(IMP_ROWS, len(test)), random_state=0)
    X = make_X(sub, bundle["features"], bundle["levels"])
    r = permutation_importance(bundle["model"], X, np.log1p(sub["resolution_days"]),
                               scoring="neg_mean_absolute_error", n_repeats=IMP_REPEATS,
                               random_state=0, n_jobs=-1)
    imp = pd.DataFrame({"mean": r.importances_mean, "std": r.importances_std},
                       index=bundle["features"]).sort_values("mean")
    fig, ax = plt.subplots(figsize=(6.4, 5.2), dpi=150)
    style(ax)
    ax.grid(axis="y", visible=False)
    ax.barh(imp.index, imp["mean"], xerr=imp["std"], color=BLUE, height=0.6,
            error_kw={"ecolor": GRAY, "elinewidth": 1})
    ax.set_xlabel("Increase in MAE of log1p(days) when shuffled", color=INK2)
    ax.set_title("Global permutation importance, p50 model, 2025 test", color=INK, loc="left", fontsize=11)
    fig.tight_layout(), fig.savefig(path), plt.close(fig)
    return imp["mean"].sort_values(ascending=False).round(4).to_dict()


def main() -> None:
    rng = np.random.default_rng(0)
    feats = pd.read_parquet(PROC / "features.parquet")
    test = split(feats, "test").reset_index(drop=True)
    y = test["resolution_days"].values
    preds, use = predictions(test)
    metrics = {"test_years": [2025], "n_test": len(test),
               "share_test_rows_using_ml_in_app": float(use.mean()),
               "note": "Test = valid closures only; ~25% of 2025 cases were still open at snapshot."}
    for name, (p50, p80) in preds.items():
        metrics[f"test_{name}"] = by_type(test, p50, p80)

    metrics["bootstrap_model_vs_baseline"] = {}
    for t in ["overall"] + DEMO_TYPES:
        m = np.ones(len(test), bool) if t == "overall" else (test["type"] == t).values
        metrics["bootstrap_model_vs_baseline"][t] = paired_bootstrap(
            y[m], *[p[m] for p in preds["model"]], *[p[m] for p in preds["baseline"]], rng)

    months = test["open_dt"].dt.month.values
    metrics["test_by_month"] = {
        int(mo): {"n": int((months == mo).sum()),
                  "model_p80_coverage": float(np.mean(y[months == mo] <= preds["model"][1][months == mo])),
                  "baseline_p80_coverage": float(np.mean(y[months == mo] <= preds["baseline"][1][months == mo])),
                  "model_p50_mae": float(mean_absolute_error(y[months == mo], preds["model"][0][months == mo])),
                  "baseline_p50_mae": float(mean_absolute_error(y[months == mo], preds["baseline"][0][months == mo]))}
        for mo in range(1, 13)}

    # On-time classifier on 2025 (closures + open cases already past target at snapshot)
    clf = joblib.load(EVAL_DIR / "ontime.joblib")
    data, _, snapshot = ontime_data(feats)
    ct = split(data, "test")
    prob = clf["model"].predict_proba(make_X(ct, clf["features"], clf["levels"]))[:, 1]
    lab = ct["label"].values
    metrics["test_ontime"] = {
        "n": len(ct), "pos_rate": float(lab.mean()), "snapshot": str(snapshot),
        "auc": float(roc_auc_score(lab, prob)), "brier": float(brier_score_loss(lab, prob)),
        "brier_constant_train_rate": float(brier_score_loss(lab, np.full(len(lab), 0.7821))),
        "mean_predicted": float(prob.mean()),
        "calibration": plot_calibration(lab, prob, REPORTS / "calibration.png"),
        "auc_by_demo_type": {t: float(roc_auc_score(lab[m], prob[m])) if len(set(lab[m])) > 1 else None
                             for t in DEMO_TYPES for m in [(ct["type"] == t).values]},
    }

    metrics["permutation_importance_p50"] = plot_importance(
        joblib.load(EVAL_DIR / "p50.joblib"), test, REPORTS / "importance.png", rng)
    metrics["ml_beats_baseline_on_test"] = {
        t: {"p50_mae": metrics["test_model"][t]["p50_mae"] < metrics["test_baseline"][t]["p50_mae"],
            "p80_pinball": metrics["test_model"][t]["p80_pinball"] < metrics["test_baseline"][t]["p80_pinball"]}
        for t in ["overall"] + DEMO_TYPES}

    (REPORTS / "metrics.json").write_text(json.dumps(metrics, indent=1, default=float))
    print_summary(metrics)


def print_summary(m: dict) -> None:
    print(f"test n={m['n_test']:,}  rows using ML in app={m['share_test_rows_using_ml_in_app']:.1%}")
    hdr = f"{'type':24s} {'n':>7s} | {'p50 MAE b/m/app':>20s} | {'medAE b/m':>11s} | {'p80 pin b/m/app':>20s} | {'cov b/m/app':>17s}"
    print(hdr)
    for t in ["overall"] + DEMO_TYPES:
        b, mo, a = m["test_baseline"][t], m["test_model"][t], m["test_app"][t]
        print(f"{t[:24]:24s} {b['n']:7d} | {b['p50_mae']:6.2f} {mo['p50_mae']:6.2f} {a['p50_mae']:6.2f} | "
              f"{b['p50_medae']:5.2f} {mo['p50_medae']:5.2f} | {b['p80_pinball']:6.2f} {mo['p80_pinball']:6.2f} "
              f"{a['p80_pinball']:6.2f} | {b['p80_coverage']:.3f} {mo['p80_coverage']:.3f} {a['p80_coverage']:.3f}")
    print("\nbootstrap (model - baseline), 95% CI:")
    for t, d in m["bootstrap_model_vs_baseline"].items():
        print(f"  {t[:24]:24s} p50 MAE {d['p50_mae_diff']['mean']:+.3f} {np.round(d['p50_mae_diff']['ci95'], 3)}"
              f"  p80 pin {d['p80_pinball_diff']['mean']:+.3f} {np.round(d['p80_pinball_diff']['ci95'], 3)}")
    o = m["test_ontime"]
    print(f"\nontime: n={o['n']:,} pos={o['pos_rate']:.3f} mean_pred={o['mean_predicted']:.3f} "
          f"AUC={o['auc']:.3f} Brier={o['brier']:.3f} (const {o['brier_constant_train_rate']:.3f})")
    print("ontime AUC by demo type:", {k[:14]: round(v, 3) if v else v for k, v in o["auc_by_demo_type"].items()})
    print("\nmonthly p80 coverage model/baseline:",
          {k: (round(v["model_p80_coverage"], 2), round(v["baseline_p80_coverage"], 2)) for k, v in m["test_by_month"].items()})
    print("\ntop features:", dict(list(m["permutation_importance_p50"].items())[:8]))


if __name__ == "__main__":
    main()

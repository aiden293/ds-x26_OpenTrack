"""Phase 8: neighborhood gaps not explained by type, timing, and backlog.

Usage: .venv/bin/python -m src.equity
A p50 model is trained on 2022-2023 WITHOUT neighborhood or any neighborhood-level
feature (backlog_type_nbhd, roll_*_type_nbhd), using the validation-chosen p50 settings.
On the 2025 test set, residual = actual - predicted resolution days, summarized per
neighborhood with bootstrap 95% intervals. Writes reports/equity.csv, reports/equity.png.

Wording: a positive residual means requests there took longer than the model expected
from type, timing, source, SLA and citywide queue alone. This is a gap not explained by
those factors, not evidence of discrimination or of its cause. Reporting bias (who reports,
how often) and censoring (still-open cases are missing) can both create or hide gaps.
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.clean import DEMO_TYPES, UNKNOWN_NEIGHBORHOOD
from src.evaluate import BLUE, GRAY, INK, INK2, style
from src.features import FEATURES, PROC
from src.train import REPORTS, category_levels, fit_quantile, make_X, predict_days, split

NBHD_FEATURES = {"neighborhood", "backlog_type_nbhd", "roll_p50_type_nbhd", "roll_n_type_nbhd"}
N_BOOT, MIN_N = 1000, 200


def boot_ci(x: np.ndarray, stat, rng) -> tuple[float, float]:
    idx = rng.integers(0, len(x), (N_BOOT, len(x)))
    b = stat(x[idx], axis=1)
    return float(np.quantile(b, 0.025)), float(np.quantile(b, 0.975))


def summarize(df: pd.DataFrame, rng) -> pd.DataFrame:
    rows = []
    for nb, g in df.groupby("neighborhood"):
        r = g["residual"].values
        lo_med, hi_med = boot_ci(r, np.median, rng)
        lo_mean, hi_mean = boot_ci(r, np.mean, rng)
        rows.append({"neighborhood": nb, "n": len(r),
                     "median_residual": float(np.median(r)), "median_lo": lo_med, "median_hi": hi_med,
                     "mean_residual": float(r.mean()), "mean_lo": lo_mean, "mean_hi": hi_mean,
                     "share_longer_than_predicted": float((r > 0).mean())})
    return pd.DataFrame(rows)


def plot(tab: pd.DataFrame, path, subtitle: str, citywide: dict) -> None:
    """Two panels sharing the neighborhood axis: median (typical request) and mean (long tail).
    A p50 model on right-skewed durations has a positive mean residual everywhere, so the
    citywide value (dashed) is the reference, not zero."""
    t = tab[(tab.n >= MIN_N) & (tab.neighborhood != UNKNOWN_NEIGHBORHOOD)].sort_values("mean_residual")
    fig, axes = plt.subplots(1, 2, figsize=(10, 6.4), dpi=150, sharey=True,
                             gridspec_kw={"width_ratios": [1, 1.3]})
    y = np.arange(len(t))
    for ax, stat, label in [(axes[0], "median", "Median residual, days\n(typical request)"),
                            (axes[1], "mean", "Mean residual, days\n(pulled by long cases)")]:
        style(ax)
        ax.grid(axis="y", visible=False)
        ax.axvline(0, color=GRAY, linewidth=1)
        ax.axvline(citywide[stat], color=INK2, linewidth=1, linestyle="--")
        ax.text(citywide[stat], len(t) - 0.4, f" citywide {citywide[stat]:.2f}", color=INK2, fontsize=8)
        ax.hlines(y, t[f"{stat}_lo"], t[f"{stat}_hi"], color=GRAY, linewidth=1.5)
        ax.plot(t[f"{stat}_residual"], y, "o", color=BLUE, markersize=7, markeredgecolor="white", markeredgewidth=1.5)
        ax.set_xlabel(label, color=INK2, fontsize=9)
    axes[0].set_yticks(y, [f"{nb}  (n={n:,})" for nb, n in zip(t.neighborhood, t.n)], fontsize=8.5)
    fig.suptitle("Neighborhood gap not explained by type, timing and backlog (actual - predicted; right = slower)",
                 color=INK, x=0.01, ha="left", fontsize=11)
    fig.text(0.01, 0.925, subtitle, color=INK2, fontsize=8.5, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.92)), fig.savefig(path), plt.close(fig)


def main() -> None:
    rng = np.random.default_rng(0)
    feats = pd.read_parquet(PROC / "features.parquet")
    nb = pd.read_parquet(PROC / "clean.parquet", columns=["case_enquiry_id", "neighborhood"])
    feats = feats.drop(columns="neighborhood").merge(nb, on="case_enquiry_id")
    train, test = split(feats, "train"), split(feats, "test").copy()
    fs = [f for f in FEATURES if f not in NBHD_FEATURES]
    params = json.loads((REPORTS / "val_metrics.json").read_text())["chosen"]["p50"]["params"]
    levels = category_levels(train)
    model = fit_quantile(make_X(train, fs, levels), train["resolution_days"], 0.5, params)
    test["pred"] = predict_days(model, make_X(test, fs, levels))
    test["residual"] = test["resolution_days"] - test["pred"]

    tab = summarize(test, rng)
    cases = pd.read_parquet(PROC / "all_cases.parquet", columns=["neighborhood", "year", "is_closed"])
    c25 = cases[cases.year == 2025]
    tab = tab.merge((100 * (~c25.is_closed)).groupby(c25.neighborhood).mean().rename("pct_open_2025").reset_index(),
                    on="neighborhood", how="left")
    demo = summarize(test[test.type.isin(DEMO_TYPES)], rng)[["neighborhood", "n", "median_residual", "median_lo", "median_hi"]]
    tab = tab.merge(demo.add_prefix("demo_").rename(columns={"demo_neighborhood": "neighborhood"}), on="neighborhood", how="left")
    tab = tab.sort_values("median_residual", ascending=False)
    tab.round(3).to_csv(REPORTS / "equity.csv", index=False)
    plot(tab, REPORTS / "equity.png", f"2025 test, all request types, p50 model without neighborhood features; "
                                      f"95% bootstrap CI; n >= {MIN_N}",
         {"median": float(test["residual"].median()), "mean": float(test["residual"].mean())})

    overall = test["residual"]
    print(f"features used: {fs}")
    print(f"test n={len(test):,}; overall median residual={overall.median():.3f}, mean={overall.mean():.2f}")
    cols = ["neighborhood", "n", "median_residual", "median_lo", "median_hi", "mean_residual",
            "share_longer_than_predicted", "pct_open_2025", "demo_n", "demo_median_residual", "demo_median_lo", "demo_median_hi"]
    pd.set_option("display.width", 250)
    print(tab[cols].round(2).to_string(index=False))


if __name__ == "__main__":
    main()

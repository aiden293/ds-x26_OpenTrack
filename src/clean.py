"""Phase 2: build resolution_days target, merge neighborhood names, flag invalid closures.

Usage: .venv/bin/python -m src.clean
Reads data/processed/all_raw.parquet. Writes:
  data/processed/all_cases.parquet  every case (incl. open / excluded), for backlog
  data/processed/clean.parquet      closed, valid closures with resolution_days > 0
  reports/phase2_report.txt
"""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
REPORT = ROOT / "reports" / "phase2_report.txt"

DEMO_TYPES = [
    "Request for Pothole Repair",
    "Street Light Outages",
    "Missed Trash/Recycling/Yard Waste/Bulk Item",
    "Abandoned Vehicles",
    "Rodent Activity",
]

# Both spellings appear in every year (Phase 1), so merge into the broader name.
NEIGHBORHOOD_MAP = {
    "Allston": "Allston / Brighton",
    "Brighton": "Allston / Brighton",
    "Mattapan": "Greater Mattapan",
    "South Boston": "South Boston / South Boston Waterfront",
}
UNKNOWN_NEIGHBORHOOD = "Unknown / Citywide"  # raw "Boston" or missing

# closure_reason looks like "Case Closed. Closed date : <date> <Category> <free text>"
# (or "Case Closed Case <Category> ..."). Category -> closure_cat.
HEADER_RE = r"^Case Closed\.?\s*(?:Closed date\s*:\s*(?:\w{3} \w{3} \d{2} [\d:]+ \w{3} \d{4}|[\d-]+ [\d:.]+))?\s*"
CATEGORY_PATTERNS = [  # first match wins; checked against the text after the header
    ("duplicate", r"^(?:case )?duplicate"),
    ("invalid", r"^(?:case )?inva[il]+d|^(?:test|testing)\b|^wrong\b"),
    ("automation", r"^(?:bulk item|mattress pickup) automation"),
    ("referred", r"^(?:case )?referred to external agency"),
    ("resubmitted", r"^resubmitted"),
    ("resolved", r"^(?:case )?resolved"),
    ("noted", r"^(?:case )?noted"),
]
EXCLUDE_CATS = {"duplicate", "invalid", "automation", "referred", "resubmitted", "bulk_closure"}
# Administrative backlog purges: >= BULK_MIN cases of one type, each open > BULK_AGE_DAYS,
# closed on the same calendar day (e.g. 1,909 2021 Abandoned Vehicles closed in Oct 2024).
BULK_AGE_DAYS, BULK_MIN = 180, 50
QUANTILES = [0.1, 0.5, 0.8, 0.95, 0.99]


def closure_category(reason: pd.Series) -> pd.Series:
    body = reason.str.replace(HEADER_RE, "", regex=True).str.strip().str.lower()
    cat = pd.Series(pd.NA, index=reason.index, dtype="string")
    for name, pat in CATEGORY_PATTERNS:
        hit = cat.isna() & body.str.contains(pat, regex=True, na=False)
        cat[hit] = name
    cat[cat.isna() & reason.notna()] = "other"
    return cat


def build(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["neighborhood_raw"] = df["neighborhood"]
    nb = df["neighborhood"].replace(NEIGHBORHOOD_MAP)
    df["neighborhood"] = nb.where(nb.notna() & (nb != "Boston"), UNKNOWN_NEIGHBORHOOD)
    df["resolution_days"] = (df["closed_dt"] - df["open_dt"]).dt.total_seconds() / 86400
    df["closure_cat"] = closure_category(df["closure_reason"])
    old = df["resolution_days"] > BULK_AGE_DAYS
    t = df.loc[old, "type"]
    day_count = t.groupby([t, df.loc[old, "closed_dt"].dt.date]).transform("size")
    df.loc[day_count.index[day_count >= BULK_MIN], "closure_cat"] = "bulk_closure"
    df["is_closed"] = df["closed_dt"].notna()
    df["valid_target"] = (
        df["is_closed"] & (df["resolution_days"] > 0) & ~df["closure_cat"].isin(EXCLUDE_CATS)
    )
    return df


def qtable(s: pd.Series) -> dict:
    q = s.quantile(QUANTILES)
    return {f"p{int(k*100)}": round(v, 2) for k, v in q.items()} | {"n": len(s), "max": round(s.max(), 1)}


def report(df: pd.DataFrame, out: list) -> None:
    out.append(f"=== All cases: {len(df):,}")
    out.append("\n=== Neighborhood after merge")
    out.append(df["neighborhood"].value_counts().to_string())

    out.append("\n=== closure_cat counts (closed cases)")
    out.append(df.loc[df.is_closed, "closure_cat"].value_counts(dropna=False).to_string())
    out.append("\nExamples per excluded / other category:")
    for cat in sorted(EXCLUDE_CATS | {"other"}):
        ex = df.loc[df.closure_cat == cat, "closure_reason"].sample(3, random_state=0)
        for s in ex:
            out.append(f"  [{cat}] {s[:140]}")

    closed = df[df.is_closed]
    out.append("\n=== Drop / exclusion funnel (closed cases)")
    out.append(f"closed: {len(closed):,}")
    out.append(f"  resolution_days <= 0: {(closed.resolution_days <= 0).sum():,}")
    out.append(f"  excluded closure_cat: {closed.closure_cat.isin(EXCLUDE_CATS).sum():,}")
    out.append(f"  valid_target (kept): {closed.valid_target.sum():,}")
    out.append(f"open (no closed_dt): {(~df.is_closed).sum():,}")

    out.append("\n=== Excluded share by demo type")
    for t in DEMO_TYPES:
        c = closed[closed.type == t]
        out.append(f"{t}: closed={len(c):,} excluded={100*c.closure_cat.isin(EXCLUDE_CATS).mean():.1f}% "
                   f"nonpos={100*(c.resolution_days<=0).mean():.2f}% "
                   f"cats={c.closure_cat.value_counts().to_dict()}")

    out.append("\n=== % still open (censoring) by year")
    out.append((100 * (~df.is_closed).groupby(df.year).mean()).round(1).to_string())
    out.append("\n=== % still open by demo type x year")
    d = df[df.type.isin(DEMO_TYPES)]
    out.append((100 * (~d.is_closed)).groupby([d.type, d.year]).mean().round(1).unstack().to_string())

    v = df[df.valid_target]
    out.append("\n=== resolution_days quantiles (valid closures), all types, by year")
    out.append(pd.DataFrame({y: qtable(g.resolution_days) for y, g in v.groupby("year")}).T.to_string())
    out.append("\n=== resolution_days quantiles by demo type (all years)")
    out.append(pd.DataFrame({t: qtable(v.loc[v.type == t, "resolution_days"]) for t in DEMO_TYPES}).T.to_string())
    out.append("\n=== resolution_days p50 / p80 by demo type x year")
    dv = v[v.type.isin(DEMO_TYPES)]
    out.append(dv.groupby(["type", "year"]).resolution_days.quantile(0.5).round(2).unstack().to_string())
    out.append(dv.groupby(["type", "year"]).resolution_days.quantile(0.8).round(2).unstack().to_string())
    out.append("\n=== Very short closures (< 5 min) share by demo type (kept, reported only)")
    out.append((100 * (dv.resolution_days < 5 / 1440)).groupby(dv.type).mean().round(1).to_string())
    out.append("\nNo capping/winsorizing applied; extremes kept (see p99 / max above).")


def main() -> None:
    df = build(pd.read_parquet(PROC / "all_raw.parquet"))
    out: list[str] = []
    report(df, out)
    df.to_parquet(PROC / "all_cases.parquet", index=False)
    clean = df[df.valid_target].drop(columns=["valid_target", "is_closed"])
    clean.to_parquet(PROC / "clean.parquet", index=False)
    out.append(f"\nSaved all_cases.parquet ({len(df):,}) and clean.parquet ({len(clean):,})")
    text = "\n".join(out)
    REPORT.write_text(text)
    sys.stdout.write(text + "\n")


if __name__ == "__main__":
    main()

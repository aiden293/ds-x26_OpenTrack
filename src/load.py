"""Phase 1: inspect yearly Boston 311 CSVs, harmonize schema, save all_raw.parquet.

Usage: .venv/bin/python -m src.load
Writes data/processed/all_raw.parquet and reports/phase1_report.txt.
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "all_raw.parquet"
REPORT = ROOT / "reports" / "phase1_report.txt"

# Raw (Lagan) column name -> unified name. Only renames verified in the files.
RENAME = {"sla_target_dt": "target_dt", "on_time": "ontime"}
DATE_COLS = ["open_dt", "target_dt", "closed_dt"]
# Not needed downstream; dropped to keep the parquet small.
DROP = ["geom_4326", "submitted_photo", "closed_photo"]


def read_year(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    df["source_file"] = path.name
    return df


def profile(df: pd.DataFrame, name: str, out: list) -> None:
    out.append(f"\n=== {name}: {len(df):,} rows, {df.shape[1]} cols")
    od = pd.to_datetime(df["open_dt"], errors="coerce", format="mixed")
    out.append(f"open_dt range: {od.min()} -> {od.max()} (unparseable: {od.isna().sum()})")
    miss = (df.isna().mean() * 100).round(1)
    out.append("missing %: " + ", ".join(f"{c}={v}" for c, v in miss.items() if v > 0))


def load_all(out: list) -> pd.DataFrame:
    files = sorted(RAW.glob("*.csv"))
    frames, schemas = [], {}
    for f in files:
        df = read_year(f)
        profile(df, f.name, out)
        schemas[f.name] = list(df.columns)
        frames.append(df)

    # Schema comparison across years
    ref_name, ref = next(iter(schemas.items()))
    out.append("\n=== Schema comparison (vs %s)" % ref_name)
    for name, cols in schemas.items():
        added, missing = set(cols) - set(ref), set(ref) - set(cols)
        same_order = cols == ref
        out.append(f"{name}: added={sorted(added)} missing={sorted(missing)} same_order={same_order}")

    df = pd.concat(frames, ignore_index=True)
    df = df.rename(columns=RENAME).drop(columns=[c for c in DROP if c in df.columns])
    for c in DATE_COLS:
        df[c] = pd.to_datetime(df[c], errors="coerce", format="mixed")
    for c in ["latitude", "longitude"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["year"] = df["open_dt"].dt.year
    return df


def report(df: pd.DataFrame, out: list) -> None:
    out.append(f"\n=== Unified: {len(df):,} rows")
    dup = df["case_enquiry_id"].duplicated().sum()
    out.append(f"duplicate case_enquiry_id: {dup:,}")
    out.append("dtypes: " + ", ".join(f"{c}={t}" for c, t in df.dtypes.items()))
    for c in DATE_COLS:
        out.append(f"{c}: unparsed/missing={df[c].isna().sum():,}")

    out.append("\n=== Top 30 type")
    vc = df["type"].value_counts()
    for t, n in vc.head(30).items():
        sub = df[df["type"] == t]
        out.append(f"{n:>8,}  closed={100*(sub.case_status=='Closed').mean():5.1f}%  "
                   f"target={100*sub.target_dt.notna().mean():5.1f}%  {t}")
    out.append(f"(distinct types: {vc.size})")

    for col in ["neighborhood", "source", "case_status", "ontime"]:
        out.append(f"\n=== {col} values")
        out.append(df[col].value_counts(dropna=False).to_string())

    out.append("\n=== Top closure_reason prefixes (first 60 chars)")
    out.append(df["closure_reason"].str[:60].value_counts().head(30).to_string())
    out.append("\n=== Random sample of 30 closure_reason")
    for s in df["closure_reason"].dropna().sample(30, random_state=0):
        out.append("  " + s[:150].replace("\n", " "))

    out.append("\n=== % target_dt filled by year / status")
    out.append((df.groupby(["year", "case_status"])["target_dt"].apply(lambda s: s.notna().mean() * 100))
               .round(1).unstack().to_string())

    out.append("\n=== Is target_dt set at intake? target_days = target_dt - open_dt per top type")
    df["target_days"] = (df["target_dt"] - df["open_dt"]).dt.total_seconds() / 86400
    rows = []
    for t in vc.head(30).index:
        s = df.loc[df["type"] == t, "target_days"].dropna()
        if s.empty:
            rows.append((t, 0, *[np.nan] * 6))
            continue
        q = s.quantile([0.1, 0.5, 0.9])
        rows.append((t, len(s), q[0.1], q[0.5], q[0.9], (s < 0).mean() * 100,
                     (abs(s - q[0.5]) < 0.5).mean() * 100, s.round().nunique()))
    tab = pd.DataFrame(rows, columns=["type", "n", "p10", "p50", "p90", "neg%", "within12h_of_median%", "n_distinct_days"])
    out.append(tab.round(2).to_string(index=False))


def main() -> None:
    out: list[str] = []
    df = load_all(out)
    report(df, out)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.drop(columns=["target_days"]).to_parquet(OUT, index=False)
    out.append(f"\nSaved {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1e6:.0f} MB)")
    text = "\n".join(out)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text)
    sys.stdout.write(text + "\n")


if __name__ == "__main__":
    main()

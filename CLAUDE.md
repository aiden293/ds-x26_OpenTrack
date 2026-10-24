# CivicPulse: Data Analysis & Modeling (Claude Code instructions)

## Context
- Hackathon: BU Spark! DS+X 2026. Devpost deadline **Sun Oct 25, 11:00 AM ET**. 4-minute demo.
- Product: CivicPulse, a resident-facing Boston 311 tool. Predict how long a new request will take, compare with the city's target date, and show real similar past cases.
- This session covers **data analysis and modeling only**. A teammate builds the Streamlit app separately and will load the files we save (see "Output contract").
- Judges weight Data Science at 25%: substantial dataset, preprocessing, an identifiable method, proper validation, interpreted results. Calling an LLM or making charts alone does not count.

## Ground rules (non-negotiable)
1. **Never invent numbers.** Every metric, count, or example must come from code actually run on the data. If something fails, say so.
2. **No leakage.** Features must be knowable at the moment a request is opened. Never use `closed_dt`, `closure_reason`, `case_status`, `ontime`, or `department` (unless proven to be set at intake) as features.
3. **Chronological evaluation only.** No random train/test split.
4. **Inspect before assuming.** Column names, value sets, and date formats must be verified from the files, not guessed.
5. **Stop at each CHECKPOINT** and print a short summary for the human before continuing.
6. Keep code minimal and readable. Prefer pandas + scikit-learn. Don't add dependencies without reason.
7. Commit to git after each working phase.

## Data
- Raw files: `data/raw/` (Boston 311 Service Requests, one CSV per year, 2021 to 2025, from data.boston.gov, PDDL license).
- **Known risk:** Boston's 311 system reportedly changed in Oct 2025 and column names may differ (e.g. `open_dt` vs `open_date`, `type` vs `service_name`, `closed_dt` vs `close_date`). The 2025 file may be mixed or partial. Check this first.
- Expected (old schema) columns to verify: `case_enquiry_id, open_dt, target_dt, closed_dt, ontime, case_status, closure_reason, case_title, subject, reason, type, queue, department, source, neighborhood, location_zipcode, latitude, longitude`.

## Phase 0: Setup
- Create layout:
  ```
  data/raw/  data/processed/  models/  reports/  notebooks/
  src/load.py  src/clean.py  src/features.py  src/train.py  src/evaluate.py  src/similar.py  src/equity.py
  requirements.txt
  ```
- requirements: pandas, numpy, pyarrow, scikit-learn, joblib, matplotlib (add `holidays`, `shap` only if used).

## Phase 1: Inspect & harmonize (`src/load.py`)
- For each yearly file: row count, columns, dtypes, date range of `open_dt`, missing % per column.
- Detect schema differences across years. Build a mapping to one unified schema. If 2025 contains new-schema rows, map them if the mapping is unambiguous; otherwise drop post-change rows and record the cutoff date.
- Parse datetimes. Save `data/processed/all_raw.parquet`.
- Report: top 30 `type` values by count, `neighborhood` values, `source` values, `case_status` values, sample of 30 `closure_reason` strings, % of rows with `target_dt` filled (by year and by top types).
- Check whether `target_dt` looks set at intake: e.g. is `target_dt - open_dt` nearly constant within a type? Report.

**CHECKPOINT 1:** summarize schema, row counts, `target_dt` usability, and suggest 3 to 5 common request types for the demo (high volume, mostly closed, meaningful to residents, e.g. potholes, street lights, missed trash).

## Phase 2: Clean (`src/clean.py`)
- Target: `resolution_days = (closed_dt - open_dt).total_seconds() / 86400`.
- Keep closed cases for training. Drop: negative or zero durations, missing `closed_dt`.
- Identify duplicate / invalid / administrative closures from `closure_reason` patterns (show the patterns found before filtering). Exclude them from the target and report how many.
- Report per year and per top type: % still open (censoring), duration quantiles (p10, p50, p80, p95, p99).
- Do not winsorize silently; if extreme durations are capped, report the rule.
- Save `data/processed/clean.parquet` (closed, valid) and keep the full table for backlog computation.

## Phase 3: Features (`src/features.py`)
All features must use only information available at each case's `open_dt`.
- Categorical: `type`, `neighborhood`, `source`.
- Time: month, weekday, hour bucket, US/MA holiday flag.
- `target_days = (target_dt - open_dt)` in days, **only if** Checkpoint 1 showed it is set at intake.
- **Backlog** (key feature): number of same-type cases open at time t.
  - Per type: sort all `open_dt` and all `closed_dt` (use ALL cases incl. still-open and excluded closures, since they still occupy the queue; decide and document).
  - `backlog(t) = count(open_dt < t) - count(closed_dt < t)` via `np.searchsorted`.
  - Use 2021 as warm-up so 2022+ backlog is not biased low.
- Rolling recent performance: median `resolution_days` of same type (and same type+neighborhood if enough data) among cases **closed before t** in the prior 30 days. Must not include cases closed after t.
- Write a small sanity test: for a few random cases, recompute backlog and rolling median by brute force and assert equality.

## Phase 4: Split
- Default: train 2022 to 2023, validation 2024 (tuning), test 2025 (up to schema cutoff).
- Adjust if Phase 1 shows 2025 is unusable (then train 2022, validate 2023, test 2024). Document the final split.
- Note censoring: recent test months may be missing long cases. Report % open by month in the test period.

## Phase 5: Models (`src/train.py`)
1. **Baseline:** per-type median (p50) and 80th percentile (p80) from training data. Fallback to `reason`, then global, for sparse types.
2. **Quantile models:** `HistGradientBoostingRegressor(loss="quantile", quantile=0.5)` and `quantile=0.8`, on `log1p(resolution_days)`, native categorical support (or OrdinalEncoder). Light tuning on validation only.
3. **On-time classifier (if `target_days` usable):** `HistGradientBoostingClassifier` predicting `closed_dt <= target_dt`. Label from outcome is fine; features still intake-only.
4. Final app models: after test evaluation is recorded, retrain on train+val+test period and save. Keep the evaluated metrics as the reported numbers.

## Phase 6: Evaluate (`src/evaluate.py`)
On the test set, baseline vs model:
- p50: MAE and median absolute error (days), overall and per demo type.
- p80: empirical coverage (share of actual <= predicted p80, target ~0.80) and pinball loss.
- Classifier: ROC AUC, Brier score, calibration plot (`reports/calibration.png`).
- Global permutation importance on test set (`reports/importance.png`), clearly labelled global.
- If the model does not beat the baseline for a type, say so; the app will use the baseline there.
- Save everything to `reports/metrics.json`.

**CHECKPOINT 2:** print metric table (baseline vs model), coverage, top features, and any failures.

## Phase 7: Similar cases (`src/similar.py`)
- `similar_cases(type, neighborhood, open_date, k=10, reference_date=None) -> DataFrame`
- Candidates: same type, closed before `reference_date` (default: open_date). Prefer same neighborhood; rank by closeness of day-of-year (±60 days) then recency. Widen to all neighborhoods if fewer than k, and add a `match_level` column.
- Never use resolution time as a matching criterion.
- Return: `case_enquiry_id, type, neighborhood, open_dt, closed_dt, resolution_days, closure_reason, match_level`. No lat/long.

## Phase 8: Equity analysis (`src/equity.py`)
- Train a p50 model **without** `neighborhood`. On test data, compute mean and median residual (actual minus predicted, in days) per neighborhood with case counts and bootstrap 95% intervals.
- Save `reports/equity.csv` and `reports/equity.png`.
- Wording: "gap not explained by type, timing, and backlog". Do not claim discrimination or causes. Note reporting bias.

## Output contract (for the app teammate)
Save in `models/` and `data/processed/`:
- `models/p50.joblib`, `models/p80.joblib`, `models/ontime.joblib` (if built), `models/baseline.json`
- `data/processed/cases_for_app.parquet`: closed cases with columns needed by `similar_cases` plus features
- `reports/metrics.json`, `reports/equity.csv`, plots
- `src/predict.py` exposing:
  ```python
  predict(type: str, neighborhood: str, open_date: datetime, source: str | None = None) -> dict
  # returns {"p50": float, "p80": float, "baseline_p50": float, "baseline_p80": float,
  #          "target_days": float | None, "p_ontime": float | None,
  #          "n_support": int, "used_model": "ml" | "baseline"}
  ```
  For a new request, compute backlog and rolling features from the latest data available in `cases_for_app.parquet` and document that assumption.
- Also export `choices.json` (valid type / neighborhood / source values) so the app's dropdowns use real values.

## Ethics notes to keep in reports
- Estimates are historical, not official deadlines or guarantees. Not an official City of Boston service.
- Reporting bias: areas that report more appear more in data.
- Censoring: long open cases are missing from training, so estimates may be short.
- Show neighborhood-level only; no exact coordinates in outputs.
- Data source and date range: City of Boston 311, PDDL.

## Cut order if short on time
Weather (not planned) → on-time classifier → SHAP → equity chart.
**Never cut:** real data, chronological validation, baseline comparison, working `predict()`, real similar cases.

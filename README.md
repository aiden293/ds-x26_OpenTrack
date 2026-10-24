# Civic Pulse

A Boston 311 project that aims to estimate how long citizen service requests take to resolve using historical request data.

## Current stage

Data analysis and modeling are done; the Streamlit app is in progress.

- Data: City of Boston 311 Service Requests 2021-2025 (data.boston.gov, PDDL), 1,433,236 requests, 1,099,534 valid closures after cleaning.
- Models: per-type baseline and gradient-boosted quantile models (p50, p80) for resolution days, plus an on-time classifier. Trained on 2022-2023, tuned on 2024, tested on 2025.
- On the 2025 test set, p50 mean absolute error is 7.84 days vs 8.69 for the baseline (`reports/metrics.json`).
- Also included: real similar past cases and a neighborhood gap analysis (`reports/equity.png`).

Estimates are historical, not official City of Boston deadlines. About 25% of 2025 requests were never closed in the data, and Boston's October 2025 311 system change truncates later closures.

## First milestone

Choose a Boston 311 dataset, inspect its fields, and calculate historical resolution times for one request category.

An initial example could show the typical resolution time for similar requests. Predictions and explanations will need validation before they are presented as reliable estimates.

## Repository

- `README.md` - project overview.
- `BLUEPRINT.md` - minimal scope and next steps.
- `APP_HANDOFF.md` - how the app calls `predict()` and `similar_cases()`, and which caveats to show.
- `src/` - data pipeline (`load`, `clean`, `features`, `train`, `evaluate`, `export`) and app-facing `predict.py`, `similar.py`.
- `tests/` - sanity tests for features and similar cases.
- `models/` - final models and lookup files used by `predict()`; `models/eval/` holds the train-only models behind the reported metrics.
- `reports/` - metrics, charts, and phase reports.
- `requirements.txt` - Python dependencies.
- `.gitignore` - excludes local data, secrets, and generated files. Raw CSVs and processed parquet files are not committed.

## Getting started

Read [the blueprint](BLUEPRINT.md). The first contribution should document the chosen dataset and the fields available for measuring resolution time.

No dependencies or installation steps are required at this stage.
